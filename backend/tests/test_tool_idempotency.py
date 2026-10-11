"""Tests for exactly-once tool execution: wrapper decisions, human resolution and the key."""

from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt

from brain_agent.errors import InvalidApprovalError, NoPendingApprovalError
from brain_agent.graph.builder import build_graph
from brain_agent.hitl.models import ConfirmDone, Retry, Skip, UncertainExecutionInterrupt
from brain_agent.runtime.runner import AgentRunner, RunResult
from brain_agent.tools.idempotency import args_hash, current_idempotency_key
from tests.fakes import InMemoryToolLedger, ScriptedChatModel, tool_call

THREAD = "thread-1"
KEY = f"{THREAD}:call-1"
ARGS = {"to": "a@example.com"}
SEND = tool_call("send_email", ARGS, "call-1")


class Mailer:
    """Stands in for the external provider: counts side effects and sees the key."""

    def __init__(self, *, retry_safe: bool = False, fail_first: bool = False) -> None:
        self.sent: list[str] = []
        self.keys: list[str | None] = []
        self._fail_first = fail_first

        @tool
        def send_email(to: str) -> str:
            """Send an email."""
            self.keys.append(current_idempotency_key())
            if self._fail_first and not self.keys[1:]:
                raise ConnectionError("smtp down")
            self.sent.append(to)
            return f"sent to {to}"

        send_email.metadata = {"retry_safe": True} if retry_safe else {}
        self.tool: BaseTool = send_email


def _runner(
    mailer: Mailer, ledger: InMemoryToolLedger, script: list[AIMessage | Exception] | None = None
) -> AgentRunner:
    """A runner on a fresh checkpointer: running again re-executes the tools node."""
    model = ScriptedChatModel(script=script or [SEND, AIMessage(content="Sent.")])
    graph = build_graph(model, [mailer.tool], checkpointer=InMemorySaver(), tool_ledger=ledger)
    return AgentRunner(graph)


async def _tool_messages(runner: AgentRunner) -> list[ToolMessage]:
    values = (await runner.get_state(THREAD)).values
    return [m for m in values["messages"] if isinstance(m, ToolMessage)]


async def _seed(ledger: InMemoryToolLedger, *, status: str, args: dict[str, Any] = ARGS) -> None:
    await ledger.begin(KEY, THREAD, "send_email", args_hash(args))
    if status == "succeeded":
        await ledger.complete(KEY, {"content": "sent to stored", "status": "success"})
    elif status == "failed":
        await ledger.fail(KEY, "boom")


def _uncertain(result: RunResult) -> UncertainExecutionInterrupt:
    assert result.status == "interrupted"
    assert isinstance(result.pending_interrupt, UncertainExecutionInterrupt)
    assert result.pending_approval is None
    return result.pending_interrupt


async def test_first_execution_is_recorded_as_succeeded() -> None:
    mailer, ledger = Mailer(), InMemoryToolLedger()

    result = await _runner(mailer, ledger).run(THREAD, "mail")

    assert result.last_message == "Sent."
    record = await ledger.get(KEY)
    assert record is not None
    assert (record.status, record.attempts, record.tool_name) == ("succeeded", 1, "send_email")
    assert record.result == {"content": "sent to a@example.com", "status": "success"}
    assert record.args_hash == args_hash(ARGS)
    assert mailer.keys == [KEY]
    assert current_idempotency_key() is None  # scoped to the execution


async def test_replayed_tools_node_returns_stored_result_without_side_effect() -> None:
    mailer, ledger = Mailer(), InMemoryToolLedger()
    await _runner(mailer, ledger).run(THREAD, "mail")

    # A fresh checkpointer = the post-tools checkpoint was lost: the tools node runs again.
    replay = _runner(mailer, ledger)
    await replay.run(THREAD, "mail")

    assert mailer.sent == ["a@example.com"]
    [message] = await _tool_messages(replay)
    assert message.text == "sent to a@example.com"


async def test_failed_execution_is_retried_under_the_same_key() -> None:
    mailer, ledger = Mailer(fail_first=True), InMemoryToolLedger()
    first = _runner(mailer, ledger)
    with pytest.raises(ConnectionError):
        await first.run(THREAD, "mail")
    failed = await ledger.get(KEY)
    assert failed is not None and failed.status == "failed" and failed.error == "ConnectionError"

    await _runner(mailer, ledger).run(THREAD, "mail")

    record = await ledger.get(KEY)
    assert record is not None and (record.status, record.attempts) == ("succeeded", 2)
    assert mailer.sent == ["a@example.com"] and mailer.keys == [KEY, KEY]


async def test_started_and_retry_safe_is_re_executed_with_the_same_key() -> None:
    mailer, ledger = Mailer(retry_safe=True), InMemoryToolLedger()
    await _seed(ledger, status="started")

    result = await _runner(mailer, ledger).run(THREAD, "mail")

    assert result.status == "completed"
    assert mailer.sent == ["a@example.com"] and mailer.keys == [KEY]
    record = await ledger.get(KEY)
    assert record is not None and (record.status, record.attempts) == ("succeeded", 2)


async def test_started_without_retry_safe_escalates_to_a_human() -> None:
    mailer, ledger = Mailer(), InMemoryToolLedger()
    await _seed(ledger, status="started")

    result = await _runner(mailer, ledger).run(THREAD, "mail")

    pending = _uncertain(result)
    [action] = pending.actions
    assert (pending.kind, action.action_id, action.tool_name) == (
        "uncertain_execution",
        "call-1",
        "send_email",
    )
    assert action.args == ARGS and action.message
    assert mailer.sent == []


async def test_confirm_done_records_success_without_executing() -> None:
    mailer, ledger = Mailer(), InMemoryToolLedger()
    await _seed(ledger, status="started")
    runner = _runner(mailer, ledger)
    _uncertain(await runner.run(THREAD, "mail"))

    result = await runner.resolve_uncertain(THREAD, {"call-1": ConfirmDone()})

    assert (result.status, result.last_message) == ("completed", "Sent.")
    assert mailer.sent == []
    [message] = await _tool_messages(runner)
    assert (message.text, message.status) == ("Confirmed done by human", "success")
    record = await ledger.get(KEY)
    assert record is not None and record.status == "succeeded"


async def test_confirm_done_accepts_a_custom_message() -> None:
    mailer, ledger = Mailer(), InMemoryToolLedger()
    await _seed(ledger, status="started")
    runner = _runner(mailer, ledger)
    await runner.run(THREAD, "mail")

    await runner.resolve_uncertain(
        THREAD, {"call-1": ConfirmDone(message="Seen in the sent folder")}
    )

    [message] = await _tool_messages(runner)
    assert message.text == "Seen in the sent folder"


async def test_retry_executes_the_tool_once() -> None:
    mailer, ledger = Mailer(), InMemoryToolLedger()
    await _seed(ledger, status="started")
    runner = _runner(mailer, ledger)
    await runner.run(THREAD, "mail")

    result = await runner.resolve_uncertain(THREAD, {"call-1": Retry()})

    assert result.status == "completed"
    assert mailer.sent == ["a@example.com"] and mailer.keys == [KEY]
    record = await ledger.get(KEY)
    assert record is not None and record.status == "succeeded"


async def test_skip_answers_with_an_error_and_never_executes() -> None:
    mailer, ledger = Mailer(), InMemoryToolLedger()
    await _seed(ledger, status="started")
    runner = _runner(mailer, ledger)
    await runner.run(THREAD, "mail")

    result = await runner.resolve_uncertain(THREAD, {"call-1": Skip()})

    assert result.status == "completed"
    assert mailer.sent == []
    [message] = await _tool_messages(runner)
    assert (message.text, message.status) == ("Skipped by human", "error")
    record = await ledger.get(KEY)
    assert record is not None and (record.status, record.error) == ("failed", "Skipped by human")


async def test_args_hash_mismatch_is_treated_as_uncertain() -> None:
    mailer, ledger = Mailer(retry_safe=True), InMemoryToolLedger()
    await _seed(ledger, status="succeeded", args={"to": "someone-else@example.com"})

    result = await _runner(mailer, ledger).run(THREAD, "mail")

    assert "differ" in _uncertain(result).actions[0].message
    assert mailer.sent == []


async def test_resolve_uncertain_requires_a_pending_uncertain_execution() -> None:
    runner = _runner(Mailer(), InMemoryToolLedger(), [AIMessage(content="Hi.")])
    await runner.run(THREAD, "hello")

    with pytest.raises(NoPendingApprovalError):
        await runner.resolve_uncertain(THREAD, {"call-1": Retry()})


def _batch(*calls: tuple[str, str, dict[str, Any]]) -> AIMessage:
    tool_calls = [{"name": name, "args": args, "id": call_id} for call_id, name, args in calls]
    return AIMessage(content="", tool_calls=tool_calls)


async def _seed_batch(ledger: InMemoryToolLedger, *ids: str) -> None:
    for call_id in ids:
        await ledger.begin(f"{THREAD}:{call_id}", THREAD, "send_email", args_hash({"to": call_id}))


MAIL_AB = _batch(("a", "send_email", {"to": "a"}), ("b", "send_email", {"to": "b"}))
CONFIG: RunnableConfig = {"configurable": {"thread_id": THREAD}}


async def test_two_uncertain_calls_are_asked_once_and_answered_by_id() -> None:
    mailer, ledger = Mailer(), InMemoryToolLedger()
    await _seed_batch(ledger, "a", "b")
    runner = _runner(mailer, ledger, [MAIL_AB, AIMessage(content="Done.")])

    pending = _uncertain(await runner.run(THREAD, "mail"))
    with pytest.raises(InvalidApprovalError, match="missing"):
        await runner.resolve_uncertain(THREAD, {"b": Skip()})
    with pytest.raises(InvalidApprovalError, match="unknown"):
        await runner.resolve_uncertain(THREAD, {"a": Skip(), "b": Skip(), "z": Skip()})
    final = await runner.resolve_uncertain(THREAD, {"b": Skip(), "a": ConfirmDone()})

    assert [a.action_id for a in pending.actions] == ["a", "b"]
    assert final.status == "completed" and mailer.sent == []
    texts = {m.tool_call_id: m.text for m in await _tool_messages(runner)}
    assert texts == {"a": "Confirmed done by human", "b": "Skipped by human"}


class FailOnceLedger(InMemoryToolLedger):
    """Crashes the first retry authorisation: decisions are only partially applied."""

    armed = True

    async def authorize_retry(self, key: str, args_hash: str) -> None:
        if self.armed:
            self.armed = False
            raise RuntimeError("process died mid-decision")
        await super().authorize_retry(key, args_hash)


async def test_reexecuted_resolution_applies_remaining_decisions_by_id() -> None:
    mailer, ledger = Mailer(), FailOnceLedger()
    await _seed_batch(ledger, "a", "b")
    model = ScriptedChatModel(script=[MAIL_AB, AIMessage(content="Done.")])
    graph = build_graph(model, [mailer.tool], checkpointer=InMemorySaver(), tool_ledger=ledger)
    await graph.ainvoke({"messages": [HumanMessage("go")]}, CONFIG)

    # "a" is confirmed, then the node dies before "b" (Retry) is authorised.
    resume: Command[Any] = Command(
        resume={"decisions": {"a": {"type": "confirm_done"}, "b": {"type": "retry"}}}
    )
    with pytest.raises(RuntimeError, match="mid-decision"):
        await graph.ainvoke(resume, CONFIG)
    done = await graph.ainvoke(None, CONFIG)  # re-executes with the persisted answer

    assert mailer.sent == ["b"]  # "a" (ConfirmDone) is never retried; "b" runs once
    texts = {m.tool_call_id: m.text for m in done["messages"] if isinstance(m, ToolMessage)}
    assert texts == {"a": "Confirmed done by human", "b": "sent to b"}


async def test_a_tool_interrupt_in_the_batch_gets_its_own_resume_value() -> None:
    mailer, ledger = Mailer(), InMemoryToolLedger()

    @tool
    def ask(question: str) -> str:
        """Ask the user something."""
        return f"answer: {interrupt(question)}"

    await _seed_batch(ledger, "a")
    batch = _batch(("a", "send_email", {"to": "a"}), ("q", "ask", {"question": "ok?"}))
    model = ScriptedChatModel(script=[batch, AIMessage(content="Done.")])
    graph = build_graph(model, [mailer.tool, ask], checkpointer=InMemorySaver(), tool_ledger=ledger)

    first = await graph.ainvoke({"messages": [HumanMessage("go")]}, CONFIG)
    assert first["__interrupt__"][0].value["kind"] == "uncertain_execution"
    second = await graph.ainvoke(Command(resume={"decisions": {"a": {"type": "retry"}}}), CONFIG)
    assert second["__interrupt__"][0].value == "ok?"  # the tool's own question, not a decision
    last = await graph.ainvoke(Command(resume="yes"), CONFIG)

    texts = {m.tool_call_id: m.text for m in last["messages"] if isinstance(m, ToolMessage)}
    assert texts == {"a": "sent to a", "q": "answer: yes"}
    assert mailer.sent == ["a"]
