import asyncio
from pathlib import Path

from langchain_core.messages import ToolCall

import brain_agent.graph  # noqa: F401  # load before brain_agent.tools (tools/graph import cycle)
from brain_agent.brain.rules import RulesEngine, YamlRuleSource
from brain_agent.hitl.policy import MetadataApprovalPolicy
from brain_agent.persistence.users import InMemoryUserRepository
from brain_agent.tools.rules_tools import build_rules_tools

RULES = """\
version: 1
hard_rules:
  - id: no-crm-deletion
    description: No CRM deletion.
    when: { tool: crm_delete_record }
    action: block
    reason: Not allowed.
"""

NEW_RULES = (
    RULES
    + """\
  - id: no-task-deletion
    description: No task deletion.
    when: { tool: delete_task }
    action: block
    reason: Not allowed either.
"""
)


async def test_update_rules_file_is_admin_only_validated_and_needs_approval(
    tmp_path: Path,
) -> None:
    (tmp_path / "default.yaml").write_text(RULES)
    engine = RulesEngine.from_source(YamlRuleSource(tmp_path))
    users = InMemoryUserRepository()
    admin = await users.create("a@acme.com", "x", "Admin")
    operator = await users.create("o@acme.com", "x", "Op")
    read_rules, update = build_rules_tools(tmp_path, engine, users, asyncio.Lock())

    def call(user_id: str, content: str) -> object:
        return update.ainvoke(
            {"filename": "default.yaml", "content": content},
            config={"configurable": {"user_id": user_id}},
        )

    assert "no-crm-deletion" in await read_rules.ainvoke({})
    assert "Only admins" in await call(operator.id, NEW_RULES)
    assert "Invalid rules" in await call(admin.id, "hard_rules: []\n")
    assert (tmp_path / "default.yaml").read_text() == RULES

    assert "Saved default.yaml" in await call(admin.id, NEW_RULES)
    assert [r.id for r in engine.ruleset.hard_rules] == ["no-crm-deletion", "no-task-deletion"]

    tool_call = ToolCall(name=update.name, args={}, id="1")
    verdict = MetadataApprovalPolicy().evaluate(tool_call, update)
    assert verdict is not None and verdict.risk == "high"
