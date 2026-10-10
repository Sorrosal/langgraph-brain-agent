"""Tests for the agent runner: thread persistence and crash recovery via checkpoints."""

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver

from brain_agent.errors import ConfigurationError
from brain_agent.graph.builder import build_graph
from brain_agent.graph.nodes import TOOLS_NODE
from brain_agent.runtime.runner import AgentRunner, RunResult
from tests.fakes import ScriptedChatModel, tool_call


class SimulatedCrashError(Exception):
    """Stands in for the process dying while a tool is running."""


def _runner(model: ScriptedChatModel, checkpointer: InMemorySaver) -> AgentRunner:
    return AgentRunner(build_graph(model, [], checkpointer=checkpointer))


async def test_run_returns_completed_result_with_last_message() -> None:
    model = ScriptedChatModel(script=[AIMessage(content="Hi there.")])
    runner = _runner(model, InMemorySaver())

    result = await runner.run("thread-1", "hello")

    assert result == RunResult(
        thread_id="thread-1", status="completed", last_message="Hi there.", next_nodes=()
    )


async def test_state_persists_across_runs_on_the_same_thread() -> None:
    model = ScriptedChatModel(
        script=[AIMessage(content="Nice to meet you."), AIMessage(content="You are Ada.")]
    )
    runner = _runner(model, InMemorySaver())

    await runner.run("thread-1", "My name is Ada.")
    result = await runner.run("thread-1", "What is my name?")

    assert result.last_message == "You are Ada."
    second_call = [m.text for m in model.inputs[1] if m.type != "system"]
    assert second_call == [
        "My name is Ada.",
        "Nice to meet you.",
        "What is my name?",
    ]
    snapshot = await runner.get_state("thread-1")
    assert len(snapshot.values["messages"]) == 4


async def test_threads_are_isolated() -> None:
    model = ScriptedChatModel(script=[AIMessage(content="one"), AIMessage(content="two")])
    runner = _runner(model, InMemorySaver())

    await runner.run("thread-a", "first")
    await runner.run("thread-b", "second")

    assert [m.text for m in model.inputs[1] if m.type != "system"] == ["second"]


async def test_step_budget_resets_for_each_new_message() -> None:
    model = ScriptedChatModel(
        script=[
            tool_call("echo", {"text": "a"}, "call-1"),
            AIMessage(content="first answer"),
            AIMessage(content="second answer"),
        ]
    )

    @tool
    def echo(text: str) -> str:
        """Echo the text back."""
        return text

    runner = AgentRunner(build_graph(model, [echo], checkpointer=InMemorySaver(), max_steps=2))

    first = await runner.run("thread-1", "use a tool")
    second = await runner.run("thread-1", "answer directly")

    assert first.last_message == "first answer"
    assert second.last_message == "second answer"
    assert model.calls == 3


async def test_resume_after_crash_continues_from_last_checkpoint() -> None:
    checkpointer = InMemorySaver()
    attempts = {"lookup": 0}
    checkpointed_before_crash: list[BaseMessage] = []

    @tool
    def lookup(query: str) -> str:
        """Look up a record."""
        attempts["lookup"] += 1
        if attempts["lookup"] == 1:
            # A hard kill only keeps what was persisted before the tool started running.
            saved = checkpointer.get_tuple({"configurable": {"thread_id": "thread-1"}})
            assert saved is not None
            checkpointed_before_crash.extend(saved.checkpoint["channel_values"]["messages"])
            raise SimulatedCrashError("process died mid-tool")
        return f"record for {query}"

    tools: list[BaseTool] = [lookup]
    model_before_crash = ScriptedChatModel(
        script=[tool_call("lookup", {"query": "ACME"}, "call-1")]
    )
    crashed_runner = AgentRunner(build_graph(model_before_crash, tools, checkpointer=checkpointer))

    with pytest.raises(SimulatedCrashError):
        await crashed_runner.run("thread-1", "find ACME")

    last_saved = checkpointed_before_crash[-1]
    assert isinstance(last_saved, AIMessage)
    assert last_saved.tool_calls[0]["id"] == "call-1"

    # A fresh runner over the same durable checkpointer simulates a restarted process.
    model_after_restart = ScriptedChatModel(script=[AIMessage(content="ACME found.")])
    restarted_runner = AgentRunner(
        build_graph(model_after_restart, tools, checkpointer=checkpointer)
    )
    pending = await restarted_runner.get_state("thread-1")
    assert pending.next == (TOOLS_NODE,)

    result = await restarted_runner.resume("thread-1")

    assert result == RunResult(
        thread_id="thread-1", status="completed", last_message="ACME found.", next_nodes=()
    )
    # The checkpointed reasoning step is not replayed: one model call before, one after.
    assert model_before_crash.calls == 1
    assert model_after_restart.calls == 1
    assert attempts["lookup"] == 2
    messages = (await restarted_runner.get_state("thread-1")).values["messages"]
    assert [type(m) for m in messages] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
    assert messages[2].text == "record for ACME"


async def test_resume_on_finished_thread_is_a_no_op() -> None:
    model = ScriptedChatModel(script=[AIMessage(content="done")])
    runner = _runner(model, InMemorySaver())
    await runner.run("thread-1", "hi")

    result = await runner.resume("thread-1")

    assert result.status == "completed"
    assert result.last_message == "done"
    assert model.calls == 1


async def test_resume_unknown_thread_returns_empty_result() -> None:
    model = ScriptedChatModel(script=[])
    runner = _runner(model, InMemorySaver())

    result = await runner.resume("missing")

    assert result == RunResult(
        thread_id="missing", status="completed", last_message=None, next_nodes=()
    )
    assert model.calls == 0


def test_runner_requires_a_checkpointer() -> None:
    graph = build_graph(ScriptedChatModel(script=[]), [])

    with pytest.raises(ConfigurationError, match="checkpointer"):
        AgentRunner(graph)


async def test_run_rejects_blank_thread_id() -> None:
    runner = _runner(ScriptedChatModel(script=[]), InMemorySaver())

    with pytest.raises(ValueError, match="thread_id"):
        await runner.run("  ", "hi")
