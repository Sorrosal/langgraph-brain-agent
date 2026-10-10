"""Tests for the agent runner: thread persistence and crash recovery via checkpoints."""

import asyncio
import os

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver

from brain_agent.errors import ConfigurationError, LeaseLostError, ThreadBusyError
from brain_agent.graph.builder import build_graph
from brain_agent.graph.nodes import TOOLS_NODE
from brain_agent.runtime.runner import AgentRunner, RunResult
from tests.fakes import FakeRunLedger, ScriptedChatModel, tool_call


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


async def test_run_refuses_a_thread_with_pending_work() -> None:
    checkpointer = InMemorySaver()

    @tool
    def lookup(query: str) -> str:
        """Look up a record."""
        raise SimulatedCrashError("process died mid-tool")

    model = ScriptedChatModel(script=[tool_call("lookup", {"query": "ACME"}, "call-1")])
    runner = AgentRunner(build_graph(model, [lookup], checkpointer=checkpointer))
    with pytest.raises(SimulatedCrashError):
        await runner.run("thread-1", "find ACME")

    with pytest.raises(ThreadBusyError, match="thread-1") as busy:
        await runner.run("thread-1", "another question")

    assert busy.value.thread_id == "thread-1"
    assert busy.value.next_nodes == (TOOLS_NODE,)
    assert model.calls == 1
    state = await runner.get_state("thread-1")
    assert [m.text for m in state.values["messages"] if m.type == "human"] == ["find ACME"]


def _ledger_runner(
    model: ScriptedChatModel,
    ledger: FakeRunLedger,
    tools: list[BaseTool] | None = None,
    checkpointer: InMemorySaver | None = None,
    **kwargs: float,
) -> AgentRunner:
    graph = build_graph(model, tools or [], checkpointer=checkpointer or InMemorySaver())
    return AgentRunner(graph, runs=ledger, owner_id="owner-1", **kwargs)


async def test_run_records_lifecycle_in_the_run_registry() -> None:
    ledger = FakeRunLedger()
    runner = _ledger_runner(ScriptedChatModel(script=[AIMessage(content="ok")]), ledger)

    await runner.run("thread-1", "hi")

    assert ledger.events == ["running:thread-1", "completed:thread-1"]
    assert ledger.records["thread-1"].status == "completed"


async def test_default_owner_id_identifies_host_and_process() -> None:
    graph = build_graph(ScriptedChatModel(script=[]), [], checkpointer=InMemorySaver())
    first, second = AgentRunner(graph), AgentRunner(graph)

    assert str(os.getpid()) in first.owner_id
    assert first.owner_id != second.owner_id


async def test_heartbeat_renews_the_lease_while_the_graph_runs() -> None:
    ledger = FakeRunLedger()

    @tool
    async def slow(query: str) -> str:
        """Take a while."""
        await asyncio.sleep(0.3)
        return query

    model = ScriptedChatModel(
        script=[tool_call("slow", {"query": "x"}, "call-1"), AIMessage(content="done")]
    )
    runner = _ledger_runner(model, ledger, [slow], lease_seconds=1.0, heartbeat_interval=0.03)

    await runner.run("thread-1", "go")

    assert ledger.heartbeats >= 3
    beats = ledger.heartbeats
    await asyncio.sleep(0.1)
    assert ledger.heartbeats == beats  # heartbeat stops once the run is over


async def test_transient_failure_keeps_run_recoverable() -> None:
    ledger = FakeRunLedger()

    @tool
    def flaky(query: str) -> str:
        """Fail like a network blip."""
        raise ConnectionError("db down")

    model = ScriptedChatModel(script=[tool_call("flaky", {"query": "x"}, "call-1")])
    runner = _ledger_runner(model, ledger, [flaky])

    with pytest.raises(ConnectionError):
        await runner.run("thread-1", "go")

    record = ledger.records["thread-1"]
    assert record.status == "running"
    assert record.last_error is not None
    assert "db down" in record.last_error


async def test_permanent_failure_marks_run_failed() -> None:
    ledger = FakeRunLedger()

    @tool
    def broken(query: str) -> str:
        """Fail permanently."""
        raise ValueError("bad input")

    model = ScriptedChatModel(script=[tool_call("broken", {"query": "x"}, "call-1")])
    runner = _ledger_runner(model, ledger, [broken])

    with pytest.raises(ValueError, match="bad input"):
        await runner.run("thread-1", "go")

    record = ledger.records["thread-1"]
    assert record.status == "failed"
    assert record.last_error is not None
    assert "bad input" in record.last_error


async def test_resume_keeps_attempt_count_and_completes_the_run() -> None:
    ledger = FakeRunLedger()
    checkpointer = InMemorySaver()
    calls = {"n": 0}

    @tool
    def lookup(query: str) -> str:
        """Fail once, then work."""
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("blip")
        return "found"

    first = ScriptedChatModel(script=[tool_call("lookup", {"query": "x"}, "call-1")])
    with pytest.raises(ConnectionError):
        await _ledger_runner(first, ledger, [lookup], checkpointer).run("thread-1", "go")
    ledger.expire("thread-1")
    assert await ledger.claim_orphans("owner-1", 30, 5) == ["thread-1"]

    second = ScriptedChatModel(script=[AIMessage(content="all done")])
    result = await _ledger_runner(second, ledger, [lookup], checkpointer).resume("thread-1")

    assert result.status == "completed"
    record = ledger.records["thread-1"]
    assert (record.status, record.attempts) == ("completed", 1)


async def test_resume_with_nothing_pending_closes_a_stale_running_row() -> None:
    ledger = FakeRunLedger()
    checkpointer = InMemorySaver()
    model = ScriptedChatModel(script=[AIMessage(content="done")])
    runner = _ledger_runner(model, ledger, checkpointer=checkpointer)
    await runner.run("thread-1", "hi")
    ledger.records["thread-1"].status = "running"  # crashed right before mark_finished

    await runner.resume("thread-1")

    assert ledger.records["thread-1"].status == "completed"
    assert model.calls == 1


def _assert_every_tool_call_answered(messages: list[BaseMessage]) -> None:
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    asked = {c["id"] for m in messages if isinstance(m, AIMessage) for c in m.tool_calls}
    assert asked <= answered


async def test_run_after_permanent_failure_closes_dangling_tool_call() -> None:
    ledger = FakeRunLedger()
    checkpointer = InMemorySaver()

    @tool
    def broken(query: str) -> str:
        """Fail permanently."""
        raise ValueError("bad input")

    first = ScriptedChatModel(script=[tool_call("broken", {"query": "x"}, "call-1")])
    with pytest.raises(ValueError, match="bad input"):
        await _ledger_runner(first, ledger, [broken], checkpointer).run("thread-1", "go")

    second = ScriptedChatModel(script=[AIMessage(content="sorry about that")])
    result = await _ledger_runner(second, ledger, [broken], checkpointer).run("thread-1", "again")

    assert result.status == "completed"
    assert result.last_message == "sorry about that"
    seen = second.inputs[0]
    _assert_every_tool_call_answered(seen)
    closing = next(m for m in seen if isinstance(m, ToolMessage))
    assert (closing.tool_call_id, closing.status) == ("call-1", "error")
    assert "bad input" in closing.text
    assert seen[-1].text == "again"
    assert ledger.records["thread-1"].status == "completed"


async def test_run_after_poisoned_run_closes_dangling_tool_call() -> None:
    ledger = FakeRunLedger()
    checkpointer = InMemorySaver()

    @tool
    def flaky(query: str) -> str:
        """Fail like a network blip."""
        raise ConnectionError("db down")

    first = ScriptedChatModel(script=[tool_call("flaky", {"query": "x"}, "call-1")])
    with pytest.raises(ConnectionError):
        await _ledger_runner(first, ledger, [flaky], checkpointer).run("thread-1", "go")
    ledger.expire("thread-1")
    assert await ledger.claim_orphans("owner-1", 30, 5, max_attempts=0) == []
    assert ledger.records["thread-1"].status == "failed"

    second = ScriptedChatModel(script=[AIMessage(content="recovered")])
    result = await _ledger_runner(second, ledger, [flaky], checkpointer).run("thread-1", "again")

    assert result.last_message == "recovered"
    _assert_every_tool_call_answered(second.inputs[0])


async def test_run_on_running_thread_with_pending_work_is_still_busy() -> None:
    ledger = FakeRunLedger()
    checkpointer = InMemorySaver()

    @tool
    def flaky(query: str) -> str:
        """Fail like a network blip."""
        raise ConnectionError("db down")

    model = ScriptedChatModel(script=[tool_call("flaky", {"query": "x"}, "call-1")])
    runner = _ledger_runner(model, ledger, [flaky], checkpointer)
    with pytest.raises(ConnectionError):
        await runner.run("thread-1", "go")

    with pytest.raises(ThreadBusyError):
        await runner.run("thread-1", "again")


async def test_lease_loss_stops_the_run_and_raises_without_finishing_it() -> None:
    ledger = FakeRunLedger()
    started = asyncio.Event()
    finished_tool = False

    @tool
    async def slow(query: str) -> str:
        """Take long enough to lose the lease."""
        nonlocal finished_tool
        started.set()
        await asyncio.sleep(30)
        finished_tool = True
        return query

    model = ScriptedChatModel(script=[tool_call("slow", {"query": "x"}, "call-1")])
    runner = _ledger_runner(model, ledger, [slow], lease_seconds=1.0, heartbeat_interval=0.02)
    task = asyncio.create_task(runner.run("thread-1", "go"))
    await asyncio.wait_for(started.wait(), timeout=5)
    # Another process takes over the run (e.g. after a long pause of this one).
    ledger.expire("thread-1")
    await ledger.mark_running("thread-1", "owner-2", 30)

    with pytest.raises(LeaseLostError) as lost:
        await asyncio.wait_for(task, timeout=5)

    assert lost.value.thread_id == "thread-1"
    assert not finished_tool
    record = ledger.records["thread-1"]
    assert (record.status, record.owner) == ("running", "owner-2")  # the new owner is untouched


async def test_a_stale_owner_cannot_finish_the_run_it_lost() -> None:
    ledger = FakeRunLedger()
    token = await ledger.mark_running("t", "old", 30)
    ledger.expire("t")
    await ledger.mark_running("t", "new", 30)

    assert await ledger.mark_finished("t", "old", token, "completed") is False
    assert await ledger.heartbeat("t", "old", token, 30) is False
    assert ledger.records["t"].status == "running"


async def test_fake_mark_running_refuses_a_live_foreign_lease() -> None:
    ledger = FakeRunLedger()
    first = await ledger.mark_running("t", "a", 30)

    with pytest.raises(ThreadBusyError):
        await ledger.mark_running("t", "b", 30)
    assert await ledger.mark_running("t", "a", 30) == first + 1  # own lease: re-entrant
    ledger.expire("t")
    assert await ledger.mark_running("t", "b", 30) == first + 2


async def test_run_on_a_thread_leased_to_another_owner_is_busy() -> None:
    ledger = FakeRunLedger()
    await ledger.mark_running("thread-1", "someone-else", 30)
    runner = _ledger_runner(ScriptedChatModel(script=[AIMessage(content="x")]), ledger)

    with pytest.raises(ThreadBusyError):
        await runner.run("thread-1", "hi")


@pytest.mark.parametrize(
    ("lease", "interval"), [(0, None), (-1, None), (10, 0), (10, -1), (10, 10), (10, 11)]
)
def test_runner_validates_lease_and_heartbeat(lease: float, interval: float | None) -> None:
    graph = build_graph(ScriptedChatModel(script=[]), [], checkpointer=InMemorySaver())

    with pytest.raises(ValueError, match=r"lease_seconds|heartbeat_interval"):
        AgentRunner(graph, lease_seconds=lease, heartbeat_interval=interval)
