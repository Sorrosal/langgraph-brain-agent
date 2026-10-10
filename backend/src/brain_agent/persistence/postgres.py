"""Opening the PostgreSQL persistence layer used by the agent."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from brain_agent.persistence.runs import RunRegistry

# Serialises schema setup across processes/replicas starting at the same time.
_SETUP_LOCK_KEY = 7_424_000


async def _try_lock(conn: AsyncConnection[DictRow]) -> bool:
    cursor = await conn.execute("SELECT pg_try_advisory_lock(%s) AS locked", (_SETUP_LOCK_KEY,))
    row = await cursor.fetchone()
    return bool(row and row["locked"])


@dataclass(frozen=True, slots=True)
class Persistence:
    """Everything that survives a process: checkpoints, long-term store and the run registry."""

    checkpointer: AsyncPostgresSaver
    store: AsyncPostgresStore
    runs: RunRegistry
    pool: AsyncConnectionPool[AsyncConnection[DictRow]]


@asynccontextmanager
async def open_persistence(
    database_url: str, *, min_size: int = 1, max_size: int = 10
) -> AsyncIterator[Persistence]:
    """Open a connection pool and set up checkpointer, store and run registry on it.

    Connections use ``autocommit=True``, ``prepare_threshold=0`` and ``dict_row``, which
    langgraph-checkpoint-postgres requires. All schema setup is idempotent.
    """
    pool: AsyncConnectionPool[AsyncConnection[DictRow]] = AsyncConnectionPool(
        database_url,
        min_size=min_size,
        max_size=max_size,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        check=AsyncConnectionPool.check_connection,
        open=False,
    )
    async with pool:
        checkpointer = AsyncPostgresSaver(pool)
        store = AsyncPostgresStore(pool)
        runs = RunRegistry(pool)
        # Session-level lock on a dedicated connection (not the pool, which setup also needs).
        async with await AsyncConnection.connect(
            database_url, autocommit=True, row_factory=dict_row
        ) as lock_conn:
            # Poll instead of blocking in pg_advisory_lock: a waiting statement would stall
            # the holder's CREATE INDEX CONCURRENTLY (it waits for every open statement).
            while not await _try_lock(lock_conn):  # noqa: ASYNC110
                await asyncio.sleep(0.05)
            try:
                await checkpointer.setup()
                await store.setup()
                await runs.setup()
            finally:
                await lock_conn.execute("SELECT pg_advisory_unlock(%s)", (_SETUP_LOCK_KEY,))
        yield Persistence(checkpointer=checkpointer, store=store, runs=runs, pool=pool)
