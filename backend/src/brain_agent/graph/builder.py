"""Assembly of the agent graph."""

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from langgraph.store.base import BaseStore
from langgraph.types import RetryPolicy

from brain_agent.brain.context import ContextBudget
from brain_agent.brain.policy import RulesApprovalPolicy
from brain_agent.brain.prompt import build_system_prompt, build_turn_context
from brain_agent.brain.rules import RulesEngine
from brain_agent.graph.context_nodes import (
    LOAD_CONTEXT_NODE,
    MEMORIZE_NODE,
    SUMMARIZE_NODE,
    make_load_context,
    make_memorize,
    make_summarize,
)
from brain_agent.graph.nodes import (
    APPROVAL_NODE,
    AWAIT_NODE,
    DEFAULT_SYSTEM_PROMPT,
    REASON_NODE,
    RESOLVE_NODE,
    TOOLS_NODE,
    make_approval_gate,
    make_await_approval,
    make_gate_router,
    make_reason_node,
    route_after_reason,
)
from brain_agent.graph.retry import is_transient_error
from brain_agent.graph.state import AgentState
from brain_agent.hitl.policy import (
    ApprovalPolicy,
    CompositeApprovalPolicy,
    MetadataApprovalPolicy,
)
from brain_agent.persistence.tool_ledger import ToolLedger
from brain_agent.tools.idempotency import make_resolve_uncertain_node, make_tools_node

AgentGraph = CompiledStateGraph[AgentState, None, AgentState, AgentState]


def _turn_context(state: AgentState) -> str:
    """Local date and time, who is talking, the running summary and recalled memories."""
    return build_turn_context(
        session=state.get("session"), summary=state.get("summary"), memories=state.get("context")
    )


DEFAULT_MAX_STEPS = 25
DEFAULT_RECALL_LIMIT = 5

DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=0.5,
    backoff_factor=2.0,
    max_interval=10.0,
    max_attempts=3,
    jitter=True,
    retry_on=is_transient_error,
)


def recursion_limit_for(max_steps: int) -> int:
    """LangGraph superstep budget that lets the step guard, not recursion, end a run.

    Each step is a ``reason``, an ``approval_gate``, an ``await_approval``, a ``resolve_uncertain``
    and a ``tools`` superstep, followed by one final ``reason`` and the ``load_context``,
    ``memorize`` and ``summarize`` supersteps around the loop.
    """
    return 5 * max_steps + 9


def build_graph(
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    *,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    store: BaseStore | None = None,
    max_steps: int = DEFAULT_MAX_STEPS,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
    approval_policy: ApprovalPolicy | None = None,
    tool_ledger: ToolLedger | None = None,
    rules: RulesEngine | None = None,
    context_budget: ContextBudget | None = None,
    memory_extraction: bool = False,
    memory_recall_limit: int = DEFAULT_RECALL_LIMIT,
) -> AgentGraph:
    """Build and compile the reason/act agent graph.

    ``reason`` calls the model (bound to ``tools`` when any are given) and routes tool calls to
    ``approval_gate``, which pauses for a human decision on calls ``approval_policy`` flags
    (default: :class:`MetadataApprovalPolicy`) and then sends the remaining calls to ``tools``;
    ``tools`` always returns to ``reason``. With a ``tool_ledger`` every tool call runs
    exactly once even when the node is replayed after a crash (see
    :mod:`brain_agent.tools.idempotency`); without one tools are simply executed.

    With ``rules`` the system prompt is rebuilt from the rule set on every model call (so rule
    reloads apply, replacing ``system_prompt``) and hard rules join the approval policy: the
    strictest verdict of the rules, ``approval_policy`` (default metadata) wins.

    Around the loop: with a ``store`` a ``load_context`` node recalls up to
    ``memory_recall_limit`` memories at the start of each user turn; at the end of the turn
    ``memorize`` (when ``memory_extraction``) stores durable facts the model extracts, and
    ``summarize`` (when a ``context_budget`` is given) folds old messages into the running
    summary if the history is over budget. All three degrade to no-ops on failure.
    """
    if max_steps < 1:
        raise ValueError(f"max_steps must be at least 1, got {max_steps}")

    bound_model: Runnable[LanguageModelInput, AIMessage] = (
        model.bind_tools(tools) if tools else model
    )
    prompt: str | Callable[[], str] = system_prompt
    policy = approval_policy or MetadataApprovalPolicy()
    if rules is not None:
        engine = rules
        prompt = lambda: build_system_prompt(engine.ruleset)  # noqa: E731
        policy = CompositeApprovalPolicy(RulesApprovalPolicy(engine), policy)
    reason = make_reason_node(
        bound_model,
        system_prompt=prompt,
        turn_context=_turn_context,
        tools=tools,
        max_steps=max_steps,
    )

    builder = StateGraph(AgentState)
    builder.add_node(REASON_NODE, reason, retry_policy=retry_policy)
    if store is not None:
        builder.add_node(LOAD_CONTEXT_NODE, make_load_context(memory_recall_limit))
        builder.add_edge(START, LOAD_CONTEXT_NODE)
        builder.add_edge(LOAD_CONTEXT_NODE, REASON_NODE)
    else:
        builder.add_edge(START, REASON_NODE)
    # Turn end: reason -> memorize -> summarize -> END, skipping what is not enabled.
    turn_end = END
    if context_budget is not None:
        builder.add_node(SUMMARIZE_NODE, make_summarize(model, context_budget))
        builder.add_edge(SUMMARIZE_NODE, END)
        turn_end = SUMMARIZE_NODE
    if memory_extraction and store is not None:
        builder.add_node(MEMORIZE_NODE, make_memorize(model))
        builder.add_edge(MEMORIZE_NODE, turn_end)
        turn_end = MEMORIZE_NODE
    if tools:
        gate = make_approval_gate(tools, policy)
        builder.add_node(APPROVAL_NODE, gate)
        builder.add_node(AWAIT_NODE, make_await_approval(tools, policy))
        builder.add_node(
            TOOLS_NODE, make_tools_node(tools, tool_ledger) if tool_ledger else ToolNode(tools)
        )
        builder.add_conditional_edges(
            REASON_NODE, route_after_reason, {APPROVAL_NODE: APPROVAL_NODE, END: turn_end}
        )
        if tool_ledger:
            builder.add_node(RESOLVE_NODE, make_resolve_uncertain_node(tools, tool_ledger))
        first = RESOLVE_NODE if tool_ledger else TOOLS_NODE
        router = make_gate_router(RESOLVE_NODE)
        after_gate = make_gate_router(first)
        targets = [first, REASON_NODE, AWAIT_NODE]
        builder.add_conditional_edges(APPROVAL_NODE, after_gate, targets)
        builder.add_conditional_edges(AWAIT_NODE, after_gate, targets)
        if tool_ledger:  # calls left unanswered: an uncertain call needs a human first
            builder.add_conditional_edges(TOOLS_NODE, router, [RESOLVE_NODE, REASON_NODE])
        else:
            builder.add_edge(TOOLS_NODE, REASON_NODE)
    else:
        builder.add_edge(REASON_NODE, turn_end)

    graph = builder.compile(checkpointer=checkpointer, store=store)
    return graph.with_config(recursion_limit=recursion_limit_for(max_steps))
