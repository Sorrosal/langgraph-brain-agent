"""Pending approvals do not wait forever: stale ones are dismissed in the background."""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import structlog

from brain_agent.errors import ThreadBusyError
from brain_agent.persistence.runs import RunLedger
from brain_agent.persistence.threads import ThreadRepository
from brain_agent.runtime.runner import AgentRunner
from brain_agent.runtime.supervisor import RunSupervisor, Work

logger = structlog.get_logger(__name__)

EXPIRED = "The approval expired without a decision; do not run this action."
SWEEP_LIMIT = 50


async def expire_stale_approvals(
    *,
    runs: RunLedger,
    threads: ThreadRepository,
    runner: AgentRunner,
    supervisor: RunSupervisor,
    ttl: timedelta,
) -> list[str]:
    """Dismiss approvals paused for longer than ``ttl``; returns the threads it resumed."""
    cutoff = datetime.now(UTC) - ttl
    resumed: list[str] = []
    for thread_id in await runs.paused_before(cutoff, SWEEP_LIMIT):
        owner = await threads.owner_of(thread_id)
        if owner is None or await runner.get_pending_interrupt(thread_id) is None:
            continue
        try:
            supervisor.reserve(thread_id)
        except ThreadBusyError:
            continue  # someone is acting on it right now
        supervisor.start(thread_id, _dismiss(runner, thread_id, owner))
        resumed.append(thread_id)
    if resumed:
        logger.info("approvals_expired", thread_ids=resumed, ttl_hours=ttl / timedelta(hours=1))
    return resumed


def _dismiss(runner: AgentRunner, thread_id: str, owner: str) -> Work:
    return lambda sink: runner.dismiss(thread_id, reason=EXPIRED, user_id=owner, sink=sink)


def expiry_loop(
    sweep: Callable[[], Awaitable[list[str]]], interval: float
) -> Callable[[asyncio.Event], Awaitable[None]]:
    """A ``SupervisedLoop`` body that runs ``sweep`` every ``interval`` seconds."""

    async def run(stop: asyncio.Event) -> None:
        while not stop.is_set():
            await sweep()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=interval)

    return run
