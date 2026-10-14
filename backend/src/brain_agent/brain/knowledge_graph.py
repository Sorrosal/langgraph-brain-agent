"""Everything the agent knows about a user, as a graph for the UI.

Nodes: the user, their memories grouped by kind, organisation knowledge, the rules (guidelines,
hard rules and the tools they govern) and the business data (companies, contacts, deals, tasks).
Edges connect each item to its hub, contacts to companies, deals to contacts, rules to tools and
memories to the contacts and companies they mention (whole-word, case-insensitive match).
"""

import re
from collections.abc import Sequence
from typing import Any

from brain_agent.brain.memory import MemoryRecord
from brain_agent.brain.rules import RuleSet
from brain_agent.integrations.crm import Contact, Deal
from brain_agent.integrations.tasks import Task

LABEL_LENGTH = 60
MIN_MENTION_LENGTH = 3

Node = dict[str, Any]
Edge = dict[str, str]


def _short(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= LABEL_LENGTH else f"{text[: LABEL_LENGTH - 1]}…"


def _company_id(name: str) -> str:
    return f"company:{' '.join(name.lower().split())}"


def _mentions(text: str, name: str) -> bool:
    if len(name.strip()) < MIN_MENTION_LENGTH:
        return False
    return re.search(rf"(?<!\w){re.escape(name.strip())}(?!\w)", text, re.IGNORECASE) is not None


def build_knowledge_graph(
    *,
    user_name: str,
    memories: Sequence[MemoryRecord],
    org_knowledge: Sequence[MemoryRecord],
    ruleset: RuleSet,
    contacts: Sequence[Contact],
    deals: Sequence[Deal],
    tasks: Sequence[Task],
    truncated: bool = False,
) -> dict[str, Any]:
    nodes: dict[str, Node] = {"user": {"id": "user", "type": "user", "label": user_name}}
    edges: list[Edge] = []

    def add(node: Node, parent: str | None = None, kind: str = "has") -> None:
        nodes.setdefault(node["id"], node)
        if parent is not None:
            edges.append({"source": parent, "target": node["id"], "kind": kind})

    for memory in memories:
        add({"id": f"kind:{memory.kind}", "type": "memory_kind", "label": memory.kind}, "user")
        add(
            {
                "id": f"mem:{memory.id}",
                "type": "memory",
                "label": _short(memory.text),
                "detail": memory.text,
                "group": memory.kind,
                "created_at": memory.created_at.isoformat(),
            },
            f"kind:{memory.kind}",
        )

    if org_knowledge:
        add({"id": "org", "type": "hub", "label": "organisation"}, "user")
    for fact in org_knowledge:
        add(
            {
                "id": f"org:{fact.id}",
                "type": "org",
                "label": _short(fact.text),
                "detail": fact.text,
                "created_at": fact.created_at.isoformat(),
            },
            "org",
        )

    if ruleset.guidelines or ruleset.hard_rules:
        add({"id": "rules", "type": "hub", "label": "rules"}, "user")
    for guideline in ruleset.guidelines:
        add(
            {
                "id": f"guideline:{guideline.id}",
                "type": "guideline",
                "label": guideline.id,
                "detail": guideline.text,
            },
            "rules",
        )
    for rule in ruleset.hard_rules:
        add(
            {
                "id": f"rule:{rule.id}",
                "type": "rule",
                "label": rule.id,
                "detail": rule.description,
                "group": rule.action,
            },
            "rules",
        )
        add({"id": f"tool:{rule.when.tool}", "type": "tool", "label": rule.when.tool})
        edges.append(
            {"source": f"rule:{rule.id}", "target": f"tool:{rule.when.tool}", "kind": "governs"}
        )

    if contacts or deals:
        add({"id": "crm", "type": "hub", "label": "crm"}, "user")
    for contact in contacts:
        add(
            {
                "id": f"contact:{contact.id}",
                "type": "contact",
                "label": contact.name,
                "detail": contact.email,
            },
            None if contact.company.strip() else "crm",
        )
        if contact.company.strip():
            add(
                {"id": _company_id(contact.company), "type": "company", "label": contact.company},
                "crm",
            )
            edges.append(
                {
                    "source": f"contact:{contact.id}",
                    "target": _company_id(contact.company),
                    "kind": "works_at",
                }
            )
    for deal in deals:
        add(
            {
                "id": f"deal:{deal.id}",
                "type": "deal",
                "label": _short(deal.title),
                "detail": f"{deal.amount} {deal.currency} · {deal.stage}",
                "group": deal.stage,
            }
        )
        if f"contact:{deal.contact_id}" in nodes:
            edges.append(
                {
                    "source": f"deal:{deal.id}",
                    "target": f"contact:{deal.contact_id}",
                    "kind": "deal_of",
                }
            )
    if tasks:
        add({"id": "tasks", "type": "hub", "label": "tasks"}, "user")
    for task in tasks:
        due = f"due {task.due_date.isoformat()} · " if task.due_date else ""
        add(
            {
                "id": f"task:{task.id}",
                "type": "task",
                "label": _short(task.title),
                "detail": f"{due}{task.priority}",
                "group": task.status,
            },
            "tasks",
        )

    sources = [(f"mem:{m.id}", m.text) for m in memories]
    sources += [(f"org:{m.id}", m.text) for m in org_knowledge]
    sources += [(f"task:{t.id}", f"{t.title} {t.description}") for t in tasks]
    for source, text in sources:
        for contact in contacts:
            if _mentions(text, contact.name):
                edges.append(
                    {"source": source, "target": f"contact:{contact.id}", "kind": "mentions"}
                )
        for company in {c.company for c in contacts if c.company.strip()}:
            if _mentions(text, company):
                edges.append({"source": source, "target": _company_id(company), "kind": "mentions"})

    return {"nodes": list(nodes.values()), "edges": edges, "truncated": truncated}
