"""Recovery of runs orphaned by a crashed process."""

import asyncio
import contextlib
from typing import Protocol

import structlog

from brain_agent.persistence.runs import DEFAULT_MAX_ATTEMPTS, RunLedger
from brain_agent.runtime.runner import RunResult

logger = structlog.get_logger(__name__)

# Upper bound on claim rounds in recover_on_startup, so a pathological registry cannot loop forever.
MAX_STARTUP_ROUNDS = 100


class ThreadResumer(Protocol):
    """The part of :class:`AgentRunner` the worker needs.

    ``owner_id`` must be the owner the runner heartbeats with, so claimed leases stay alive;
    ``lease_seconds`` is the lease the runner holds, and the worker claims with the same one.
    """

    @property
    def owner_id(self) -> str: ...

    @property
    def lease_seconds(self) -> float: ...

    async def resume(self, thread_id: str) -> RunResult: ...


class RecoveryWorker:
    """Claims runs whose lease expired and resumes them from their last checkpoint."""

    def __init__(
        self,
        runner: ThreadResumer,
        runs: RunLedger,
        *,
        interval_seconds: float = 15.0,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        batch_size: int = 10,
        max_concurrency: int = 4,
        resume_timeout_seconds: float = 300.0,
    ) -> None:
        if batch_size < 1:
            raise ValueError(f"batch_size must be at least 1, got {batch_size}")
        if max_attempts < 1:
            raise ValueError(f"max_attempts must be at least 1, got {max_attempts}")
        if max_concurrency < 1:
            raise ValueError(f"max_concurrency must be at least 1, got {max_concurrency}")
        if resume_timeout_seconds <= 0:
            raise ValueError(
                f"resume_timeout_seconds must be positive, got {resume_timeout_seconds}"
            )
        self._runner = runner
        self._runs = runs
        self._interval_seconds = interval_seconds
        self._max_attempts = max_attempts
        self._batch_size = batch_size
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._resume_timeout = resume_timeout_seconds

    async def run_once(self) -> list[str]:
        """Claim up to ``batch_size`` orphans and resume them, ``max_concurrency`` at a time.

        Returns the claimed thread ids. A failing or timed-out resume is logged and never
        affects the others (a timed-out run stays ``running`` and is retried once its lease
        expires): the runner has already recorded the outcome (transient errors leave the run
        ``running`` so a later pass retries it, until ``max_attempts``).
        """
        claimed = await self._runs.claim_orphans(
            self._runner.owner_id,
            self._runner.lease_seconds,
            self._batch_size,
            max_attempts=self._max_attempts,
        )
        await asyncio.gather(*(self._resume(thread_id) for thread_id in claimed))
        return claimed

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        """Poll for orphans every ``interval_seconds`` until ``stop_event`` is set."""
        while not stop_event.is_set():
            try:
                await self.run_once()
            except Exception:
                logger.exception("recovery_pass_failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=self._interval_seconds)

    async def _resume(self, thread_id: str) -> None:
        log = logger.bind(thread_id=thread_id)
        async with self._semaphore:
            log.info("recovery_resuming")
            try:
                async with asyncio.timeout(self._resume_timeout):
                    result = await self._runner.resume(thread_id)
            except TimeoutError:
                log.warning("recovery_resume_timed_out", timeout_seconds=self._resume_timeout)
            except Exception as exc:
                log.warning("recovery_resume_failed", error=f"{type(exc).__name__}: {exc}")
            else:
                log.info("recovery_resumed", status=result.status)


async def recover_on_startup(worker: RecoveryWorker) -> list[str]:
    """Recover every currently orphaned run once; meant to be awaited at process start-up.

    Repeats :meth:`RecoveryWorker.run_once` until a pass claims nothing. Runs that fail
    transiently keep a fresh lease, so they are not re-claimed within this call.
    """
    recovered: list[str] = []
    for _ in range(MAX_STARTUP_ROUNDS):
        claimed = await worker.run_once()
        if not claimed:
            break
        recovered.extend(claimed)
    return recovered
