import asyncio
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolCall
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver

import brain_agent.graph  # noqa: F401  # load before brain_agent.tools (tools/graph import cycle)
from brain_agent.brain.rules import RulesEngine, YamlRuleSource
from brain_agent.graph.builder import build_graph
from brain_agent.hitl.policy import CompositeApprovalPolicy, MetadataApprovalPolicy
from brain_agent.persistence.users import InMemoryUserRepository
from brain_agent.tools.rules_tools import CHAT_RULES_FILE, RulesEditPolicy, build_rules_tools
from tests.fakes import ScriptedChatModel, tool_call

RULES = """\
version: 1
hard_rules:
  - id: no-crm-deletion
    description: No CRM deletion.
    when: { tool: crm_delete_record }
    action: block
    reason: Not allowed.
"""

HARD_RULE = {
    "kind": "hard_rule",
    "id": "no-task-deletion",
    "text": "Tasks are never deleted by the agent.",
    "tool": "delete_task",
    "action": "block",
}
GUIDELINE = {
    "kind": "guideline",
    "id": "short-answers",
    "text": "Answer in two lines.",
    "priority": 9,
}


async def _setup(
    tmp_path: Path,
) -> tuple[RulesEngine, InMemoryUserRepository, list[BaseTool]]:
    (tmp_path / "default.yaml").write_text(RULES)
    engine = RulesEngine.from_source(YamlRuleSource(tmp_path))
    users = InMemoryUserRepository()
    return engine, users, build_rules_tools(tmp_path, engine, users, asyncio.Lock())


async def test_add_rule_is_admin_only_appends_to_its_own_file_and_needs_approval(
    tmp_path: Path,
) -> None:
    engine, users, (read_rules, add_rule) = await _setup(tmp_path)
    admin = await users.create("a@acme.com", "x", "Admin")
    operator = await users.create("o@acme.com", "x", "Op")

    async def call(user_id: str, args: dict[str, Any]) -> str:
        return str(await add_rule.ainvoke(args, config={"configurable": {"user_id": user_id}}))

    assert "no-crm-deletion" in await read_rules.ainvoke({})
    assert "Only admins" in await call(operator.id, HARD_RULE)
    assert "Added rule no-task-deletion" in await call(admin.id, HARD_RULE)
    assert "Added rule short-answers" in await call(admin.id, GUIDELINE)
    assert "Invalid rule" in await call(admin.id, HARD_RULE)  # duplicate id

    assert (tmp_path / "default.yaml").read_text() == RULES  # existing files are never touched
    assert (tmp_path / CHAT_RULES_FILE).exists()
    assert {r.id for r in engine.ruleset.hard_rules} == {"no-crm-deletion", "no-task-deletion"}
    assert [g.id for g in engine.ruleset.guidelines] == ["short-answers"]

    call_ = ToolCall(name="add_rule", args={}, id="1")
    verdict = MetadataApprovalPolicy().evaluate(call_, add_rule)
    assert verdict is not None and verdict.risk == "high"


async def test_invalid_rules_are_refused_before_anyone_is_asked(tmp_path: Path) -> None:
    engine, _, tools = await _setup(tmp_path)
    duplicate = HARD_RULE | {"id": "no-crm-deletion"}
    model = ScriptedChatModel(
        script=[
            tool_call("add_rule", duplicate, "c1"),
            tool_call("add_rule", {"kind": "hard_rule", "id": "x1", "text": "No tool"}, "c2"),
            tool_call("add_rule", HARD_RULE, "c3"),
            AIMessage("done"),
        ]
    )
    graph = build_graph(
        model,
        tools,
        checkpointer=InMemorySaver(),
        approval_policy=CompositeApprovalPolicy(
            MetadataApprovalPolicy(), RulesEditPolicy(tmp_path, engine)
        ),
    )
    result = await graph.ainvoke(
        {"messages": [HumanMessage("add a rule")]}, {"configurable": {"thread_id": "t"}}
    )

    refusals = {m.tool_call_id: m.text for m in result["messages"] if m.type == "tool"}
    assert "Duplicate rule id" in refusals["c1"]
    assert "needs the tool" in refusals["c2"]
    [pending] = result["__interrupt__"]  # only the valid rule reaches the human
    assert pending.value["actions"][0]["action_id"] == "c3"
    assert not (tmp_path / CHAT_RULES_FILE).exists()
