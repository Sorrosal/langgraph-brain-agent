"""Thread-oriented runner over a compiled, checkpointed agent graph."""

import asyncio
import contextlib
import os
import socket
import uuid
from dataclasses import dataclass
from typing import Literal

import structlog
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import StateSnapshot

from brain_agent.errors import ConfigurationError, ThreadBusyError
from brain_agent.graph.builder import AgentGraph
from brain_agent.graph.retry import is_transient_error
from brain_agent.graph.state import AgentState
from brain_agent.persistence.runs import RunLedger

logger = structlog.get_logger(__name__)

RunStatus = Literal["completed", "interrupted"]

DEFAULT_LEASE_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class RunResult:
    """Outcome of a run or resume on a thread."""

    thread_id: str
    status: RunStatus
    last_message: str | None
    next_nodes: tuple[str, ...]


def default_owner_id() -> str:
    """Identify this runner as ``hostname-pid-uuid``; unique per process and runner."""
    return f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


class AgentRunner:
    """Runs the agent graph per conversation thread with synchronous checkpointing.

    Every superstep is persisted before the next one starts (``durability="sync"``), so a run
    that dies mid-way can be continued with :meth:`resume` from any process sharing the
    same checkpointer.

    When a run registry (``runs``) is given, every run/resume is tracked in it: the run is
    marked ``running`` under a lease owned by ``owner_id``, a background heartbeat renews
    the lease while the graph executes, and the run is closed as ``completed`` or
    ``interrupted`` when the graph stops. A process that dies stops heartbeating, its lease
    expires, and a recovery worker can claim and resume the run.

    Failure policy (an exception escaping the graph, after node-level retries are exhausted):

    * transient (:func:`is_transient_error`) -> ``last_error`` is recorded and the status
      stays ``running``; the lease is no longer renewed, so recovery retries the run later,
      bounded by the registry's ``max_attempts``;
    * anything else -> the run is marked ``failed`` with the error, since retrying a
      deterministic failure cannot help.

    Cancellation (``CancelledError``, e.g. shutdown) is not recorded: the run stays
    ``running`` and is recovered once the lease expires.
    """

    def __init__(
        self,
        graph: AgentGraph,
        *,
        runs: RunLedger | None = None,
        owner_id: str | None = None,
        lease_seconds: float = DEFAULT_LEASE_SECONDS,
        heartbeat_interval: float | None = None,
    ) -> None:
        if not isinstance(graph.checkpointer, BaseCheckpointSaver):
            raise ConfigurationError("AgentRunner requires a graph compiled with a checkpointer")
        if lease_seconds <= 0:
            raise ValueError(f"lease_seconds must be positive, got {lease_seconds}")
        self._graph = graph
        self._runs = runs
        self._owner_id = owner_id or default_owner_id()
        self._lease_seconds = lease_seconds
        self._heartbeat_interval = heartbeat_interval or lease_seconds / 3

    @property
    def owner_id(self) -> str:
        """Identity under which this runner holds run leases."""
        return self._owner_id

    async def run(self, thread_id: str, message: str) -> RunResult:
        """Send a user message on ``thread_id`` and run the agent until it stops.

        Raises:
            ThreadBusyError: if the thread has unfinished work; :meth:`resume` it first.
        """
        config = _thread_config(thread_id)
        pending = await self._graph.aget_state(config)
        if pending.next:
            raise ThreadBusyError(thread_id, tuple(pending.next))
        # A new user message starts a new run, so the step budget starts again.
        update: AgentState = {"messages": [HumanMessage(content=message)], "step_count": 0}
        await self._execute(thread_id, update, reset_attempts=True)
        return await self._finish(thread_id)

    async def resume(self, thread_id: str) -> RunResult:
        """Continue an unfinished run from its last checkpoint; no-op if nothing is pending."""
        config = _thread_config(thread_id)
        snapshot = await self._graph.aget_state(config)
        if snapshot.next:
            await self._execute(thread_id, None, reset_attempts=False)
        return await self._finish(thread_id)

    async def get_state(self, thread_id: str) -> StateSnapshot:
        """Return the latest checkpointed state of ``thread_id``."""
        return await self._graph.aget_state(_thread_config(thread_id))

    async def _execute(
        self, thread_id: str, graph_input: AgentState | None, *, reset_attempts: bool
    ) -> None:
        config = _thread_config(thread_id)
        runs = self._runs
        if runs is None:
            await self._graph.ainvoke(graph_input, config, durability="sync")
            return

        await runs.mark_running(
            thread_id, self._owner_id, self._lease_seconds, reset_attempts=reset_attempts
        )
        heartbeat = asyncio.create_task(self._heartbeat_loop(runs, thread_id))
        try:
            await self._graph.ainvoke(graph_input, config, durability="sync")
        except Exception as exc:
            await self._record_failure(runs, thread_id, exc)
            raise
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat

    async def _heartbeat_loop(self, runs: RunLedger, thread_id: str) -> None:
        log = logger.bind(thread_id=thread_id, owner=self._owner_id)
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            try:
                if not await runs.heartbeat(thread_id, self._owner_id, self._lease_seconds):
                    log.warning("lease_lost")
            except Exception:
                # A missed beat is survivable (the lease outlasts several intervals).
                log.warning("heartbeat_failed", exc_info=True)

    async def _record_failure(self, runs: RunLedger, thread_id: str, exc: Exception) -> None:
        error = f"{type(exc).__name__}: {exc}"
        try:
            if is_transient_error(exc):
                await runs.record_error(thread_id, error)
            else:
                await runs.mark_finished(thread_id, "failed", error)
        except Exception:
            # Never mask the graph's own error; the lease will expire and recovery decides.
            logger.warning("run_failure_not_recorded", thread_id=thread_id, exc_info=True)

    async def _finish(self, thread_id: str) -> RunResult:
        result = await self._result(thread_id)
        if self._runs is not None:
            await self._runs.mark_finished(thread_id, result.status)
        return result

    async def _result(self, thread_id: str) -> RunResult:
        snapshot = await self.get_state(thread_id)
        messages: list[BaseMessage] = (snapshot.values or {}).get("messages", [])
        return RunResult(
            thread_id=thread_id,
            status="interrupted" if snapshot.next else "completed",
            last_message=messages[-1].text if messages else None,
            next_nodes=tuple(snapshot.next),
        )


def _thread_config(thread_id: str) -> RunnableConfig:
    if not thread_id.strip():
        raise ValueError("thread_id must be a non-empty string")
    return {"configurable": {"thread_id": thread_id}}
