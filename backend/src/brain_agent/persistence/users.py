"""Users of the API: the Postgres table and an in-memory twin for tests."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import uuid4

from psycopg import AsyncConnection
from psycopg.errors import UniqueViolation
from psycopg.rows import DictRow
from psycopg_pool import AsyncConnectionPool

from brain_agent.errors import DuplicateEmailError

Role = Literal["admin", "operator"]
Pool = AsyncConnectionPool[AsyncConnection[DictRow]]

MIGRATIONS = (
    """
CREATE TABLE IF NOT EXISTS users (
    id uuid PRIMARY KEY,
    email text NOT NULL,
    password_hash text NOT NULL,
    display_name text NOT NULL DEFAULT '',
    role text NOT NULL CHECK (role IN ('admin', 'operator')),
    created_at timestamptz NOT NULL DEFAULT now()
)
""",
    "CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower_idx ON users (lower(email))",
)

# Serialises registrations so exactly one user (the first) becomes admin.
_USERS_LOCK_KEY = 7_424_002
_COLUMNS = "id::text AS id, email, password_hash, display_name, role, created_at"


@dataclass(frozen=True, slots=True)
class User:
    id: str
    email: str
    password_hash: str
    display_name: str
    role: Role
    created_at: datetime


class UserRepository(Protocol):
    async def create(self, email: str, password_hash: str, display_name: str) -> User:
        """Store a user; the very first one becomes ``admin``, the rest ``operator``.

        Raises:
            DuplicateEmailError: the email (case-insensitive) is already registered.
        """
        ...

    async def get(self, user_id: str) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    async def create(self, email: str, password_hash: str, display_name: str) -> User:
        if await self.get_by_email(email) is not None:
            raise DuplicateEmailError(email)
        role: Role = "operator" if self._users else "admin"
        user = User(str(uuid4()), email, password_hash, display_name, role, datetime.now(UTC))
        self._users[user.id] = user
        return user

    async def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._users.values() if u.email.lower() == email.lower()), None)


class PostgresUserRepository:
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def setup(self) -> None:
        async with self._pool.connection() as conn:
            for statement in MIGRATIONS:
                await conn.execute(statement)

    async def create(self, email: str, password_hash: str, display_name: str) -> User:
        try:
            async with self._pool.connection() as conn, conn.transaction():
                await conn.execute("SELECT pg_advisory_xact_lock(%s)", (_USERS_LOCK_KEY,))
                cursor = await conn.execute(
                    f"""
                    INSERT INTO users (id, email, password_hash, display_name, role)
                    VALUES (%s, %s, %s, %s,
                        CASE WHEN EXISTS (SELECT 1 FROM users) THEN 'operator' ELSE 'admin' END)
                    RETURNING {_COLUMNS}
                    """,
                    (str(uuid4()), email, password_hash, display_name),
                )
                row = await cursor.fetchone()
        except UniqueViolation as exc:
            raise DuplicateEmailError(email) from exc
        assert row is not None
        return _user(row)

    async def get(self, user_id: str) -> User | None:
        return await self._one("id = %s::uuid", user_id)

    async def get_by_email(self, email: str) -> User | None:
        return await self._one("lower(email) = lower(%s)", email)

    async def _one(self, condition: str, value: str) -> User | None:
        async with self._pool.connection() as conn:
            cursor = await conn.execute(f"SELECT {_COLUMNS} FROM users WHERE {condition}", (value,))
            row = await cursor.fetchone()
        return _user(row) if row else None


def _user(row: DictRow) -> User:
    return User(**row)
