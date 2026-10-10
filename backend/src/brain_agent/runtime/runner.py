"""Thread-oriented runner over a compiled, checkpointed agent graph."""

import asyncio
import contextlib
import os
import socket
import uuid
from dataclasses import dataclass
from typing import Any, Literal

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command, StateSnapshot

from brain_agent.errors import (
    ConfigurationError,
    LeaseLostError,
    NoPendingApprovalError,
    ThreadBusyError,
)
from brain_agent.graph.builder import AgentGraph
from brain_agent.graph.nodes import TOOLS_NODE
from brain_agent.graph.retry import is_transient_error
from brain_agent.graph.state import AgentState
from brain_agent.hitl.models import ApprovalInterrupt, ApprovalResponse
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
    pending_approval: ApprovalInterrupt | None = None
    """Set when the run is paused waiting for a human decision."""


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

    A thread whose pending work belongs to a ``failed`` run is not wedged: the next
    :meth:`run` closes its dangling tool calls with error ``ToolMessage``s and starts the new
    turn. Without a registry a failure cannot be told apart from live work, so pending work
    always raises :class:`ThreadBusyError`.

    Lease fencing: if the heartbeat finds the lease gone (another owner claimed the run after
    this process stalled), the graph task is cancelled and :class:`LeaseLostError` is raised
    from :meth:`run`/:meth:`resume`; the run is left to its new owner, never marked finished.

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
        resolved_interval = lease_seconds / 3 if heartbeat_interval is None else heartbeat_interval
        if resolved_interval <= 0:
            raise ValueError(f"heartbeat_interval must be positive, got {heartbeat_interval}")
        if resolved_interval >= lease_seconds:
            raise ValueError(
                f"heartbeat_interval ({resolved_interval}) must be shorter than "
                f"lease_seconds ({lease_seconds})"
            )
        self._graph = graph
        self._runs = runs
        self._owner_id = owner_id or default_owner_id()
        self._lease_seconds = lease_seconds
        self._heartbeat_interval = resolved_interval

    @property
    def lease_seconds(self) -> float:
        """Duration of the leases this runner takes (and renews)."""
        return self._lease_seconds

    @property
    def owner_id(self) -> str:
        """Identity under which this runner holds run leases."""
        return self._owner_id

    async def run(self, thread_id: str, message: str) -> RunResult:
        """Send a user message on ``thread_id`` and run the agent until it stops.

        Raises:
            ThreadBusyError: if the thread has unfinished work that is not a ``failed`` run
                (or no registry is configured); :meth:`resume` it first.
        """
        config = _thread_config(thread_id)
        pending = await self._graph.aget_state(config)
        if _pending_approval(pending) is not None:
            raise ThreadBusyError(thread_id, tuple(pending.next), approval_pending=True)
        if pending.next:
            record = await self._runs.get(thread_id) if self._runs is not None else None
            if record is None or record.status != "failed":
                raise ThreadBusyError(thread_id, tuple(pending.next))
            await self._abandon_failed_work(thread_id, config, pending, record.last_error)
        # A new user message starts a new run, so the step budget starts again.
        update: AgentState = {"messages": [HumanMessage(content=message)], "step_count": 0}
        token = await self._execute(thread_id, update, reset_attempts=True)
        return await self._finish(thread_id, token)

    async def _abandon_failed_work(
        self,
        thread_id: str,
        config: RunnableConfig,
        snapshot: StateSnapshot,
        last_error: str | None,
    ) -> None:
        """Fix forward: answer unanswered tool calls with an error so the thread is usable."""
        messages: list[BaseMessage] = snapshot.values.get("messages", [])
        answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
        last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
        dangling = [c for c in (last_ai.tool_calls if last_ai else []) if c["id"] not in answered]
        reason = last_error or "unknown error"
        closing = [
            ToolMessage(
                tool_call_id=str(call["id"]),
                content=f"Tool execution failed: {reason}; the run was abandoned.",
                status="error",
            )
            for call in dangling
        ]
        logger.warning("failed_run_abandoned", thread_id=thread_id, closed_tool_calls=len(closing))
        await self._graph.aupdate_state(config, {"messages": closing}, as_node=TOOLS_NODE)

    async def resume(self, thread_id: str) -> RunResult:
        """Continue an unfinished run from its last checkpoint; no-op if nothing is pending."""
        config = _thread_config(thread_id)
        snapshot = await self._graph.aget_state(config)
        if _pending_approval(snapshot) is not None:
            # Waiting for a human, not crashed: resuming blindly would skip the decision.
            return await self._result(thread_id)
        if snapshot.next:
            token = await self._execute(thread_id, None, reset_attempts=False)
        else:
            token = await self._reclaim_stale_row(thread_id)
        return await self._finish(thread_id, token)

    async def approve(self, thread_id: str, response: ApprovalResponse) -> RunResult:
        """Apply the human decisions to the paused approval and continue the run.

        Raises:
            NoPendingApprovalError: the thread is not paused on an approval.
            InvalidApprovalError: the decisions do not match the pending actions; the thread
                stays paused.
        """
        pending = await self.get_pending_approval(thread_id)
        if pending is None:
            raise NoPendingApprovalError(thread_id)
        response.ensure_covers(pending.actions)
        command: Command[Any] = Command(resume=response.model_dump())
        token = await self._execute(thread_id, command, reset_attempts=True)
        return await self._finish(thread_id, token)

    async def get_pending_approval(self, thread_id: str) -> ApprovalInterrupt | None:
        """Return the approval request the thread is paused on, if any."""
        return _pending_approval(await self.get_state(thread_id))

    async def _reclaim_stale_row(self, thread_id: str) -> int | None:
        """Re-lease a ``running`` row with nothing left to run, so it can be closed fenced."""
        if self._runs is None:
            return None
        record = await self._runs.get(thread_id)
        if record is None or record.status != "running":
            return None
        return await self._runs.mark_running(
            thread_id, self._owner_id, self._lease_seconds, reset_attempts=False
        )

    async def get_state(self, thread_id: str) -> StateSnapshot:
        """Return the latest checkpointed state of ``thread_id``."""
        return await self._graph.aget_state(_thread_config(thread_id))

    async def _execute(
        self, thread_id: str, graph_input: AgentState | Command[Any] | None, *, reset_attempts: bool
    ) -> int | None:
        """Run the graph under a lease; return the fencing token (``None`` without a registry)."""
        config = _thread_config(thread_id)
        runs = self._runs
        if runs is None:
            await self._graph.ainvoke(graph_input, config, durability="sync")
            return None

        token = await runs.mark_running(
            thread_id, self._owner_id, self._lease_seconds, reset_attempts=reset_attempts
        )
        lost = asyncio.Event()
        graph_task = asyncio.ensure_future(
            self._graph.ainvoke(graph_input, config, durability="sync")
        )
        heartbeat = asyncio.create_task(
            self._heartbeat_loop(runs, thread_id, token, lost, graph_task)
        )
        try:
            await graph_task
        except asyncio.CancelledError:
            if lost.is_set():
                raise LeaseLostError(thread_id) from None
            raise
        except Exception as exc:
            await self._record_failure(runs, thread_id, token, exc)
            raise
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
        return token

    async def _heartbeat_loop(
        self,
        runs: RunLedger,
        thread_id: str,
        token: int,
        lost: asyncio.Event,
        graph_task: asyncio.Future[object],
    ) -> None:
        log = logger.bind(thread_id=thread_id, owner=self._owner_id)
        while True:
            await asyncio.sleep(self._heartbeat_interval)
            try:
                renewed = await runs.heartbeat(
                    thread_id, self._owner_id, token, self._lease_seconds
                )
            except Exception:
                # A missed beat is survivable (the lease outlasts several intervals).
                log.warning("heartbeat_failed", exc_info=True)
                continue
            if not renewed:
                log.error("lease_lost")
                lost.set()
                graph_task.cancel()
                return

    async def _record_failure(
        self, runs: RunLedger, thread_id: str, token: int, exc: Exception
    ) -> None:
        error = f"{type(exc).__name__}: {exc}"
        try:
            if is_transient_error(exc):
                await runs.record_error(thread_id, self._owner_id, token, error)
            else:
                await runs.mark_finished(thread_id, self._owner_id, token, "failed", error)
        except Exception:
            # Never mask the graph's own error; the lease will expire and recovery decides.
            logger.warning("run_failure_not_recorded", thread_id=thread_id, exc_info=True)

    async def _finish(self, thread_id: str, token: int | None) -> RunResult:
        result = await self._result(thread_id)
        if self._runs is not None and token is not None:
            finished = await self._runs.mark_finished(
                thread_id, self._owner_id, token, result.status
            )
            if not finished:
                raise LeaseLostError(thread_id)
        return result

    async def _result(self, thread_id: str) -> RunResult:
        snapshot = await self.get_state(thread_id)
        messages: list[BaseMessage] = (snapshot.values or {}).get("messages", [])
        return RunResult(
            thread_id=thread_id,
            status="interrupted" if snapshot.next else "completed",
            last_message=messages[-1].text if messages else None,
            next_nodes=tuple(snapshot.next),
            pending_approval=_pending_approval(snapshot),
        )


def _thread_config(thread_id: str) -> RunnableConfig:
    if not thread_id.strip():
        raise ValueError("thread_id must be a non-empty string")
    return {"configurable": {"thread_id": thread_id}}


def _pending_approval(snapshot: StateSnapshot) -> ApprovalInterrupt | None:
    """The approval interrupt still awaiting an answer in the latest state, if any."""
    for interrupt in snapshot.interrupts:
        if isinstance(interrupt.value, dict) and interrupt.value.get("kind") == "approval_required":
            return ApprovalInterrupt.model_validate(interrupt.value)
    return None
