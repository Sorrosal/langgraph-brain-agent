"""Tool execution ledger: which tool calls ran, so a replayed ``tools`` node never repeats one.

A row is keyed by an idempotency key (``thread_id:tool_call_id``). ``begin`` records the intent
to execute *before* the tool runs, ``complete``/``fail`` record the outcome afterwards. A row
still ``started`` after a crash means the outcome is unknown: the side effect may have happened.
"""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from psycopg import AsyncConnection
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

ExecutionStatus = Literal["started", "succeeded", "failed"]

MIGRATIONS = (
    """
CREATE TABLE IF NOT EXISTS tool_executions (
    idempotency_key text PRIMARY KEY,
    thread_id text NOT NULL,
    tool_name text NOT NULL,
    args_hash text NOT NULL,
    status text NOT NULL
        CONSTRAINT tool_executions_status_check
        CHECK (status IN ('started', 'succeeded', 'failed')),
    result jsonb,
    error text,
    attempts integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
)
""",
    "CREATE INDEX IF NOT EXISTS tool_executions_thread_idx ON tool_executions (thread_id)",
)

_COLUMNS = "idempotency_key, thread_id, tool_name, args_hash, status, result, error, attempts"

_BEGIN = f"""
INSERT INTO tool_executions (idempotency_key, thread_id, tool_name, args_hash, status)
VALUES (%(key)s, %(thread_id)s, %(tool_name)s, %(args_hash)s, 'started')
ON CONFLICT (idempotency_key) DO UPDATE SET idempotency_key = tool_executions.idempotency_key
RETURNING {_COLUMNS}, (xmax = 0) AS is_new
"""

_COMPLETE = """
UPDATE tool_executions SET status = 'succeeded', result = %(result)s, error = NULL,
    updated_at = now()
WHERE idempotency_key = %(key)s
"""

_FAIL = """
UPDATE tool_executions SET status = 'failed', error = %(error)s, updated_at = now()
WHERE idempotency_key = %(key)s
"""

_RESTART = """
UPDATE tool_executions SET status = 'started', args_hash = %(args_hash)s, result = NULL,
    error = NULL, attempts = attempts + 1, updated_at = now()
WHERE idempotency_key = %(key)s
"""

_GET = f"SELECT {_COLUMNS}, false AS is_new FROM tool_executions WHERE idempotency_key = %(key)s"


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    """Snapshot of a ``tool_executions`` row."""

    idempotency_key: str
    thread_id: str
    tool_name: str
    args_hash: str
    status: ExecutionStatus
    result: dict[str, Any] | None
    error: str | None
    attempts: int
    is_new: bool = False
    """Set by :meth:`ToolLedger.begin` when this call inserted the row."""


class ToolLedger(Protocol):
    """What the tool-execution wrapper needs from a ledger."""

    async def begin(
        self, key: str, thread_id: str, tool_name: str, args_hash: str
    ) -> ExecutionRecord:
        """Insert a ``started`` row, or return the existing one, atomically."""
        ...

    async def complete(self, key: str, result: dict[str, Any]) -> None: ...

    async def fail(self, key: str, error: str) -> None: ...

    async def restart(self, key: str, args_hash: str) -> None:
        """Back to ``started`` for another attempt (bumps ``attempts``, adopts ``args_hash``)."""
        ...

    async def get(self, key: str) -> ExecutionRecord | None: ...


class ToolExecutionLedger:
    """:class:`ToolLedger` backed by the ``tool_executions`` table.

    The pool must hand out autocommit connections with ``dict_row`` (as
    :func:`brain_agent.persistence.postgres.open_persistence` configures it).
    """

    def __init__(self, pool: AsyncConnectionPool[AsyncConnection[DictRow]]) -> None:
        self._pool = pool

    async def setup(self) -> None:
        """Create the table if needed (idempotent; callers serialise concurrent setups)."""
        async with self._pool.connection() as conn:
            for statement in MIGRATIONS:
                await conn.execute(statement.encode())

    async def begin(
        self, key: str, thread_id: str, tool_name: str, args_hash: str
    ) -> ExecutionRecord:
        params = {
            "key": key,
            "thread_id": thread_id,
            "tool_name": tool_name,
            "args_hash": args_hash,
        }
        async with self._pool.connection() as conn:
            row = await (await conn.execute(_BEGIN.encode(), params)).fetchone()
        assert row is not None
        return ExecutionRecord(**row)

    async def complete(self, key: str, result: dict[str, Any]) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(_COMPLETE.encode(), {"key": key, "result": Jsonb(result)})

    async def fail(self, key: str, error: str) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(_FAIL.encode(), {"key": key, "error": error})

    async def restart(self, key: str, args_hash: str) -> None:
        async with self._pool.connection() as conn:
            await conn.execute(_RESTART.encode(), {"key": key, "args_hash": args_hash})

    async def get(self, key: str) -> ExecutionRecord | None:
        async with self._pool.connection() as conn:
            row = await (await conn.execute(_GET.encode(), {"key": key})).fetchone()
        return ExecutionRecord(**row) if row is not None else None
