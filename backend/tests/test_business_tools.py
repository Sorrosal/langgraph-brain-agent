"""Tests for the CRM and task tools: schemas, output, errors, idempotency key and rules."""

import json
from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver

from brain_agent.brain.rules import RulesEngine, load_rules
from brain_agent.config import REPO_ROOT
from brain_agent.graph.builder import build_graph
from brain_agent.hitl.models import ApprovalResponse
from brain_agent.integrations.memory import InMemoryCrmRepository, InMemoryTaskRepository
from brain_agent.integrations.tasks import Priority, Task
from brain_agent.runtime.runner import AgentRunner
from brain_agent.tools.crm_tools import build_crm_tools
from brain_agent.tools.idempotency import current_idempotency_key
from brain_agent.tools.registry import build_business_tools
from brain_agent.tools.task_tools import build_task_tools
from tests.fakes import InMemoryToolLedger, ScriptedChatModel, tool_call

THREAD = "biz-1"
EXPECTED = {
    "crm_search_contacts": ("low", True),
    "crm_get_contact": ("low", True),
    "crm_list_deals": ("low", True),
    "list_tasks": ("low", True),
    "crm_create_contact": ("medium", True),
    "crm_create_deal": ("medium", True),
    "crm_update_deal": ("medium", True),
    "create_task": ("medium", True),
    "complete_task": ("medium", True),
    "delete_task": ("high", True),
}


class KeyedTasks(InMemoryTaskRepository):
    """Records the idempotency key each create receives."""

    def __init__(self) -> None:
        super().__init__()
        self.keys: list[str] = []

    async def create_task(
        self,
        title: str,
        description: str,
        due_date: date | None,
        priority: Priority,
        assignee: str | None,
        *,
        idempotency_key: str,
    ) -> Task:
        self.keys.append(idempotency_key)
        return await super().create_task(
            title, description, due_date, priority, assignee, idempotency_key=idempotency_key
        )


def _by_name(tools: list[BaseTool]) -> dict[str, BaseTool]:
    return {t.name: t for t in tools}


async def _call(tools: dict[str, BaseTool], tool: str, /, **args: Any) -> Any:
    return json.loads(await tools[tool].ainvoke(args))


def test_registry_names_metadata_and_descriptions() -> None:
    tools = build_business_tools(InMemoryCrmRepository(), InMemoryTaskRepository())
    by_name = _by_name(tools)

    assert set(by_name) == {*EXPECTED, "remember", "recall"}
    for name, (risk, retry_safe) in EXPECTED.items():
        metadata = by_name[name].metadata or {}
        assert (metadata["risk"], metadata["retry_safe"]) == (risk, retry_safe), name
        assert len(by_name[name].description) > 30
    assert "remember" not in _by_name(
        build_business_tools(
            InMemoryCrmRepository(), InMemoryTaskRepository(), include_memory_tools=False
        )
    )
    extra = by_name["recall"]
    assert extra in build_business_tools(
        InMemoryCrmRepository(), InMemoryTaskRepository(), include_memory_tools=False, extra=[extra]
    )


def test_args_schemas_are_precise() -> None:
    by_name = _by_name(build_business_tools(InMemoryCrmRepository(), InMemoryTaskRepository()))

    deal = by_name["crm_update_deal"].args
    assert set(deal) == {"deal_id", "amount", "stage", "title"}
    assert by_name["crm_create_deal"].get_input_jsonschema()["required"] == [
        "contact_id",
        "title",
        "amount",
    ]
    assert by_name["create_task"].args["priority"]["enum"] == ["low", "normal", "high"]


async def test_crm_tools_return_compact_json_and_recoverable_errors() -> None:
    tools = _by_name(build_crm_tools(InMemoryCrmRepository()))

    contact = await _call(
        tools, "crm_create_contact", name="Ada", email="ada@x.io", company="X", tags=["vip"]
    )
    raw = await tools["crm_get_contact"].ainvoke({"contact_id": contact["id"]})
    assert " " not in raw and list(json.loads(raw)) == sorted(json.loads(raw))
    assert [c["id"] for c in await _call(tools, "crm_search_contacts", query="ADA")] == [
        contact["id"]
    ]

    deal = await _call(tools, "crm_create_deal", contact_id=contact["id"], title="T", amount=50)
    assert (deal["amount"], deal["stage"], deal["currency"]) == ("50.00", "lead", "USD")
    updated = await _call(tools, "crm_update_deal", deal_id=deal["id"], amount="20000")
    assert updated["amount"] == "20000.00"
    assert await _call(tools, "crm_list_deals", stage="lead") == [updated]

    message = await tools["crm_get_contact"].ainvoke(
        {"type": "tool_call", "name": "x", "id": "1", "args": {"contact_id": "nope"}}
    )
    assert isinstance(message, ToolMessage) and message.status == "error"
    assert "nope" in message.text
    empty = await tools["crm_update_deal"].ainvoke(
        {"type": "tool_call", "name": "x", "id": "2", "args": {"deal_id": deal["id"]}}
    )
    assert empty.status == "error" and "at least one" in empty.text
    bad = await tools["crm_create_deal"].ainvoke(
        {"type": "tool_call", "name": "x", "id": "3", "args": {"contact_id": "c", "title": "t"}}
    )
    assert bad.status == "error"


async def test_task_tools_roundtrip_and_direct_calls_get_a_fallback_key() -> None:
    repo = KeyedTasks()
    tools = _by_name(build_task_tools(repo))
    assert current_idempotency_key() is None

    task = await _call(tools, "create_task", title="Call", due_date="2026-12-01", priority="high")
    await _call(tools, "create_task", title="Call")

    assert len(set(repo.keys)) == 2 and all(repo.keys)  # distinct uuid fallbacks
    assert task["due_date"] == "2026-12-01" and task["status"] == "open"
    assert len(await _call(tools, "list_tasks", limit=1)) == 1
    assert (await _call(tools, "complete_task", task_id=task["id"]))["status"] == "done"
    assert [t["id"] for t in await _call(tools, "list_tasks", status="open")] != [task["id"]]
    assert await _call(tools, "delete_task", task_id=task["id"]) == {"deleted": True}


# --- graph with the shipped rules ---------------------------------------------------------


def _runner(
    crm: InMemoryCrmRepository, tasks: InMemoryTaskRepository, script: list[AIMessage]
) -> AgentRunner:
    graph = build_graph(
        ScriptedChatModel(script=script),
        build_business_tools(crm, tasks, include_memory_tools=False),
        checkpointer=InMemorySaver(),
        tool_ledger=InMemoryToolLedger(),
        rules=RulesEngine(load_rules(REPO_ROOT / "rules")),
    )
    return AgentRunner(graph)


async def _deal(crm: InMemoryCrmRepository) -> str:
    contact = await crm.create_contact(
        name="Ada", email="a@x.io", company="X", phone=None, tags=[], idempotency_key="c"
    )
    deal = await crm.create_deal(
        contact_id=contact.id,
        title="T",
        amount=Decimal(100),
        currency="USD",
        stage="lead",
        idempotency_key="d",
    )
    return deal.id


def _approve(action_id: str) -> ApprovalResponse:
    return ApprovalResponse.model_validate({"decisions": {action_id: {"type": "approve"}}})


async def test_create_task_runs_automatically_with_the_ledger_key() -> None:
    call = tool_call("create_task", {"title": "Call Ada"}, "c1")
    tasks = KeyedTasks()
    runner = _runner(InMemoryCrmRepository(), tasks, [call, AIMessage(content="Done.")])

    result = await runner.run(THREAD, "add a task")

    assert result.status == "completed" and result.last_message == "Done."
    assert tasks.keys == [f"{THREAD}:c1"]
    assert [t.title for t in await tasks.list_tasks(None, None, 10)] == ["Call Ada"]


async def test_crm_deletion_is_not_a_tool_and_still_blocked_by_the_rules() -> None:
    # Deletion is not offered to the model (the rules would always block it); a hallucinated
    # call is still refused by the hard rule before anything runs.
    assert "crm_delete_record" not in {
        t.name for t in build_business_tools(InMemoryCrmRepository(), InMemoryTaskRepository())
    }
    crm = InMemoryCrmRepository()
    deal_id = await _deal(crm)
    call = tool_call("crm_delete_record", {"kind": "deal", "id": deal_id}, "c1")
    runner = _runner(crm, InMemoryTaskRepository(), [call, AIMessage(content="Cannot.")])

    result = await runner.run(THREAD, "delete the deal")

    assert result.status == "completed"
    assert len(await crm.list_deals(None, None)) == 1
    messages = (await runner.get_state(THREAD)).values["messages"]
    [tool_message] = [m for m in messages if isinstance(m, ToolMessage)]
    assert tool_message.status == "error" and "no-crm-deletion" in tool_message.text


@pytest.mark.parametrize("amount", [20000, "20000", "20000.00"])
async def test_large_deal_update_waits_for_approval_then_executes(amount: Any) -> None:
    crm = InMemoryCrmRepository()
    deal_id = await _deal(crm)
    call = tool_call("crm_update_deal", {"deal_id": deal_id, "amount": amount}, "c1")
    runner = _runner(crm, InMemoryTaskRepository(), [call, AIMessage(content="Updated.")])

    paused = await runner.run(THREAD, "raise the deal")

    assert paused.status == "interrupted" and paused.pending_approval is not None
    [action] = paused.pending_approval.actions
    assert action.tool_name == "crm_update_deal"
    assert (await crm.list_deals(None, None))[0].amount == Decimal("100.00")

    done = await runner.approve(THREAD, _approve("c1"))

    assert done.status == "completed"
    assert (await crm.list_deals(None, None))[0].amount == Decimal("20000.00")


async def test_small_deal_update_and_task_deletion() -> None:
    crm, tasks = InMemoryCrmRepository(), InMemoryTaskRepository()
    deal_id = await _deal(crm)
    task = await tasks.create_task("t", "", None, "normal", None, idempotency_key="t")
    script = [
        tool_call("crm_update_deal", {"deal_id": deal_id, "amount": 9000}, "c1"),
        tool_call("delete_task", {"task_id": task.id}, "c2"),
        AIMessage(content="Finished."),
    ]
    runner = _runner(crm, tasks, script)

    paused = await runner.run(THREAD, "go")

    assert (await crm.list_deals(None, None))[0].amount == Decimal("9000.00")  # no approval
    assert paused.status == "interrupted" and paused.pending_approval is not None
    assert [a.tool_name for a in paused.pending_approval.actions] == ["delete_task"]
    assert len(await tasks.list_tasks(None, None, 10)) == 1

    done = await runner.approve(THREAD, _approve("c2"))

    assert done.status == "completed"
    assert await tasks.list_tasks(None, None, 10) == []


@pytest.mark.parametrize(
    ("amount", "message"),
    [
        ("1000000000000", "less than or equal"),
        ("1.005", "decimal places"),
        ("-1", "greater than or equal"),
    ],
)
async def test_deal_amounts_are_bounded_with_a_clear_message(amount: str, message: str) -> None:
    tools = _by_name(build_crm_tools(InMemoryCrmRepository()))

    for tool, args in (
        ("crm_create_deal", {"contact_id": "c", "title": "t", "amount": amount}),
        ("crm_update_deal", {"deal_id": "d", "amount": amount}),
    ):
        result = await tools[tool].ainvoke(
            {"type": "tool_call", "name": tool, "id": "1", "args": args}
        )
        assert result.status == "error" and "amount" in result.text and message in result.text, tool

    contact = await _call(tools, "crm_create_contact", name="Ada", email="a@x.io")
    biggest = await _call(
        tools, "crm_create_deal", contact_id=contact["id"], title="t", amount="999999999999.99"
    )
    assert biggest["amount"] == "999999999999.99"
