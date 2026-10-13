"""Thread-oriented runner over a compiled, checkpointed agent graph."""

import asyncio
import contextlib
import os
import socket
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

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
    safe_error,
)
from brain_agent.graph.builder import AgentGraph
from brain_agent.graph.nodes import TOOLS_NODE
from brain_agent.graph.retry import is_transient_error
from brain_agent.graph.state import AgentState
from brain_agent.hitl.models import (
    ApprovalInterrupt,
    ApprovalResponse,
    ConfirmDone,
    PendingInterrupt,
    Retry,
    Skip,
    UncertainExecutionInterrupt,
    UncertainResponse,
)
from brain_agent.observability.tracing import observe_run, telemetry
from brain_agent.persistence.runs import RunLedger
from brain_agent.runtime.events import EventSink, failure_data, translate
from brain_agent.tools.memory_tools import DEFAULT_USER_ID

logger = structlog.get_logger(__name__)

RunStatus = Literal["completed", "interrupted"]
Pending = TypeVar("Pending", ApprovalInterrupt, UncertainExecutionInterrupt)

DEFAULT_LEASE_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class RunResult:
    """Outcome of a run or resume on a thread."""

    thread_id: str
    status: RunStatus
    last_message: str | None
    next_nodes: tuple[str, ...]
    pending_approval: ApprovalInterrupt | None = None
    """Set when the run is paused waiting for an approval decision."""
    pending_interrupt: PendingInterrupt | None = None
    """Whatever the run is paused on: an approval or an uncertain tool execution."""


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
        self._active: set[str] = set()  # threads this runner is executing right now

    @property
    def lease_seconds(self) -> float:
        """Duration of the leases this runner takes (and renews)."""
        return self._lease_seconds

    @property
    def owner_id(self) -> str:
        """Identity under which this runner holds run leases."""
        return self._owner_id

    async def run(
        self,
        thread_id: str,
        message: str,
        *,
        user_id: str = DEFAULT_USER_ID,
        session: Mapping[str, str] | None = None,
        sink: EventSink | None = None,
    ) -> RunResult:
        """Send a user message on ``thread_id`` and run the agent until it stops.

        ``session`` (user name, role, language, time zone) is stored in the state with the
        message, so approvals and crash recovery keep it.

        Raises:
            ThreadBusyError: if the thread has unfinished work that is not a ``failed`` run
                (or no registry is configured); :meth:`resume` it first.
        """
        config = _thread_config(thread_id, user_id)
        pending = await self._graph.aget_state(config)
        if _pending_interrupt(pending) is not None:
            raise ThreadBusyError(thread_id, tuple(pending.next), approval_pending=True)
        if pending.next:
            record = await self._runs.get(thread_id) if self._runs is not None else None
            if record is None or record.status != "failed":
                raise ThreadBusyError(thread_id, tuple(pending.next))
            await self._abandon_failed_work(thread_id, config, pending, record.last_error)
        # A new user message starts a new run, so the step budget starts again.
        update: AgentState = {"messages": [HumanMessage(content=message)], "step_count": 0}
        if session:
            update["session"] = dict(session)
        token = await self._execute(
            thread_id, update, user_id, operation="run", reset_attempts=True, sink=sink
        )
        return await self._finish(thread_id, token, sink)

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

    async def resume(
        self, thread_id: str, *, user_id: str = DEFAULT_USER_ID, sink: EventSink | None = None
    ) -> RunResult:
        """Continue an unfinished run from its last checkpoint; no-op if nothing is pending."""
        config = _thread_config(thread_id)
        snapshot = await self._graph.aget_state(config)
        if _pending_interrupt(snapshot) is not None:
            # Waiting for a human, not crashed: resuming blindly would skip the decision.
            # A row still marked running (crash after the pause) is closed as interrupted.
            return await self._finish(thread_id, await self._reclaim_stale_row(thread_id), sink)
        if snapshot.next:
            token = await self._execute(
                thread_id, None, user_id, operation="resume", reset_attempts=False, sink=sink
            )
        else:
            token = await self._reclaim_stale_row(thread_id)
        return await self._finish(thread_id, token, sink)

    async def approve(
        self,
        thread_id: str,
        response: ApprovalResponse,
        *,
        user_id: str = DEFAULT_USER_ID,
        sink: EventSink | None = None,
    ) -> RunResult:
        """Apply the human decisions to the paused approval and continue the run.

        The lease is taken before the pending approval is read, so concurrent calls cannot
        both apply a decision.

        Raises:
            NoPendingApprovalError: the thread is not paused on an approval.
            ThreadBusyError: another call or process is already resuming the thread.
            InvalidApprovalError: the decisions do not match the pending actions; the thread
                stays paused.
        """

        def command(pending: ApprovalInterrupt) -> Command[Any]:
            response.ensure_covers(pending.actions)
            return Command(resume=response.model_dump())

        return await self._resume_paused(
            thread_id, ApprovalInterrupt, command, user_id, sink, "approve"
        )

    async def resolve_uncertain(
        self,
        thread_id: str,
        decisions: Mapping[str, ConfirmDone | Retry | Skip],
        *,
        user_id: str = DEFAULT_USER_ID,
        sink: EventSink | None = None,
    ) -> RunResult:
        """Answer the paused uncertain tool executions, one decision per action id.

        See :class:`UncertainExecutionInterrupt`.

        Raises:
            NoPendingApprovalError: the thread is not paused on an uncertain execution.
            InvalidApprovalError: a pending action has no decision, or an id is unknown.
            ThreadBusyError: another call or process is already resuming the thread.
        """
        return await self._resume_paused(
            thread_id,
            UncertainExecutionInterrupt,
            lambda pending: _uncertain_command(pending, decisions),
            user_id,
            sink,
            "resolve_uncertain",
        )

    async def validate_approval(self, thread_id: str, response: ApprovalResponse) -> None:
        """Check ``response`` against the pending approval without resuming anything.

        Raises:
            NoPendingApprovalError: the thread is not paused on an approval.
            InvalidApprovalError: the decisions do not match the pending actions.
        """
        pending = await self.get_pending_interrupt(thread_id)
        if not isinstance(pending, ApprovalInterrupt):
            raise NoPendingApprovalError(thread_id)
        response.ensure_covers(pending.actions)

    async def validate_uncertain(
        self, thread_id: str, decisions: Mapping[str, ConfirmDone | Retry | Skip]
    ) -> None:
        """Like :meth:`validate_approval`, for a pending uncertain execution."""
        pending = await self.get_pending_interrupt(thread_id)
        if not isinstance(pending, UncertainExecutionInterrupt):
            raise NoPendingApprovalError(thread_id)
        _uncertain_command(pending, decisions)

    async def _resume_paused(
        self,
        thread_id: str,
        kind: type[Pending],
        build_command: Callable[[Pending], Command[Any]],
        user_id: str,
        sink: EventSink | None,
        operation: str,
    ) -> RunResult:
        async def prepare() -> Command[Any]:
            pending = _pending_interrupt(await self.get_state(thread_id))
            if not isinstance(pending, kind):
                raise NoPendingApprovalError(thread_id)
            return build_command(pending)

        token = await self._execute(
            thread_id, prepare, user_id, operation=operation, reset_attempts=True, sink=sink
        )
        return await self._finish(thread_id, token, sink)

    async def get_pending_interrupt(self, thread_id: str) -> PendingInterrupt | None:
        """Return whatever the thread is paused on (approval or uncertain execution), if any."""
        return _pending_interrupt(await self.get_state(thread_id))

    async def get_pending_approval(self, thread_id: str) -> ApprovalInterrupt | None:
        """Return the approval request the thread is paused on, if any."""
        pending = _pending_interrupt(await self.get_state(thread_id))
        return pending if isinstance(pending, ApprovalInterrupt) else None

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

    async def get_history(self, thread_id: str, limit: int) -> list[dict[str, Any]]:
        """Checkpoints of ``thread_id``, newest first, as plain dictionaries.

        ``writes`` names the nodes that produced a checkpoint: they are the ``next`` nodes of
        the checkpoint before it (one more is read to know the oldest one's predecessor).
        """
        config = _thread_config(thread_id)
        snapshots = [s async for s in self._graph.aget_state_history(config, limit=limit + 1)]
        entries = []
        for index, snapshot in enumerate(snapshots[:limit]):
            older = snapshots[index + 1] if index + 1 < len(snapshots) else None
            metadata = snapshot.metadata or {}
            entries.append(
                {
                    "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"],
                    "step": metadata.get("step", -1),
                    "created_at": snapshot.created_at,
                    "source": metadata.get("source", "unknown"),
                    "writes": list(older.next) if older else [],
                    "next": list(snapshot.next),
                    "message_count": len((snapshot.values or {}).get("messages", [])),
                }
            )
        return entries

    async def get_state(self, thread_id: str) -> StateSnapshot:
        """Return the latest checkpointed state of ``thread_id``."""
        return await self._graph.aget_state(_thread_config(thread_id))

    async def _execute(
        self,
        thread_id: str,
        graph_input: AgentState | Command[Any] | Callable[[], Awaitable[Command[Any]]] | None,
        user_id: str,
        *,
        operation: str,
        reset_attempts: bool,
        sink: EventSink | None = None,
    ) -> int | None:
        """Run the graph under a lease; return the fencing token (``None`` without a registry).

        A callable ``graph_input`` is awaited once the thread is claimed (in-process guard and
        lease), so it can validate against state nobody else is changing. If it raises, the
        claim is released and the error propagates. Any failure, including one before the graph
        starts (rejected decision, setup error), is published as ``run_failed`` so event streams
        always see a terminal event. A busy thread is the exception: the run that owns it emits
        its own terminal event, and a rejected caller must not fail it in the eyes of watchers.
        """
        bound = structlog.contextvars.bound_contextvars(thread_id=thread_id, owner=self._owner_id)
        with bound, observe_run(thread_id, operation) as observation:
            try:
                return await self._claim_and_drive(
                    thread_id, graph_input, user_id, reset_attempts, sink
                )
            except Exception as exc:
                if isinstance(exc, LeaseLostError):
                    observation.outcome = "lease_lost"
                if not isinstance(exc, ThreadBusyError):
                    _emit(sink, "run_failed", failure_data(exc))
                raise

    async def _claim_and_drive(
        self,
        thread_id: str,
        graph_input: AgentState | Command[Any] | Callable[[], Awaitable[Command[Any]]] | None,
        user_id: str,
        reset_attempts: bool,
        sink: EventSink | None,
    ) -> int | None:
        config = _thread_config(thread_id, user_id)
        runs = self._runs
        if thread_id in self._active:
            raise ThreadBusyError(thread_id)
        self._active.add(thread_id)
        try:
            token: int | None = None
            if runs is not None:
                prior = await runs.get(thread_id)
                token = await runs.mark_running(
                    thread_id, self._owner_id, self._lease_seconds, reset_attempts=reset_attempts
                )
            if callable(graph_input):
                try:
                    graph_input = await graph_input()
                except BaseException:
                    if runs is not None and token is not None:
                        await self._release(runs, thread_id, token, prior.status if prior else None)
                    raise
            if runs is None or token is None:
                await self._drive(graph_input, config, sink)
                return None
            return await self._execute_leased(runs, thread_id, token, graph_input, config, sink)
        finally:
            self._active.discard(thread_id)

    async def _release(
        self, runs: RunLedger, thread_id: str, token: int, prior: str | None
    ) -> None:
        """Give back a lease taken for a call that did not run the graph, keeping the status."""
        snapshot = await self.get_state(thread_id)
        derived = "interrupted" if snapshot.next else "completed"
        status = prior if prior in ("interrupted", "completed", "failed") else derived
        await runs.mark_finished(thread_id, self._owner_id, token, status)  # type: ignore[arg-type]

    async def _execute_leased(
        self,
        runs: RunLedger,
        thread_id: str,
        token: int,
        graph_input: AgentState | Command[Any] | None,
        config: RunnableConfig,
        sink: EventSink | None,
    ) -> int:
        lost = asyncio.Event()
        graph_task = asyncio.ensure_future(self._drive(graph_input, config, sink))
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

    async def _drive(
        self,
        graph_input: AgentState | Command[Any] | None,
        config: RunnableConfig,
        sink: EventSink | None,
    ) -> None:
        """Execute the graph; with a ``sink`` its progress is streamed as domain events."""
        if sink is None:
            await self._graph.ainvoke(graph_input, config, durability="sync")
            return
        async for mode, data in self._graph.astream(
            graph_input,
            config,
            stream_mode=["messages", "updates"],
            durability="sync",
            subgraphs=False,
        ):
            for kind, payload in translate(mode, data):
                _emit(sink, kind, payload)

    async def _heartbeat_loop(
        self,
        runs: RunLedger,
        thread_id: str,
        token: int,
        lost: asyncio.Event,
        graph_task: asyncio.Future[Any],
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
        error = safe_error(exc)  # the full exception is in the log, never in the registry
        try:
            if is_transient_error(exc):
                await runs.record_error(thread_id, self._owner_id, token, error)
            else:
                await runs.mark_finished(thread_id, self._owner_id, token, "failed", error)
        except Exception:
            # Never mask the graph's own error; the lease will expire and recovery decides.
            logger.warning("run_failure_not_recorded", thread_id=thread_id, exc_info=True)

    async def _finish(
        self, thread_id: str, token: int | None, sink: EventSink | None = None
    ) -> RunResult:
        result = await self._result(thread_id)
        if self._runs is not None and token is not None:
            finished = await self._runs.mark_finished(
                thread_id, self._owner_id, token, result.status
            )
            if not finished:
                _emit(sink, "run_failed", failure_data(LeaseLostError(thread_id)))
                raise LeaseLostError(thread_id)
        telemetry().runs_completed.add(1, {"status": result.status})
        _emit(sink, "run_completed", {"status": result.status})
        return result

    async def _result(self, thread_id: str) -> RunResult:
        snapshot = await self.get_state(thread_id)
        messages: list[BaseMessage] = (snapshot.values or {}).get("messages", [])
        approval = _pending_interrupt(snapshot)
        return RunResult(
            thread_id=thread_id,
            status="interrupted" if snapshot.next else "completed",
            last_message=messages[-1].text if messages else None,
            next_nodes=tuple(snapshot.next),
            pending_approval=approval if isinstance(approval, ApprovalInterrupt) else None,
            pending_interrupt=approval,
        )


def _emit(sink: EventSink | None, kind: str, data: dict[str, Any]) -> None:
    if sink is not None:
        sink(kind, data)


def _uncertain_command(
    pending: UncertainExecutionInterrupt, decisions: Mapping[str, ConfirmDone | Retry | Skip]
) -> Command[Any]:
    ids = [action.action_id for action in pending.actions]
    response = UncertainResponse(decisions=dict(decisions))
    response.ensure_covers(ids, ids)
    return Command(resume=response.model_dump())


def _thread_config(thread_id: str, user_id: str = DEFAULT_USER_ID) -> RunnableConfig:
    if not thread_id.strip():
        raise ValueError("thread_id must be a non-empty string")
    return {"configurable": {"thread_id": thread_id, "user_id": user_id}}


def _pending_interrupt(snapshot: StateSnapshot) -> PendingInterrupt | None:
    """The interrupt still awaiting a human answer in the latest state, if any."""
    for interrupt in snapshot.interrupts:
        value = interrupt.value
        if not isinstance(value, dict):
            continue
        if value.get("kind") == "approval_required":
            return ApprovalInterrupt.model_validate(value)
        if value.get("kind") == "uncertain_execution":
            return UncertainExecutionInterrupt.model_validate(value)
    return None
