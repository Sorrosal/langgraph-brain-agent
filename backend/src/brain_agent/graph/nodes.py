"""Graph nodes and routing."""

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Protocol

import structlog
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolCall, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END
from langgraph.types import Send, interrupt

from brain_agent.brain.prompt import UNTRUSTED_TAG
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


CLEAR_TOOL_RESULT_CHARS = 1500
"""Tool results from earlier turns longer than this are replaced by a stub in the prompt."""

UNTRUSTED_REASON = (
    "Content from outside the organisation (e.g. an email) is in this conversation; a human "
    "confirms any action that follows it."
)


def _with_taint(verdict: PolicyVerdict | None) -> PolicyVerdict:
    """Require approval because outside content is in scope, keeping any rule verdict visible."""
    if verdict is None:
        return PolicyVerdict(risk="high", reason=UNTRUSTED_REASON, rule_ids=("untrusted-content",))
    if verdict.blocked:
        return verdict
    return PolicyVerdict(
        risk="high",
        reason=f"{verdict.reason} {UNTRUSTED_REASON}",
        rule_ids=(*verdict.rule_ids, "untrusted-content"),
    )


def last_human_index(messages: Sequence[AnyMessage]) -> int | None:
    """Index of the latest human message, where the current turn starts."""
    return next((i for i in range(len(messages) - 1, -1, -1) if messages[i].type == "human"), None)


def _tool_names(messages: Sequence[AnyMessage]) -> dict[str, str]:
    """Tool call id -> tool name, from the AI messages' tool calls."""
    return {
        str(call["id"]): call["name"]
        for m in messages
        if isinstance(m, AIMessage)
        for call in m.tool_calls
    }


def is_untrusted(message: AnyMessage) -> bool:
    """A tool result spotlighted as outside content (see ``tools/email_tools.py``)."""
    return isinstance(message, ToolMessage) and message.text.lstrip().startswith(
        f"<{UNTRUSTED_TAG}"
    )


def untrusted_in_context(state: AgentState) -> bool:
    """Whether outside content can still steer the model in this thread.

    Sticky on purpose: once an email has been read, the model's own paraphrase of it stays in
    the history, and compaction folds it into the summary (``summary_tainted``). Conservative,
    like FIDES' most-restrictive-wins labels: writes keep needing a human for this thread.
    """
    return bool(state.get("summary_tainted")) or any(map(is_untrusted, state["messages"]))


def clear_old_tool_results(messages: Sequence[AnyMessage]) -> tuple[list[AnyMessage], int]:
    """The prompt view of the history: long tool results from earlier turns become a stub.

    Only what the model sees changes; the persisted state keeps every result (the inspector and
    the summary still have them). Returns the view and how many results were cleared.
    """
    start = last_human_index(messages)
    if start is None:
        return list(messages), 0
    names = _tool_names(messages)
    view: list[AnyMessage] = []
    cleared = 0
    for index, message in enumerate(messages):
        if (
            index < start
            and isinstance(message, ToolMessage)
            and len(message.text) > CLEAR_TOOL_RESULT_CHARS
        ):
            name = names.get(message.tool_call_id, "the tool")
            stub = f"[Earlier result of {name} cleared to save context; call it again if needed.]"
            view.append(message.model_copy(update={"content": stub}))
            cleared += 1
        else:
            view.append(message)
    return view, cleared


def _usage(response: AIMessage) -> dict[str, int | None]:
    """Provider-reported input tokens and how many of them came from its prompt cache."""
    usage = response.usage_metadata
    if usage is None:
        return {"input_tokens": None, "cached_tokens": None}
    details = usage.get("input_token_details") or {}
    return {"input_tokens": usage["input_tokens"], "cached_tokens": details.get("cache_read")}


def _default_turn_context(state: AgentState) -> str | None:
    parts = []
    if summary := state.get("summary"):
        parts.append(f"Conversation summary so far:\n{summary}")
    if context := state.get("context"):
        parts.append(context)
    return "\n\n".join(parts) or None


def make_reason_node(
    model: Runnable[LanguageModelInput, AIMessage],
    *,
    system_prompt: str | Callable[[], str] = DEFAULT_SYSTEM_PROMPT,
    turn_context: Callable[[AgentState], str | None] = _default_turn_context,
    max_steps: int | None = None,
) -> ReasonNode:
    """Create the node that calls the (already tool-bound) chat model.

    The prompt is ``[system prompt, earlier history, turn context, current turn]``: the system
    prompt is stable (a callable is evaluated per call so rule reloads apply) and the volatile
    ``turn_context`` sits right before the latest user message, so the provider's prompt cache
    keeps the prefix. Long tool results from earlier turns are cleared in the prompt view. The
    node records what it sent in ``context_report`` (shown by the inspector).

    When ``max_steps`` is set and the run has already taken that many steps, the node skips
    the model and returns a final message explaining the limit.
    """

    async def reason(state: AgentState, config: RunnableConfig) -> AgentState:
        step_count = state.get("step_count", 0)
        if max_steps is not None and step_count >= max_steps:
            return {"messages": [AIMessage(content=step_limit_message(max_steps))]}

        system = system_prompt() if callable(system_prompt) else system_prompt
        history, cleared = clear_old_tool_results(state["messages"])
        context = turn_context(state)
        cut = last_human_index(history)
        if context and cut is not None:
            prompt = [
                SystemMessage(content=system),
                *history[:cut],
                SystemMessage(content=context),
                *history[cut:],
            ]
        else:
            joined = f"{system}\n\n{context}" if context else system
            prompt = [SystemMessage(content=joined), *history]
        response = await model.ainvoke(prompt, config)
        report = {
            "step": step_count + 1,
            "system_tokens": count_tokens_approximately([SystemMessage(content=system)]),
            "turn_context": context or "",
            "turn_context_tokens": (
                count_tokens_approximately([SystemMessage(content=context)]) if context else 0
            ),
            "history_messages": len(history),
            "history_tokens": count_tokens_approximately(history),
            "cleared_tool_results": cleared,
            "untrusted_in_context": untrusted_in_context(state),
            **_usage(response),
        }
        return {"messages": [response], "step_count": step_count + 1, "context_report": report}

    return reason


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
        tainted = untrusted_in_context(state)
        for call_id, call in calls.items():
            tool = tools_by_name.get(call["name"])
            verdict = policy.evaluate(call, tool)
            if tainted and not (tool is not None and (tool.metadata or {}).get("read_only")):
                # Untrusted content in scope may be steering this action: a human decides.
                verdict = _with_taint(verdict)
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
