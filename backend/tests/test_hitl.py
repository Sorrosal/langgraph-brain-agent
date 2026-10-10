"""Tests for human-in-the-loop approvals: policy, models, graph gate and runner."""

from typing import Any

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver

from brain_agent.errors import InvalidApprovalError, NoPendingApprovalError, ThreadBusyError
from brain_agent.graph.builder import build_graph
from brain_agent.hitl.models import ActionRequest, ApprovalResponse
from brain_agent.hitl.policy import CompositeApprovalPolicy, MetadataApprovalPolicy, PolicyVerdict
from brain_agent.runtime.runner import AgentRunner
from tests.fakes import FakeRunLedger, ScriptedChatModel, tool_call

THREAD = "thread-1"


class Tools:
    """A high-risk and a low-risk tool that record every execution."""

    def __init__(self) -> None:
        self.refunds: list[dict[str, Any]] = []
        self.lookups: list[str] = []

        @tool
        def refund(order_id: str, amount: int) -> str:
            """Refund an order."""
            self.refunds.append({"order_id": order_id, "amount": amount})
            return f"refunded {amount} on {order_id}"

        @tool
        def lookup(query: str) -> str:
            """Look up a record."""
            self.lookups.append(query)
            return f"record for {query}"

        refund.metadata = {"risk": "high", "approval_reason": "Moves money"}
        self.all: list[BaseTool] = [refund, lookup]


REFUND_CALL = tool_call("refund", {"order_id": "A1", "amount": 50}, "call-1")
MIXED_BATCH = AIMessage(
    content="",
    tool_calls=[
        {"name": "lookup", "args": {"query": "A1"}, "id": "call-0"},
        {"name": "refund", "args": {"order_id": "A1", "amount": 50}, "id": "call-1"},
    ],
)


def _runner(
    script: list[AIMessage | Exception], tools: Tools, ledger: FakeRunLedger | None = None
) -> tuple[AgentRunner, ScriptedChatModel]:
    model = ScriptedChatModel(script=script)
    graph = build_graph(model, tools.all, checkpointer=InMemorySaver())
    return AgentRunner(graph, runs=ledger), model


def _decide(**decisions: dict[str, Any]) -> ApprovalResponse:
    return ApprovalResponse.model_validate({"decisions": decisions})


def _tool_messages(values: dict[str, Any]) -> list[ToolMessage]:
    return [m for m in values["messages"] if isinstance(m, ToolMessage)]


def _call(name: str) -> Any:
    return {"name": name, "args": {}, "id": "c", "type": "tool_call"}


# --- policy -------------------------------------------------------------------------------


def test_policy_requires_approval_for_high_risk_or_flagged_tools() -> None:
    tools = {t.name: t for t in Tools().all}
    policy = MetadataApprovalPolicy()

    assert policy.evaluate(_call("refund"), tools["refund"]) == PolicyVerdict(
        risk="high", reason="Moves money"
    )

    tools["lookup"].metadata = {"requires_approval": True}
    flagged = policy.evaluate(_call("lookup"), tools["lookup"])
    assert flagged is not None and flagged.risk == "medium" and flagged.reason

    tools["lookup"].metadata = {"risk": "low"}
    assert policy.evaluate(_call("lookup"), tools["lookup"]) is None
    assert policy.evaluate(_call("ghost"), None) is None


def test_composite_policy_first_verdict_wins() -> None:
    verdict = PolicyVerdict(risk="medium", reason="rule")

    class Always:
        def evaluate(self, tool_call: Any, tool: BaseTool | None) -> PolicyVerdict | None:
            return verdict

    lookup = Tools().all[1]
    both = CompositeApprovalPolicy(MetadataApprovalPolicy(), Always())
    assert both.evaluate(_call("lookup"), lookup) == verdict
    assert CompositeApprovalPolicy(MetadataApprovalPolicy()).evaluate(_call("x"), lookup) is None


def test_response_validation_requires_exactly_the_pending_actions() -> None:
    actions = [ActionRequest(action_id="a", tool_name="t", args={}, risk="high", reason="r")]

    _decide(a={"type": "approve"}).ensure_covers(actions)
    with pytest.raises(InvalidApprovalError, match="missing"):
        _decide().ensure_covers(actions)
    with pytest.raises(InvalidApprovalError, match="unknown"):
        _decide(a={"type": "approve"}, zzz={"type": "approve"}).ensure_covers(actions)


# --- graph + runner -----------------------------------------------------------------------


async def test_high_risk_call_pauses_with_pending_approval() -> None:
    tools = Tools()
    ledger = FakeRunLedger()
    runner, _ = _runner([REFUND_CALL], tools, ledger)

    result = await runner.run(THREAD, "refund A1")

    assert result.status == "interrupted"
    assert result.pending_approval is not None
    [action] = result.pending_approval.actions
    assert (action.action_id, action.tool_name, action.risk) == ("call-1", "refund", "high")
    assert action.args == {"order_id": "A1", "amount": 50}
    assert action.reason == "Moves money"
    assert tools.refunds == []
    assert await runner.get_pending_approval(THREAD) == result.pending_approval
    # Paused: the registry row is interrupted and holds no lease.
    record = ledger.records[THREAD]
    assert (record.status, record.owner) == ("interrupted", None)


async def test_approve_executes_tool_once_and_completes() -> None:
    tools = Tools()
    runner, model = _runner([REFUND_CALL, AIMessage(content="Refunded.")], tools)
    await runner.run(THREAD, "refund A1")

    result = await runner.approve(THREAD, _decide(**{"call-1": {"type": "approve"}}))

    assert (result.status, result.last_message, result.pending_approval) == (
        "completed",
        "Refunded.",
        None,
    )
    assert tools.refunds == [{"order_id": "A1", "amount": 50}]
    assert model.calls == 2  # the resume does not replay the reasoning step
    state = (await runner.get_state(THREAD)).values
    assert state["approvals"] == [
        {"action_id": "call-1", "tool_name": "refund", "decision": "approve"}
    ]


async def test_edit_executes_tool_with_edited_args() -> None:
    tools = Tools()
    runner, _ = _runner([REFUND_CALL, AIMessage(content="Done.")], tools)
    await runner.run(THREAD, "refund A1")

    await runner.approve(
        THREAD, _decide(**{"call-1": {"type": "edit", "args": {"order_id": "A1", "amount": 5}}})
    )

    assert tools.refunds == [{"order_id": "A1", "amount": 5}]
    state = (await runner.get_state(THREAD)).values
    ai = [m for m in state["messages"] if isinstance(m, AIMessage)]
    assert len(ai) == 2  # the edited call replaced the original message, not appended
    assert ai[0].tool_calls[0]["args"]["amount"] == 5
    assert state["approvals"][0]["decision"] == "edit"


async def test_reject_skips_tool_and_lets_model_answer() -> None:
    tools = Tools()
    runner, model = _runner([REFUND_CALL, AIMessage(content="Understood, no refund.")], tools)
    await runner.run(THREAD, "refund A1")

    result = await runner.approve(
        THREAD, _decide(**{"call-1": {"type": "reject", "reason": "too large"}})
    )

    assert (result.status, result.last_message) == ("completed", "Understood, no refund.")
    assert tools.refunds == []
    [message] = _tool_messages((await runner.get_state(THREAD)).values)
    assert message.status == "error"
    assert message.text == "Rejected by human reviewer: too large"
    assert model.calls == 2


async def test_respond_returns_human_message_without_running_tool() -> None:
    tools = Tools()
    runner, _ = _runner([REFUND_CALL, AIMessage(content="Ok.")], tools)
    await runner.run(THREAD, "refund A1")

    await runner.approve(
        THREAD, _decide(**{"call-1": {"type": "respond", "message": "Use store credit."}})
    )

    assert tools.refunds == []
    [message] = _tool_messages((await runner.get_state(THREAD)).values)
    assert (message.text, message.status) == ("Use store credit.", "success")


async def test_mixed_batch_waits_for_approval_as_a_whole() -> None:
    tools = Tools()
    runner, _ = _runner([MIXED_BATCH, AIMessage(content="Done.")], tools)

    paused = await runner.run(THREAD, "look up and refund")

    assert paused.pending_approval is not None
    assert [a.action_id for a in paused.pending_approval.actions] == ["call-1"]
    assert tools.lookups == [] and tools.refunds == []  # the whole batch waits

    await runner.approve(THREAD, _decide(**{"call-1": {"type": "approve"}}))

    assert tools.lookups == ["A1"]
    assert tools.refunds == [{"order_id": "A1", "amount": 50}]
    assert len(_tool_messages((await runner.get_state(THREAD)).values)) == 2


async def test_mixed_batch_with_reject_still_runs_the_other_call_once() -> None:
    tools = Tools()
    runner, _ = _runner([MIXED_BATCH, AIMessage(content="Done.")], tools)
    await runner.run(THREAD, "go")

    await runner.approve(THREAD, _decide(**{"call-1": {"type": "reject"}}))

    assert tools.lookups == ["A1"] and tools.refunds == []
    assert len(_tool_messages((await runner.get_state(THREAD)).values)) == 2


async def test_invalid_response_raises_and_thread_stays_interrupted() -> None:
    tools = Tools()
    runner, _ = _runner([REFUND_CALL, AIMessage(content="Done.")], tools)
    await runner.run(THREAD, "refund A1")

    with pytest.raises(InvalidApprovalError):
        await runner.approve(THREAD, _decide())
    with pytest.raises(InvalidApprovalError):
        await runner.approve(
            THREAD, _decide(**{"call-1": {"type": "approve"}, "bogus": {"type": "approve"}})
        )

    pending = await runner.get_pending_approval(THREAD)
    assert pending is not None and pending.actions[0].action_id == "call-1"
    assert tools.refunds == []


async def test_approve_without_pending_approval_raises() -> None:
    runner, _ = _runner([AIMessage(content="Hi.")], Tools())
    await runner.run(THREAD, "hello")

    with pytest.raises(NoPendingApprovalError):
        await runner.approve(THREAD, _decide(x={"type": "approve"}))
    with pytest.raises(NoPendingApprovalError):
        await runner.approve("unknown-thread", _decide())


async def test_run_while_interrupted_is_busy_and_resume_is_a_no_op() -> None:
    tools = Tools()
    ledger = FakeRunLedger()
    runner, model = _runner([REFUND_CALL], tools, ledger)
    paused = await runner.run(THREAD, "refund A1")

    with pytest.raises(ThreadBusyError, match="approval pending"):
        await runner.run(THREAD, "another message")

    assert await runner.resume(THREAD) == paused
    assert model.calls == 1 and tools.refunds == []
    assert ledger.records[THREAD].status == "interrupted"
