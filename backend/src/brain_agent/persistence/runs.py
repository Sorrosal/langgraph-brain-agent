"""Run registry: which threads are executing, who owns them and when the lease runs out.

A run is a unit of graph execution on a thread. Its row in ``agent_runs`` carries a *lease*
that the owning process keeps renewing (heartbeat). If the process dies, the lease expires,
and any other process can claim the run and resume it from the last checkpoint.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol

import structlog
from psycopg import AsyncConnection
from psycopg.rows import DictRow
from psycopg_pool import AsyncConnectionPool

from brain_agent.errors import ThreadBusyError

logger = structlog.get_logger(__name__)

DEFAULT_MAX_ATTEMPTS = 3

RunState = Literal["running", "interrupted", "completed", "failed"]
FinishedState = Literal["interrupted", "completed", "failed"]

MIGRATIONS = (
    """
CREATE TABLE IF NOT EXISTS agent_runs (
    thread_id text PRIMARY KEY,
    status text NOT NULL
        CONSTRAINT agent_runs_status_check
        CHECK (status IN ('running', 'interrupted', 'completed', 'failed')),
    owner text,
    lease_expires_at timestamptz,
    attempts integer NOT NULL DEFAULT 0,
    last_error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
""",
    """
ALTER TABLE agent_runs ADD COLUMN IF NOT EXISTS fencing_token bigint NOT NULL DEFAULT 0
""",
    """
CREATE INDEX IF NOT EXISTS agent_runs_orphan_idx
    ON agent_runs (lease_expires_at) WHERE status = 'running'
""",
)

# Serialises concurrent migrations from several processes starting at once.
_MIGRATION_LOCK_KEY = 7_424_001

_MARK_RUNNING = """
INSERT INTO agent_runs (thread_id, status, owner, lease_expires_at, fencing_token)
VALUES (%(thread_id)s, 'running', %(owner)s, now() + make_interval(secs => %(lease)s), 1)
ON CONFLICT (thread_id) DO UPDATE SET
    status = 'running',
    owner = EXCLUDED.owner,
    lease_expires_at = EXCLUDED.lease_expires_at,
    fencing_token = agent_runs.fencing_token + 1,
    attempts = CASE WHEN %(reset)s THEN 0 ELSE agent_runs.attempts END,
    last_error = CASE WHEN %(reset)s THEN NULL ELSE agent_runs.last_error END,
    updated_at = now()
WHERE agent_runs.status <> 'running'
   OR agent_runs.lease_expires_at IS NULL
   OR agent_runs.lease_expires_at < now()
   OR agent_runs.owner = EXCLUDED.owner
RETURNING fencing_token
"""

_HEARTBEAT = """
UPDATE agent_runs
SET lease_expires_at = now() + make_interval(secs => %(lease)s), updated_at = now()
WHERE thread_id = %(thread_id)s AND owner = %(owner)s AND fencing_token = %(token)s
  AND status = 'running'
RETURNING thread_id
"""

_MARK_FINISHED = """
UPDATE agent_runs
SET status = %(status)s,
    owner = NULL,
    lease_expires_at = NULL,
    last_error = COALESCE(%(error)s, last_error),
    updated_at = now()
WHERE thread_id = %(thread_id)s AND owner = %(owner)s AND fencing_token = %(token)s
RETURNING thread_id
"""

_RECORD_ERROR = """
UPDATE agent_runs SET last_error = %(error)s, updated_at = now()
WHERE thread_id = %(thread_id)s AND owner = %(owner)s AND fencing_token = %(token)s
RETURNING thread_id
"""

_ORPHANS = """
SELECT thread_id FROM agent_runs
WHERE status = 'running'
  AND (lease_expires_at IS NULL OR lease_expires_at < now())
  AND attempts {comparison} %(max_attempts)s
ORDER BY lease_expires_at NULLS FIRST
LIMIT %(limit)s
FOR UPDATE SKIP LOCKED
"""

_FAIL_POISONED = f"""
UPDATE agent_runs
SET status = 'failed',
    owner = NULL,
    lease_expires_at = NULL,
    last_error = COALESCE(last_error || ' | ', '')
        || 'gave up after ' || attempts || ' recovery attempts (max attempts reached)',
    updated_at = now()
WHERE thread_id IN ({_ORPHANS.format(comparison=">=")})
RETURNING thread_id
"""

_CLAIM = f"""
UPDATE agent_runs
SET owner = %(owner)s,
    lease_expires_at = now() + make_interval(secs => %(lease)s),
    attempts = attempts + 1,
    fencing_token = fencing_token + 1,
    updated_at = now()
WHERE thread_id IN ({_ORPHANS.format(comparison="<")})
RETURNING thread_id
"""

_GET = """
SELECT thread_id, status, owner, lease_expires_at, attempts, last_error, fencing_token,
    created_at, updated_at
FROM agent_runs WHERE thread_id = %(thread_id)s
"""

Params = dict[str, Any]


@dataclass(frozen=True, slots=True)
class RunRecord:
    """Snapshot of an ``agent_runs`` row."""

    thread_id: str
    status: RunState
    owner: str | None
    lease_expires_at: datetime | None
    attempts: int
    last_error: str | None
    fencing_token: int
    created_at: datetime
    updated_at: datetime


class RunView(Protocol):
    """Read-only part of a run row that callers rely on (satisfied by :class:`RunRecord`)."""

    @property
    def status(self) -> str: ...

    @property
    def last_error(self) -> str | None: ...


class RunLedger(Protocol):
    """What the runner and the recovery worker need from a run registry."""

    async def mark_running(
        self, thread_id: str, owner: str, lease_seconds: float, *, reset_attempts: bool = True
    ) -> int: ...

    async def heartbeat(
        self, thread_id: str, owner: str, token: int, lease_seconds: float
    ) -> bool: ...

    async def mark_finished(
        self,
        thread_id: str,
        owner: str,
        token: int,
        status: FinishedState,
        error: str | None = None,
    ) -> bool: ...

    async def record_error(self, thread_id: str, owner: str, token: int, error: str) -> bool: ...

    async def claim_orphans(
        self,
        owner: str,
        lease_seconds: float,
        limit: int,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> list[str]: ...

    async def get(self, thread_id: str) -> RunView | None: ...


class RunRegistry:
    """:class:`RunLedger` backed by the ``agent_runs`` table.

    The pool must hand out autocommit connections with ``dict_row`` (as
    :func:`brain_agent.persistence.postgres.open_persistence` configures it).
    """

    def __init__(self, pool: AsyncConnectionPool[AsyncConnection[DictRow]]) -> None:
        self._pool = pool

    async def setup(self) -> None:
        """Create the table and indexes if needed (idempotent, safe to run concurrently)."""
        async with self._pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK_KEY,))
            for statement in MIGRATIONS:  # one statement per call: no multi-command execute
                await conn.execute(statement.encode())

    async def mark_running(
        self, thread_id: str, owner: str, lease_seconds: float, *, reset_attempts: bool = True
    ) -> int:
        """Take (or create) the run for ``owner`` with a fresh lease; return its fencing token.

        The token grows on every claim; the owner-scoped writes below only apply while it is
        still the current one, so a stale owner can never overwrite the new owner's run.

        Raises:
            ThreadBusyError: another owner holds an unexpired lease on the running run.

        ``reset_attempts=False`` is for resuming a claimed run, which must keep its count.
        """
        params: Params = {
            "thread_id": thread_id,
            "owner": owner,
            "lease": float(lease_seconds),
            "reset": reset_attempts,
        }
        async with self._pool.connection() as conn:
            row = await (await conn.execute(_MARK_RUNNING.encode(), params)).fetchone()
        if row is None:
            raise ThreadBusyError(thread_id)
        return int(row["fencing_token"])

    async def heartbeat(self, thread_id: str, owner: str, token: int, lease_seconds: float) -> bool:
        """Extend the lease; ``False`` when ``owner``/``token`` no longer hold the running run."""
        params: Params = {
            "thread_id": thread_id,
            "owner": owner,
            "token": token,
            "lease": float(lease_seconds),
        }
        async with self._pool.connection() as conn:
            cursor = await conn.execute(_HEARTBEAT.encode(), params)
            return await cursor.fetchone() is not None

    async def mark_finished(
        self,
        thread_id: str,
        owner: str,
        token: int,
        status: FinishedState,
        error: str | None = None,
    ) -> bool:
        """Close the run and release its lease; ``False`` (nothing written) for a stale owner."""
        params: Params = {
            "thread_id": thread_id,
            "owner": owner,
            "token": token,
            "status": status,
            "error": error,
        }
        async with self._pool.connection() as conn:
            cursor = await conn.execute(_MARK_FINISHED.encode(), params)
            return await cursor.fetchone() is not None

    async def record_error(self, thread_id: str, owner: str, token: int, error: str) -> bool:
        """Store ``last_error`` without touching status or lease; ``False`` for a stale owner."""
        params: Params = {"thread_id": thread_id, "owner": owner, "token": token, "error": error}
        async with self._pool.connection() as conn:
            cursor = await conn.execute(_RECORD_ERROR.encode(), params)
            return await cursor.fetchone() is not None

    async def claim_orphans(
        self,
        owner: str,
        lease_seconds: float,
        limit: int,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> list[str]:
        """Atomically claim up to ``limit`` running runs whose lease has expired.

        Rows already locked by a concurrent claim are skipped (``FOR UPDATE SKIP LOCKED``),
        so two workers never get the same run. Each claim increments ``attempts``; orphans
        that already used ``max_attempts`` are marked ``failed`` instead of being claimed.
        """
        params: Params = {
            "owner": owner,
            "lease": float(lease_seconds),
            "limit": limit,
            "max_attempts": max_attempts,
        }
        async with self._pool.connection() as conn, conn.transaction():
            poisoned = await (await conn.execute(_FAIL_POISONED.encode(), params)).fetchall()
            claimed_rows = await (await conn.execute(_CLAIM.encode(), params)).fetchall()
        if poisoned:
            logger.error(
                "run_abandoned",
                thread_ids=[row["thread_id"] for row in poisoned],
                max_attempts=max_attempts,
            )
        return [row["thread_id"] for row in claimed_rows]

    async def get(self, thread_id: str) -> RunRecord | None:
        """Return the run row for ``thread_id`` or ``None``."""
        async with self._pool.connection() as conn:
            cursor = await conn.execute(_GET.encode(), {"thread_id": thread_id})
            row = await cursor.fetchone()
        return RunRecord(**row) if row is not None else None
