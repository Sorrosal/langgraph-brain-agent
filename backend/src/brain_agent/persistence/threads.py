"""Conversation threads owned by users: the Postgres table and an in-memory twin for tests."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from psycopg import AsyncConnection
from psycopg.rows import DictRow
from psycopg_pool import AsyncConnectionPool

Pool = AsyncConnectionPool[AsyncConnection[DictRow]]

MIGRATIONS = (
    """
CREATE TABLE IF NOT EXISTS threads (
    id text PRIMARY KEY,
    user_id text NOT NULL,
    title text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
)
""",
    "CREATE INDEX IF NOT EXISTS threads_user_idx ON threads (user_id, created_at DESC)",
)

_COLUMNS = "id, user_id, title, created_at, updated_at"


@dataclass(frozen=True, slots=True)
class Thread:
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ThreadRepository(Protocol):
    """Every lookup but :meth:`owner_of` is scoped to the owner, so other users' ids look absent."""

    async def create(self, user_id: str, title: str) -> Thread: ...

    async def get(self, thread_id: str, user_id: str) -> Thread | None: ...

    async def list(self, user_id: str, limit: int, offset: int) -> list[Thread]:
        """The user's threads, newest first."""
        ...

    async def touch(self, thread_id: str, *, title_if_empty: str | None = None) -> None:
        """Bump ``updated_at`` and, when the title is still empty, set it."""
        ...

    async def owner_of(self, thread_id: str) -> str | None: ...


class InMemoryThreadRepository:
    def __init__(self) -> None:
        self._threads: dict[str, Thread] = {}

    async def create(self, user_id: str, title: str) -> Thread:
        now = datetime.now(UTC)
        thread = Thread(uuid4().hex, user_id, title, now, now)
        self._threads[thread.id] = thread
        return thread

    async def get(self, thread_id: str, user_id: str) -> Thread | None:
        thread = self._threads.get(thread_id)
        return thread if thread and thread.user_id == user_id else None

    async def list(self, user_id: str, limit: int, offset: int) -> list[Thread]:
        mine = [t for t in self._threads.values() if t.user_id == user_id]
        return list(reversed(mine))[offset : offset + limit]  # dicts keep creation order

    async def touch(self, thread_id: str, *, title_if_empty: str | None = None) -> None:
        thread = self._threads[thread_id]
        title = thread.title or title_if_empty or ""
        self._threads[thread_id] = replace(thread, title=title, updated_at=datetime.now(UTC))

    async def owner_of(self, thread_id: str) -> str | None:
        thread = self._threads.get(thread_id)
        return thread.user_id if thread else None


class PostgresThreadRepository:
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def setup(self) -> None:
        async with self._pool.connection() as conn:
            for statement in MIGRATIONS:
                await conn.execute(statement)

    async def _rows(self, query: str, *params: object) -> list[DictRow]:
        async with self._pool.connection() as conn:
            cursor = await conn.execute(query, params)
            return await cursor.fetchall()

    async def create(self, user_id: str, title: str) -> Thread:
        rows = await self._rows(
            f"INSERT INTO threads (id, user_id, title) VALUES (%s, %s, %s) RETURNING {_COLUMNS}",
            uuid4().hex,
            user_id,
            title,
        )
        return Thread(**rows[0])

    async def get(self, thread_id: str, user_id: str) -> Thread | None:
        rows = await self._rows(
            f"SELECT {_COLUMNS} FROM threads WHERE id = %s AND user_id = %s", thread_id, user_id
        )
        return Thread(**rows[0]) if rows else None

    async def list(self, user_id: str, limit: int, offset: int) -> list[Thread]:
        rows = await self._rows(
            f"SELECT {_COLUMNS} FROM threads WHERE user_id = %s "
            "ORDER BY created_at DESC, id LIMIT %s OFFSET %s",
            user_id,
            limit,
            offset,
        )
        return [Thread(**row) for row in rows]

    async def touch(self, thread_id: str, *, title_if_empty: str | None = None) -> None:
        await self._rows(
            "UPDATE threads SET updated_at = clock_timestamp(), "
            "title = CASE WHEN title = '' THEN COALESCE(%s, '') ELSE title END "
            "WHERE id = %s RETURNING id",
            title_if_empty,
            thread_id,
        )

    async def owner_of(self, thread_id: str) -> str | None:
        rows = await self._rows("SELECT user_id FROM threads WHERE id = %s", thread_id)
        return str(rows[0]["user_id"]) if rows else None
