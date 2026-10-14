from datetime import UTC, datetime
from decimal import Decimal

import yaml

from brain_agent.brain.knowledge_graph import build_knowledge_graph
from brain_agent.brain.memory import MemoryRecord
from brain_agent.brain.rules import RuleSet
from brain_agent.integrations.crm import Contact, Deal
from brain_agent.integrations.tasks import Task
from tests.test_rules_tools import RULES

NOW = datetime(2026, 10, 14, tzinfo=UTC)


def _memory(id_: str, kind: str, text: str) -> MemoryRecord:
    return MemoryRecord(id_, kind, text, "t", NOW)  # type: ignore[arg-type]


def test_graph_links_memories_to_what_they_mention() -> None:
    raw = yaml.safe_load(RULES)
    ruleset = RuleSet.model_validate({"hard_rules": raw["hard_rules"]})
    graph = build_knowledge_graph(
        user_name="Ana",
        memories=[
            _memory("m1", "fact", "Ada Lovelace is the buyer at Globex"),
            _memory("m2", "preference", "Prefers morning meetings"),
        ],
        org_knowledge=[_memory("o1", "fact", "Invoices are paid on the 5th")],
        ruleset=ruleset,
        contacts=[
            Contact(
                id="c1",
                name="Ada Lovelace",
                email="ada@globex.com",
                company="Globex",
                created_at=NOW,
            )
        ],
        deals=[
            Deal(
                id="d1",
                contact_id="c1",
                title="Renewal",
                amount=Decimal("5000"),
                currency="EUR",
                stage="lead",
                updated_at=NOW,
            )
        ],
        tasks=[
            Task(
                id="t1",
                title="Call Ada Lovelace",
                description="",
                priority="high",
                status="open",
                created_at=NOW,
            )
        ],
    )
    ids = {n["id"] for n in graph["nodes"]}
    assert {
        "user",
        "kind:fact",
        "mem:m1",
        "org:o1",
        "rule:no-crm-deletion",
        "tool:crm_delete_record",
        "contact:c1",
        "company:globex",
        "deal:d1",
        "task:t1",
    } <= ids
    edges = {(e["source"], e["target"], e["kind"]) for e in graph["edges"]}
    assert ("mem:m1", "contact:c1", "mentions") in edges
    assert ("mem:m1", "company:globex", "mentions") in edges
    assert ("deal:d1", "contact:c1", "deal_of") in edges
    assert ("rule:no-crm-deletion", "tool:crm_delete_record", "governs") in edges
    assert not any(e[0] == "mem:m2" and e[2] == "mentions" for e in edges)
    assert ("tasks", "task:t1", "has") in edges and ("task:t1", "contact:c1", "mentions") in edges
    assert ("crm", "company:globex", "has") in edges
    # every edge points at an existing node
    assert all(e["source"] in ids and e["target"] in ids for e in graph["edges"])
