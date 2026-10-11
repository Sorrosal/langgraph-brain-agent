"""Background execution of agent runs, decoupled from the HTTP request that started them."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from brain_agent.errors import ThreadBusyError

logger = structlog.get_logger(__name__)


class RunSupervisor:
    """Runs agent invocations as asyncio tasks, at most one per thread.

    Requests return as soon as the task is scheduled and the run survives the client going
    away. On :meth:`shutdown` running tasks are cancelled; the runner leaves such runs
    ``running`` in the registry, so the recovery worker reclaims them once the lease expires.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._failures: dict[str, str] = {}

    def is_running(self, thread_id: str) -> bool:
        return thread_id in self._tasks

    def last_failure(self, thread_id: str) -> str | None:
        """Error of the thread's latest run if it failed in this process, else ``None``."""
        return self._failures.get(thread_id)

    def start(self, thread_id: str, work: Callable[[], Awaitable[Any]]) -> None:
        """Schedule ``work`` for the thread.

        Raises:
            ThreadBusyError: the thread already has an active task.
        """
        if thread_id in self._tasks:
            raise ThreadBusyError(thread_id)
        self._failures.pop(thread_id, None)
        task = asyncio.create_task(self._run(thread_id, work))
        self._tasks[thread_id] = task
        task.add_done_callback(lambda done: self._finished(thread_id, done))

    async def _run(self, thread_id: str, work: Callable[[], Awaitable[Any]]) -> None:
        try:
            await work()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("background_run_failed", thread_id=thread_id, exc_info=True)
            self._failures[thread_id] = f"{type(exc).__name__}: {exc}"

    def _finished(self, thread_id: str, task: asyncio.Task[None]) -> None:
        if self._tasks.get(thread_id) is task:
            del self._tasks[thread_id]

    async def shutdown(self) -> None:
        """Cancel every active task and wait for them to unwind."""
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
