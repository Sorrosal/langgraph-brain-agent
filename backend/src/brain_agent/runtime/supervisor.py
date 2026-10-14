"""Background execution of agent runs, decoupled from the HTTP request that started them."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import structlog

from brain_agent.errors import ThreadBusyError
from brain_agent.runtime.events import EventBroker, EventSink, failure_code

logger = structlog.get_logger(__name__)

MAX_REMEMBERED_FAILURES = 1000

Work = Callable[[EventSink | None], Awaitable[Any]]
"""Starts a run; receives the thread's event sink (``None`` without a broker)."""


class RunSupervisor:
    """Runs agent invocations as asyncio tasks, at most one per thread.

    Requests return as soon as the task is scheduled and the run survives the client going
    away. On :meth:`shutdown` running tasks are cancelled; the runner leaves such runs
    ``running`` in the registry, so the recovery worker reclaims them once the lease expires.

    Admission is two-step so a request can validate before it schedules without racing others:
    :meth:`reserve` claims the thread slot synchronously (raising if it is taken), then the
    request either calls :meth:`start` (which consumes the reservation) or :meth:`release`.
    With a ``broker`` every run publishes its events to it.
    """

    def __init__(self, broker: EventBroker | None = None) -> None:
        self._broker = broker
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._reserved: set[str] = set()
        self._failures: dict[str, str] = {}

    def is_running(self, thread_id: str) -> bool:
        return thread_id in self._tasks or thread_id in self._reserved

    def last_failure(self, thread_id: str) -> str | None:
        """Safe failure code of the thread's latest run if it failed in this process."""
        return self._failures.get(thread_id)

    def reserve(self, thread_id: str) -> None:
        """Claim the thread for a run about to be validated and scheduled.

        Raises:
            ThreadBusyError: the thread already has an active task or reservation.
        """
        if self.is_running(thread_id):
            raise ThreadBusyError(thread_id)
        self._reserved.add(thread_id)

    def release(self, thread_id: str) -> None:
        """Give back a reservation that was not followed by :meth:`start`."""
        self._reserved.discard(thread_id)

    def start(self, thread_id: str, work: Work) -> None:
        """Schedule ``work`` for the thread, taking a reservation if the caller made one.

        Raises:
            ThreadBusyError: the thread already has an active task.
        """
        if thread_id in self._tasks:
            raise ThreadBusyError(thread_id)
        self._reserved.discard(thread_id)
        self._failures.pop(thread_id, None)
        sink = self._broker.sink(thread_id) if self._broker else None
        task = asyncio.create_task(self._run(thread_id, work, sink))
        self._tasks[thread_id] = task
        task.add_done_callback(lambda done: self._finished(thread_id, done))

    async def _run(self, thread_id: str, work: Work, sink: EventSink | None) -> None:
        try:
            await work(sink)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # The full exception goes to the log only; callers see a stable code.
            logger.warning("background_run_failed", thread_id=thread_id, exc_info=True)
            if len(self._failures) >= MAX_REMEMBERED_FAILURES:
                self._failures.pop(next(iter(self._failures)))
            self._failures[thread_id] = failure_code(exc)

    def _finished(self, thread_id: str, task: asyncio.Task[None]) -> None:
        if self._tasks.get(thread_id) is task:
            del self._tasks[thread_id]

    def cancel(self, thread_id: str) -> bool:
        """Cancel the thread's running task; ``False`` when nothing runs for it."""
        task = self._tasks.get(thread_id)
        if task is None:
            return False
        task.cancel()
        return True

    async def shutdown(self) -> None:
        """Cancel every active task and wait for them to unwind."""
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.clear()
        self._reserved.clear()
