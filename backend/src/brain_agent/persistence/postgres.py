"""Opening the PostgreSQL persistence layer used by the agent."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from brain_agent.persistence.runs import RunRegistry


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
        await checkpointer.setup()
        await store.setup()
        await runs.setup()
        yield Persistence(checkpointer=checkpointer, store=store, runs=runs, pool=pool)
