"""Integration test: a pending approval survives a server restart (PostgreSQL)."""

import pytest
from langchain_core.messages import AIMessage

from brain_agent.graph.builder import build_graph
from brain_agent.hitl.models import ApprovalResponse
from brain_agent.persistence.postgres import Persistence, open_persistence
from brain_agent.runtime.recovery import RecoveryWorker
from brain_agent.runtime.runner import AgentRunner
from tests.fakes import ScriptedChatModel
from tests.test_hitl import REFUND_CALL, Tools

pytestmark = pytest.mark.integration

THREAD = "approval-thread"


def _runner(
    persistence: Persistence, script: list[AIMessage | Exception], tools: Tools
) -> AgentRunner:
    graph = build_graph(
        ScriptedChatModel(script=script),
        tools.all,
        checkpointer=persistence.checkpointer,
        store=persistence.store,
    )
    return AgentRunner(graph, runs=persistence.runs, lease_seconds=30)


async def test_pending_approval_survives_restart_and_is_not_recovered(
    persistence: Persistence, schema_url: str
) -> None:
    tools = Tools()
    first = _runner(persistence, [REFUND_CALL], tools)
    paused = await first.run(THREAD, "refund A1")
    assert paused.status == "interrupted" and paused.pending_approval is not None

    record = await persistence.runs.get(THREAD)
    assert record is not None
    assert (record.status, record.owner, record.lease_expires_at) == ("interrupted", None, None)
    assert await RecoveryWorker(first, persistence.runs).run_once() == []

    # A brand-new connection pool, graph and runner simulate a server restart.
    async with open_persistence(schema_url) as restarted:
        tools_after = Tools()
        second = _runner(restarted, [AIMessage(content="Refunded.")], tools_after)
        assert await second.get_pending_approval(THREAD) == paused.pending_approval
        assert await RecoveryWorker(second, restarted.runs).run_once() == []

        response = ApprovalResponse.model_validate({"decisions": {"call-1": {"type": "approve"}}})
        result = await second.approve(THREAD, response)

        assert (result.status, result.last_message) == ("completed", "Refunded.")
        assert tools_after.refunds == [{"order_id": "A1", "amount": 50}]
        assert tools.refunds == []
        finished = await restarted.runs.get(THREAD)
        assert finished is not None and finished.status == "completed"
