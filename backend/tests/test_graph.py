"""Tests for the core agent graph: reasoning loop, tools, step guard and retries."""

from typing import Any, cast

import openai
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END

from brain_agent.graph.builder import DEFAULT_RETRY_POLICY, build_graph
from brain_agent.graph.nodes import APPROVAL_NODE, route_after_reason
from brain_agent.graph.retry import is_transient_error
from brain_agent.graph.state import AgentState
from tests.fakes import ScriptedChatModel, tool_call

FAST_RETRY_POLICY = DEFAULT_RETRY_POLICY._replace(initial_interval=0.0, jitter=False)


@tool
def add(a: int, b: int) -> int:
    """Add two integers."""
    return a + b


def _input(text: str) -> AgentState:
    return {"messages": [HumanMessage(content=text)]}


async def test_plain_answer_ends_after_one_reasoning_step() -> None:
    model = ScriptedChatModel(script=[AIMessage(content="Hello!")])
    graph = build_graph(model, [])

    result = await graph.ainvoke(_input("hi"))

    assert [m.text for m in result["messages"]] == ["hi", "Hello!"]
    assert result["step_count"] == 1
    assert model.calls == 1
    assert model.bound_tool_names == []
    first_input = model.inputs[0]
    assert isinstance(first_input[0], SystemMessage)
    # The per-turn context block sits right before the latest user message.
    assert isinstance(first_input[1], SystemMessage)
    assert "Current date and time" in str(first_input[1].content)
    assert first_input[2:] == [HumanMessage(content="hi", id=first_input[2].id)]


async def test_tool_call_executes_tool_then_returns_final_answer() -> None:
    model = ScriptedChatModel(
        script=[tool_call("add", {"a": 2, "b": 3}, "call-1"), AIMessage(content="It is 5.")]
    )
    graph = build_graph(model, [add])

    result = await graph.ainvoke(_input("what is 2 + 3?"))

    messages = result["messages"]
    assert [type(m) for m in messages] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
    tool_message = messages[2]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.tool_call_id == "call-1"
    assert tool_message.text == "5"
    assert messages[-1].text == "It is 5."
    assert model.bound_tool_names == ["add"]
    assert model.calls == 2
    assert any(isinstance(m, ToolMessage) for m in model.inputs[1])
    assert result["step_count"] == 2


async def test_max_steps_guard_ends_with_explanatory_message() -> None:
    model = ScriptedChatModel(
        script=[tool_call("add", {"a": i, "b": 1}, f"call-{i}") for i in range(10)]
    )
    graph = build_graph(model, [add], max_steps=3)

    result = await graph.ainvoke(_input("loop forever"))

    assert model.calls == 3
    final = result["messages"][-1]
    assert isinstance(final, AIMessage)
    assert not final.tool_calls
    assert "maximum of 3" in final.text
    assert result["step_count"] == 3


async def test_max_steps_above_default_recursion_limit_does_not_raise() -> None:
    # 20 steps need ~41 supersteps, above LangGraph's default recursion limit of 25.
    model = ScriptedChatModel(
        script=[tool_call("add", {"a": i, "b": 1}, f"call-{i}") for i in range(20)]
    )
    graph = build_graph(model, [add], checkpointer=InMemorySaver(), max_steps=20)

    result = await graph.ainvoke(
        _input("loop forever"), {"configurable": {"thread_id": "long-run"}}
    )

    assert model.calls == 20
    assert "maximum of 20" in result["messages"][-1].text


def test_max_steps_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_steps"):
        build_graph(ScriptedChatModel(script=[]), [], max_steps=0)


async def test_retry_policy_retries_transient_failure_then_succeeds() -> None:
    model = ScriptedChatModel(
        script=[ConnectionError("network blip"), AIMessage(content="recovered")]
    )
    graph = build_graph(model, [], retry_policy=FAST_RETRY_POLICY)

    result = await graph.ainvoke(_input("hi"))

    assert result["messages"][-1].text == "recovered"
    assert model.calls == 2
    assert result["step_count"] == 1


async def test_retry_policy_gives_up_after_max_attempts() -> None:
    model = ScriptedChatModel(script=[ConnectionError(f"blip {i}") for i in range(5)])
    graph = build_graph(model, [], retry_policy=FAST_RETRY_POLICY)

    with pytest.raises(ConnectionError):
        await graph.ainvoke(_input("hi"))

    assert model.calls == 3


async def test_retry_policy_does_not_retry_permanent_failure() -> None:
    model = ScriptedChatModel(script=[ValueError("bad request"), AIMessage(content="never")])
    graph = build_graph(model, [], retry_policy=FAST_RETRY_POLICY)

    with pytest.raises(ValueError, match="bad request"):
        await graph.ainvoke(_input("hi"))

    assert model.calls == 1


def test_default_retry_policy_settings() -> None:
    assert DEFAULT_RETRY_POLICY.max_attempts == 3
    assert DEFAULT_RETRY_POLICY.backoff_factor > 1
    assert DEFAULT_RETRY_POLICY.retry_on is is_transient_error


class _StubRequest:
    """Stands in for the HTTP client's request; openai only stores it on the error."""


class _StubResponse:
    """Minimal response exposing what ``openai.APIStatusError`` reads."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.request = _StubRequest()
        self.headers: dict[str, str] = {}


_REQUEST = cast(Any, _StubRequest())


def _status_error(cls: type[openai.APIStatusError], status: int) -> openai.APIStatusError:
    return cls("error", response=cast(Any, _StubResponse(status)), body=None)


@pytest.mark.parametrize(
    "exc",
    [
        ConnectionError("reset"),
        TimeoutError("slow"),
        openai.APIConnectionError(request=_REQUEST),
        openai.APITimeoutError(request=_REQUEST),
        _status_error(openai.RateLimitError, 429),
        _status_error(openai.InternalServerError, 503),
    ],
    ids=lambda exc: type(exc).__name__,
)
def test_transient_errors_are_retried(exc: Exception) -> None:
    assert is_transient_error(exc)


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("bad"),
        KeyError("missing"),
        _status_error(openai.AuthenticationError, 401),
        _status_error(openai.BadRequestError, 400),
    ],
    ids=lambda exc: type(exc).__name__,
)
def test_permanent_errors_are_not_retried(exc: Exception) -> None:
    assert not is_transient_error(exc)


def test_route_after_reason() -> None:
    with_tools: AgentState = {"messages": [tool_call("add", {"a": 1, "b": 2}, "call-1")]}
    plain: AgentState = {"messages": [AIMessage(content="done")]}
    empty: AgentState = {"messages": []}

    assert route_after_reason(with_tools) == APPROVAL_NODE
    assert route_after_reason(plain) == END
    assert route_after_reason(empty) == END
