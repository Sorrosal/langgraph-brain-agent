"""Tests for the rules-backed approval policy, the gate's blocking path, the prompt builder
and the shipped default rule set."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from brain_agent.brain.policy import RulesApprovalPolicy
from brain_agent.brain.prompt import build_system_prompt
from brain_agent.brain.rules import RulesEngine, YamlRuleSource, load_rules
from brain_agent.config import REPO_ROOT, Settings
from brain_agent.graph.builder import AgentGraph, build_graph
from brain_agent.hitl.policy import CompositeApprovalPolicy, PolicyVerdict
from tests.fakes import ScriptedChatModel

RULES = """
version: 1
persona: You are Testbot.
guidelines:
  - {id: b-low, text: Low priority B.}
  - {id: a-low, text: Low priority A.}
  - {id: top, text: Top priority., priority: 10}
hard_rules:
  - id: no-delete
    description: Deleting is forbidden.
    when: {tool: delete_thing}
    action: block
    reason: Deletes are never allowed.
  - id: ask-send
    description: Sending needs approval.
    when: {tool: send_thing}
    action: require_approval
    risk: medium
    reason: A human must look.
  - id: ask-big
    description: Big sends need approval.
    when: {tool: "send_*", args: {n: {gt: 100}}}
    action: require_approval
"""

CONFIG: Any = {"configurable": {"thread_id": "t"}}


def _call(name: str, args: dict[str, Any] | None = None, call_id: str = "c") -> Any:
    return {"name": name, "args": args or {}, "id": call_id, "type": "tool_call"}


def _engine(tmp_path: Path, content: str = RULES) -> RulesEngine:
    (tmp_path / "rules.yaml").write_text(content, encoding="utf-8")
    return RulesEngine(load_rules(tmp_path))


def _default_engine() -> RulesEngine:
    return RulesEngine(load_rules(REPO_ROOT / "rules"))


# --- policy -------------------------------------------------------------------------------


def test_rules_policy_verdicts(tmp_path: Path) -> None:
    policy = RulesApprovalPolicy(_engine(tmp_path))

    assert policy.evaluate(_call("lookup"), None) is None
    assert policy.evaluate(_call("delete_thing"), None) == PolicyVerdict(
        risk="high", reason="Deletes are never allowed.", blocked=True, rule_ids=("no-delete",)
    )
    assert policy.evaluate(_call("send_thing", {"n": 1}), None) == PolicyVerdict(
        risk="medium", reason="A human must look.", rule_ids=("ask-send",)
    )
    both = policy.evaluate(_call("send_thing", {"n": 500}), None)
    assert both is not None and not both.blocked
    assert both.rule_ids == ("ask-send", "ask-big")
    assert both.risk == "high"
    assert "A human must look." in both.reason and "Big sends need approval." in both.reason


def test_block_beats_require_approval(tmp_path: Path) -> None:
    content = RULES.replace("tool: delete_thing", "tool: send_thing")
    verdict = RulesApprovalPolicy(_engine(tmp_path, content)).evaluate(_call("send_thing"), None)
    assert verdict is not None and verdict.blocked
    assert verdict.rule_ids == ("no-delete",)


def test_composite_takes_the_strictest_verdict() -> None:
    soft = PolicyVerdict(risk="high", reason="soft")
    hard = PolicyVerdict(risk="low", reason="hard", blocked=True, rule_ids=("r",))
    mild = PolicyVerdict(risk="medium", reason="mild")

    class Fixed:
        def __init__(self, verdict: PolicyVerdict | None) -> None:
            self.verdict = verdict

        def evaluate(self, tool_call: Any, tool: BaseTool | None) -> PolicyVerdict | None:
            return self.verdict

    call = _call("x")
    assert CompositeApprovalPolicy(Fixed(soft), Fixed(hard)).evaluate(call, None) == hard
    assert CompositeApprovalPolicy(Fixed(hard), Fixed(soft)).evaluate(call, None) == hard
    assert CompositeApprovalPolicy(Fixed(None), Fixed(mild)).evaluate(call, None) == mild
    assert CompositeApprovalPolicy(Fixed(mild), Fixed(soft)).evaluate(call, None) == soft
    assert CompositeApprovalPolicy(Fixed(None), Fixed(None)).evaluate(call, None) is None


# --- graph --------------------------------------------------------------------------------


class Recorder:
    def __init__(self) -> None:
        self.runs: list[str] = []

        @tool
        def delete_thing(thing_id: str) -> str:
            """Delete a thing."""
            self.runs.append(f"delete:{thing_id}")
            return "deleted"

        @tool
        def send_thing(n: int) -> str:
            """Send things."""
            self.runs.append(f"send:{n}")
            return "sent"

        @tool
        def lookup(query: str) -> str:
            """Look something up."""
            self.runs.append(f"lookup:{query}")
            return "found"

        self.tools: list[BaseTool] = [delete_thing, send_thing, lookup]


def _graph(tmp_path: Path, recorder: Recorder, script: list[AIMessage]) -> AgentGraph:
    model = ScriptedChatModel(script=script)
    return build_graph(model, recorder.tools, checkpointer=InMemorySaver(), rules=_engine(tmp_path))


def _batch(*calls: dict[str, Any]) -> AIMessage:
    return AIMessage(content="", tool_calls=list(calls))


async def test_blocked_call_is_never_executed_nor_sent_for_approval(tmp_path: Path) -> None:
    recorder = Recorder()
    graph = _graph(
        tmp_path,
        recorder,
        [_batch(_call("delete_thing", {"thing_id": "1"}, "c1")), AIMessage(content="ok")],
    )

    result = await graph.ainvoke({"messages": [HumanMessage("delete it")]}, CONFIG)

    assert recorder.runs == []
    assert "__interrupt__" not in result
    [message] = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert message.status == "error"
    assert message.content == "Blocked by rule no-delete: Deletes are never allowed."
    assert result["approvals"] == [
        {
            "action_id": "c1",
            "tool_name": "delete_thing",
            "decision": "blocked",
            "rule_ids": ["no-delete"],
        }
    ]
    assert result["messages"][-1].content == "ok"


async def test_mixed_batch_blocked_approval_and_auto(tmp_path: Path) -> None:
    recorder = Recorder()
    graph = _graph(
        tmp_path,
        recorder,
        [
            _batch(
                _call("delete_thing", {"thing_id": "1"}, "blocked"),
                _call("send_thing", {"n": 1}, "ask"),
                _call("lookup", {"query": "q"}, "auto"),
            ),
            AIMessage(content="done"),
        ],
    )

    paused = await graph.ainvoke({"messages": [HumanMessage("go")]}, CONFIG)

    [interrupt] = paused["__interrupt__"]
    assert [a["action_id"] for a in interrupt.value["actions"]] == ["ask"]
    assert recorder.runs == []

    resume: Command[Any] = Command(resume={"decisions": {"ask": {"type": "approve"}}})
    final = await graph.ainvoke(resume, CONFIG)

    assert sorted(recorder.runs) == ["lookup:q", "send:1"]
    by_id = {m.tool_call_id: m for m in final["messages"] if isinstance(m, ToolMessage)}
    assert by_id["blocked"].status == "error"
    assert str(by_id["blocked"].content).startswith("Blocked by rule no-delete")
    assert by_id["ask"].content == "sent" and by_id["auto"].content == "found"
    decisions = {a["action_id"]: a["decision"] for a in final["approvals"]}
    assert decisions == {"blocked": "blocked", "ask": "approve"}


async def test_metadata_policy_still_applies_alongside_rules(tmp_path: Path) -> None:
    recorder = Recorder()
    recorder.tools[2].metadata = {"requires_approval": True}
    graph = _graph(tmp_path, recorder, [_batch(_call("lookup", {"query": "q"}, "c1"))])

    paused = await graph.ainvoke({"messages": [HumanMessage("go")]}, CONFIG)

    assert paused["__interrupt__"][0].value["actions"][0]["action_id"] == "c1"
    assert recorder.runs == []


async def test_reason_node_uses_rules_prompt_and_sees_reloads(tmp_path: Path) -> None:
    (tmp_path / "rules.yaml").write_text(RULES, encoding="utf-8")
    engine = RulesEngine.from_source(YamlRuleSource(tmp_path))
    model = ScriptedChatModel(script=[AIMessage(content="a"), AIMessage(content="b")])
    graph = build_graph(model, [], checkpointer=InMemorySaver(), rules=engine)

    await graph.ainvoke({"messages": [HumanMessage("hi")]}, CONFIG)
    (tmp_path / "rules.yaml").write_text(RULES.replace("Testbot", "Newbot!!"), encoding="utf-8")
    await graph.ainvoke({"messages": [HumanMessage("again")]}, CONFIG)

    first, second = (inputs[0] for inputs in model.inputs)
    assert isinstance(first, SystemMessage) and "Testbot" in str(first.content)
    assert isinstance(second, SystemMessage) and "Newbot!!" in str(second.content)


async def test_without_rules_behaviour_is_unchanged() -> None:
    model = ScriptedChatModel(script=[AIMessage(content="hello")])
    graph = build_graph(model, [], checkpointer=InMemorySaver())
    await graph.ainvoke({"messages": [HumanMessage("hi")]}, CONFIG)
    assert "Brain Agent" in str(model.inputs[0][0].content)


# --- prompt -------------------------------------------------------------------------------


def test_prompt_content_and_ordering(tmp_path: Path) -> None:
    prompt = build_system_prompt(
        _engine(tmp_path).ruleset,
        now=datetime(2026, 1, 2, 3, 4, tzinfo=UTC),
        extra_context="Memory: likes tea.",
    )

    assert prompt.startswith("You are Testbot.")
    assert prompt.index("Top priority.") < prompt.index("Low priority A.")
    assert prompt.index("Low priority A.") < prompt.index("Low priority B.")
    assert "Hard rules (enforced by the system)" in prompt
    assert "Deleting is forbidden." in prompt and "Sending needs approval." in prompt
    assert "2026-01-02T03:04:00+00:00" in prompt
    assert prompt.rstrip().endswith("Memory: likes tea.")


def test_prompt_is_deterministic_and_has_defaults(tmp_path: Path) -> None:
    ruleset = _engine(tmp_path).ruleset
    assert build_system_prompt(ruleset) == build_system_prompt(ruleset)

    empty = tmp_path / "empty"
    empty.mkdir()
    bare = build_system_prompt(load_rules(empty))
    assert "business operations" in bare
    assert "Hard rules" not in bare and "Guidelines" not in bare
    assert "Current date" not in bare


# --- default rule set ---------------------------------------------------------------------


def _verdict(name: str, args: dict[str, Any]) -> PolicyVerdict | None:
    return RulesApprovalPolicy(_default_engine()).evaluate(_call(name, args), None)


def test_default_rules_load_with_persona_and_guidelines() -> None:
    rules = _default_engine().ruleset
    assert rules.persona and 4 <= len(rules.guidelines) <= 6
    assert len(rules.hard_rules) >= 5


def test_default_rules_external_email_needs_approval() -> None:
    assert _verdict("send_email", {"to": ["x@acme.com"], "subject": "s"}) is None
    assert _verdict("send_email", {"to": "x@acme.com"}) is None
    external = _verdict("send_email", {"to": "x@gmail.com"})
    assert external is not None and not external.blocked
    assert external.rule_ids == ("external-email-needs-approval",)
    mixed = _verdict("send_email", {"to": ["x@acme.com", "y@gmail.com"]})
    assert mixed is not None and not mixed.blocked


def test_default_rules_bulk_email_needs_approval() -> None:
    few = [f"u{i}@acme.com" for i in range(5)]
    assert _verdict("send_email", {"to": few}) is None
    bulk = _verdict("send_email", {"to": [*few, "u5@acme.com"]})
    assert bulk is not None and bulk.rule_ids == ("bulk-email-needs-approval",)


def test_default_rules_crm_delete_is_blocked() -> None:
    verdict = _verdict("crm_delete_record", {"record_id": "1"})
    assert verdict is not None and verdict.blocked
    assert verdict.rule_ids == ("no-crm-deletion",)


def test_default_rules_large_deals_need_approval() -> None:
    assert _verdict("crm_update_deal", {"deal_id": "d", "amount": 10000}) is None
    big = _verdict("crm_update_deal", {"deal_id": "d", "amount": 20000})
    assert big is not None and not big.blocked
    assert big.rule_ids == ("large-deal-needs-approval",)


def test_default_rules_task_deletion_needs_approval_and_others_run_free() -> None:
    task = _verdict("delete_task", {"task_id": "t"})
    assert task is not None and not task.blocked
    assert _verdict("create_task", {"title": "x"}) is None
    assert _verdict("crm_create_contact", {"name": "x"}) is None


def test_composite_with_rules_blocks_even_when_metadata_allows(tmp_path: Path) -> None:
    from brain_agent.hitl.policy import MetadataApprovalPolicy

    policy = CompositeApprovalPolicy(
        MetadataApprovalPolicy(), RulesApprovalPolicy(_engine(tmp_path))
    )
    verdict = policy.evaluate(_call("delete_thing"), None)
    assert verdict is not None and verdict.blocked


def test_settings_rules_dir_defaults_to_repo_rules() -> None:
    assert Settings().rules_dir == REPO_ROOT / "rules"
