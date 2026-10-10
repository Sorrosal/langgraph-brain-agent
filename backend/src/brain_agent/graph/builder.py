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

from brain_agent.brain.policy import RulesApprovalPolicy
from brain_agent.brain.prompt import build_system_prompt
from brain_agent.brain.rules import RulesEngine
from brain_agent.graph.nodes import (
    APPROVAL_NODE,
    DEFAULT_SYSTEM_PROMPT,
    REASON_NODE,
    RESOLVE_NODE,
    TOOLS_NODE,
    make_approval_gate,
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

DEFAULT_MAX_STEPS = 25

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

    Each step is a ``reason``, an ``approval_gate``, a ``resolve_uncertain`` and a ``tools``
    superstep, followed by one final ``reason``.
    """
    return 4 * max_steps + 5


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
    reason = make_reason_node(bound_model, system_prompt=prompt, max_steps=max_steps)

    builder = StateGraph(AgentState)
    builder.add_node(REASON_NODE, reason, retry_policy=retry_policy)
    builder.add_edge(START, REASON_NODE)
    if tools:
        gate = make_approval_gate(tools, policy)
        builder.add_node(APPROVAL_NODE, gate)
        builder.add_node(
            TOOLS_NODE, make_tools_node(tools, tool_ledger) if tool_ledger else ToolNode(tools)
        )
        builder.add_conditional_edges(REASON_NODE, route_after_reason, [APPROVAL_NODE, END])
        if tool_ledger:
            builder.add_node(RESOLVE_NODE, make_resolve_uncertain_node(tools, tool_ledger))
        first = RESOLVE_NODE if tool_ledger else TOOLS_NODE
        router = make_gate_router(RESOLVE_NODE)
        builder.add_conditional_edges(APPROVAL_NODE, make_gate_router(first), [first, REASON_NODE])
        if tool_ledger:  # calls left unanswered: an uncertain call needs a human first
            builder.add_conditional_edges(TOOLS_NODE, router, [RESOLVE_NODE, REASON_NODE])
        else:
            builder.add_edge(TOOLS_NODE, REASON_NODE)
    else:
        builder.add_edge(REASON_NODE, END)

    graph = builder.compile(checkpointer=checkpointer, store=store)
    return graph.with_config(recursion_limit=recursion_limit_for(max_steps))
