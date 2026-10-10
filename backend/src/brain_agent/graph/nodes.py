"""Graph nodes and routing."""

from collections.abc import Awaitable
from typing import Protocol

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import END

from brain_agent.graph.state import AgentState

REASON_NODE = "reason"
TOOLS_NODE = "tools"

DEFAULT_SYSTEM_PROMPT = (
    "You are Brain Agent, a careful business operations assistant. "
    "Use the available tools when they help, and answer concisely."
)


class ReasonNode(Protocol):
    """Async node signature LangGraph recognises as accepting the run config."""

    def __call__(self, state: AgentState, config: RunnableConfig) -> Awaitable[AgentState]: ...


def step_limit_message(max_steps: int) -> str:
    """Final answer used when the step guard stops the run."""
    return (
        f"I stopped because I reached the maximum of {max_steps} reasoning steps for this "
        "request. Please narrow the request or ask me to continue."
    )


def make_reason_node(
    model: Runnable[LanguageModelInput, AIMessage],
    *,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    max_steps: int | None = None,
) -> ReasonNode:
    """Create the node that calls the (already tool-bound) chat model.

    When ``max_steps`` is set and the run has already taken that many steps, the node skips
    the model and returns a final message explaining the limit.
    """

    async def reason(state: AgentState, config: RunnableConfig) -> AgentState:
        step_count = state.get("step_count", 0)
        if max_steps is not None and step_count >= max_steps:
            return {"messages": [AIMessage(content=step_limit_message(max_steps))]}

        prompt = [SystemMessage(content=system_prompt), *state["messages"]]
        response = await model.ainvoke(prompt, config)
        return {"messages": [response], "step_count": step_count + 1}

    return reason


def route_after_reason(state: AgentState) -> str:
    """Go to the tools node when the last AI message requests tool calls, else finish."""
    messages = state["messages"]
    last = messages[-1] if messages else None
    if isinstance(last, AIMessage) and last.tool_calls:
        return TOOLS_NODE
    return END
