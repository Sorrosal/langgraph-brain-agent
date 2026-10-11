"""Graph nodes and routing."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol

import structlog
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolCall, ToolMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END
from langgraph.types import Send, interrupt

from brain_agent.graph.state import AgentState
from brain_agent.hitl.models import ActionRequest, ApprovalInterrupt, ApprovalResponse
from brain_agent.hitl.policy import ApprovalPolicy, PolicyVerdict

logger = structlog.get_logger(__name__)

REASON_NODE = "reason"
APPROVAL_NODE = "approval_gate"
AWAIT_NODE = "await_approval"
RESOLVE_NODE = "resolve_uncertain"
TOOLS_NODE = "tools"

DEFAULT_SYSTEM_PROMPT = (
    "You are Brain Agent, a careful business operations assistant. "
    "Use the available tools when they help, and answer concisely."
)


class ReasonNode(Protocol):
    """Async node signature LangGraph recognises as accepting the run config."""

    def __call__(self, state: AgentState, config: RunnableConfig) -> Awaitable[AgentState]: ...


class GateNode(Protocol):
    """Async node signature of the approval gate."""

    def __call__(self, state: AgentState) -> Awaitable[dict[str, Any]]: ...


def step_limit_message(max_steps: int) -> str:
    """Final answer used when the step guard stops the run."""
    return (
        f"I stopped because I reached the maximum of {max_steps} reasoning steps for this "
        "request. Please narrow the request or ask me to continue."
    )


def make_reason_node(
    model: Runnable[LanguageModelInput, AIMessage],
    *,
    system_prompt: str | Callable[[str | None], str] = DEFAULT_SYSTEM_PROMPT,
    max_steps: int | None = None,
) -> ReasonNode:
    """Create the node that calls the (already tool-bound) chat model.

    ``system_prompt`` may be a callable, evaluated on every call (so rule reloads apply); it
    receives the extra context: the running conversation summary and the recalled memories.

    When ``max_steps`` is set and the run has already taken that many steps, the node skips
    the model and returns a final message explaining the limit.
    """

    async def reason(state: AgentState, config: RunnableConfig) -> AgentState:
        step_count = state.get("step_count", 0)
        if max_steps is not None and step_count >= max_steps:
            return {"messages": [AIMessage(content=step_limit_message(max_steps))]}

        extra = _extra_context(state)
        text = system_prompt(extra) if callable(system_prompt) else _join(system_prompt, extra)
        prompt = [SystemMessage(content=text), *state["messages"]]
        response = await model.ainvoke(prompt, config)
        return {"messages": [response], "step_count": step_count + 1}

    return reason


def _extra_context(state: AgentState) -> str | None:
    parts = []
    if summary := state.get("summary"):
        parts.append(f"Conversation summary so far:\n{summary}")
    if context := state.get("context"):
        parts.append(context)
    return "\n\n".join(parts) or None


def _join(prompt: str, extra: str | None) -> str:
    return f"{prompt}\n\n{extra}" if extra else prompt


def route_after_reason(state: AgentState) -> str:
    """Go to the approval gate when the last AI message requests tool calls, else finish."""
    messages = state["messages"]
    last = messages[-1] if messages else None
    if isinstance(last, AIMessage) and last.tool_calls:
        return APPROVAL_NODE
    return END


def pending_tool_calls(messages: Sequence[AnyMessage]) -> list[ToolCall]:
    """Tool calls of the latest AI message that have no ``ToolMessage`` yet."""
    last_ai = next(
        (i for i in range(len(messages) - 1, -1, -1) if isinstance(messages[i], AIMessage)), None
    )
    if last_ai is None:
        return []
    ai = messages[last_ai]
    assert isinstance(ai, AIMessage)
    answered = {m.tool_call_id for m in messages[last_ai + 1 :] if isinstance(m, ToolMessage)}
    return [call for call in ai.tool_calls if call["id"] not in answered]


def make_approval_gate(tools: Sequence[BaseTool], policy: ApprovalPolicy) -> GateNode:
    """Create the node that evaluates the policy and records verdicts in ``pending_review``.

    It never interrupts: its write is checkpointed before :func:`make_await_approval` pauses.
    """
    tools_by_name = {tool.name: tool for tool in tools}

    async def approval_gate(state: AgentState) -> dict[str, Any]:
        pending = pending_tool_calls(state["messages"])
        calls = {str(call["id"]): call for call in pending}
        if len(calls) != len(pending):
            return _reject_duplicate_ids(pending)
        blocked: list[tuple[ToolCall, PolicyVerdict]] = []
        verdicts: dict[str, dict[str, Any]] = {}
        for call_id, call in calls.items():
            verdict = policy.evaluate(call, tools_by_name.get(call["name"]))
            if verdict is None:
                continue
            if verdict.blocked:
                blocked.append((call, verdict))
            else:
                verdicts[call_id] = {
                    "blocked": False,
                    "risk": verdict.risk,
                    "reason": verdict.reason,
                    "rule_ids": list(verdict.rule_ids),
                }
        update = _refuse_blocked(blocked)
        if verdicts:
            last_ai = next(m for m in reversed(state["messages"]) if isinstance(m, AIMessage))
            update["pending_review"] = {"ai_message_id": last_ai.id, "verdicts": verdicts}
        return update

    return approval_gate


def make_await_approval(
    tools: Sequence[BaseTool] = (), policy: ApprovalPolicy | None = None
) -> GateNode:
    """Create the node that pauses for a human decision on the calls in ``pending_review``.

    The whole batch waits. On resume LangGraph re-runs this node from its start, so it only
    reads the persisted verdicts. The one exception is an ``edit`` decision: the edited call is
    re-checked against the ``policy``'s block verdicts (a live policy can only tighten) and
    refused if it is now blocked.
    """
    tools_by_name = {tool.name: tool for tool in tools}

    def blocking_verdict(call: ToolCall) -> PolicyVerdict | None:
        verdict = policy.evaluate(call, tools_by_name.get(call["name"])) if policy else None
        return verdict if verdict and verdict.blocked else None

    async def await_approval(state: AgentState) -> dict[str, Any]:
        review = state.get("pending_review") or {}
        verdicts = review.get("verdicts", {})
        last_ai = next(
            m
            for m in reversed(state["messages"])
            if isinstance(m, AIMessage) and m.id == review.get("ai_message_id")
        )
        calls = {str(c["id"]): c for c in last_ai.tool_calls if str(c["id"]) in verdicts}
        actions = [
            ActionRequest(
                action_id=call_id,
                tool_name=call["name"],
                args=call["args"],
                risk=verdicts[call_id]["risk"],
                reason=verdicts[call_id]["reason"],
            )
            for call_id, call in calls.items()
        ]
        raw = interrupt(ApprovalInterrupt(actions=actions).model_dump())
        response = ApprovalResponse.model_validate(raw)
        response.ensure_covers(actions)
        decided = _apply_decisions(state, calls, response, blocking_verdict)
        return {**decided, "pending_review": None}

    return await_approval


def _refuse_blocked(
    blocked: list[tuple[ToolCall, PolicyVerdict]], *, prefix: str = "Blocked"
) -> dict[str, Any]:
    """Answer blocked calls with an error and an audit entry; they never run nor wait."""
    messages: list[AnyMessage] = []
    approvals: list[dict[str, Any]] = []
    for call, verdict in blocked:
        call_id, name = str(call["id"]), call["name"]
        text = f"{prefix} by rule {', '.join(verdict.rule_ids)}: {verdict.reason}"
        messages.append(ToolMessage(tool_call_id=call_id, name=name, content=text, status="error"))
        approvals.append(
            {
                "action_id": call_id,
                "tool_name": name,
                "decision": "blocked",
                "rule_ids": list(verdict.rule_ids),
            }
        )
        logger.info("tool_call_blocked", tool=name, rules=list(verdict.rule_ids))
    return {"messages": messages, "approvals": approvals}


def _reject_duplicate_ids(pending: list[ToolCall]) -> dict[str, Any]:
    """Answer the whole batch with errors: ids key approvals and results, so they must be unique."""
    names = {str(call["id"]): call["name"] for call in pending}
    text = "Rejected: the batch reuses a tool_call id (duplicate ids); no call was executed."
    logger.warning("duplicate_tool_call_ids", ids=sorted(names))
    return {
        "messages": [
            ToolMessage(tool_call_id=call_id, name=name, content=text, status="error")
            for call_id, name in names.items()
        ]
    }


def _apply_decisions(
    state: AgentState,
    calls: dict[str, ToolCall],
    response: ApprovalResponse,
    blocking_verdict: Callable[[ToolCall], PolicyVerdict | None],
) -> dict[str, Any]:
    """Turn decisions into state updates: edited call, answers for skipped calls, audit trail."""
    last_ai = next(m for m in reversed(state["messages"]) if isinstance(m, AIMessage))
    updated_calls = list(last_ai.tool_calls)
    messages: list[AnyMessage] = []
    approvals: list[dict[str, Any]] = []
    for call_id, decision in response.decisions.items():
        call = calls[call_id]
        approvals.append(
            {"action_id": call_id, "tool_name": call["name"], "decision": decision.type}
        )
        if decision.type == "edit":
            index = next(i for i, c in enumerate(updated_calls) if c["id"] == call_id)
            edited: ToolCall = {**updated_calls[index], "args": decision.args}
            if (verdict := blocking_verdict(edited)) is not None:
                refused = _refuse_blocked([(edited, verdict)], prefix="Edited call blocked")
                messages += refused["messages"]
                approvals[-1] = refused["approvals"][0]
                continue
            updated_calls[index] = edited
        elif decision.type == "reject":
            text = f"Rejected by human reviewer: {decision.reason or 'no reason given'}"
            messages.append(
                ToolMessage(tool_call_id=call_id, name=call["name"], content=text, status="error")
            )
        elif decision.type == "respond":
            messages.append(
                ToolMessage(tool_call_id=call_id, name=call["name"], content=decision.message)
            )
    if updated_calls != last_ai.tool_calls:
        # Same message id: add_messages replaces the original instead of appending.
        messages.insert(0, last_ai.model_copy(update={"tool_calls": updated_calls}))
    return {"messages": messages, "approvals": approvals}


def make_gate_router(target: str) -> Callable[[AgentState], list[Send] | str]:
    """Route to ``target`` with the calls still unanswered; with none left, reason again."""

    def route_after_gate(state: AgentState) -> list[Send] | str:
        if state.get("pending_review"):
            return AWAIT_NODE
        calls = pending_tool_calls(state["messages"])
        return [Send(target, calls)] if calls else REASON_NODE

    return route_after_gate
