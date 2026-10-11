"""Memories, rules, read-only business data and the approval queue."""

import os
from decimal import Decimal
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from brain_agent.config import REPO_ROOT
from tests.api_support import make_settings, register, running_api
from tests.test_api_threads import APPROVE, EXTERNAL_EMAIL, new_thread, settled

DEFAULT_RULES = (REPO_ROOT / "rules" / "default.yaml").read_text(encoding="utf-8")


async def test_memories_are_private_to_their_owner() -> None:
    async with running_api([]) as h:
        ana = await register(h.client, "ana@acme.com")
        bob = await register(h.client, "bob@acme.com")
        created = await h.client.post(
            "/memories", json={"kind": "fact", "text": "  Prefers email  "}, headers=ana
        )
        assert created.status_code == 201
        memory = created.json()
        assert (memory["kind"], memory["text"]) == ("fact", "Prefers email")

        assert [m["id"] for m in (await h.client.get("/memories", headers=ana)).json()] == [
            memory["id"]
        ]
        assert (await h.client.get("/memories?kind=preference", headers=ana)).json() == []
        assert (await h.client.get("/memories", headers=bob)).json() == []
        found = await h.client.get("/memories/search?q=email", headers=ana)
        assert [m["id"] for m in found.json()] == [memory["id"]]
        assert (await h.client.get("/memories/search?q=email", headers=bob)).json() == []

        assert (await h.client.delete(f"/memories/{memory['id']}", headers=bob)).status_code == 404
        assert (await h.client.delete(f"/memories/{memory['id']}", headers=ana)).status_code == 204
        assert (await h.client.get("/memories", headers=ana)).json() == []
        for body in ({"kind": "nope", "text": "x"}, {"kind": "fact", "text": "   "}):
            assert (await h.client.post("/memories", json=body, headers=ana)).status_code == 422
        assert (await h.client.get("/memories")).status_code == 401


def rules_dir(tmp_path: Path) -> Path:
    (tmp_path / "default.yaml").write_text(DEFAULT_RULES, encoding="utf-8")
    return tmp_path


async def test_rules_are_readable_by_any_user_and_editable_by_admins_only(
    tmp_path: Path,
) -> None:
    async with running_api(
        [AIMessage(content="ok")], make_settings(rules_dir=rules_dir(tmp_path))
    ) as h:
        admin = await register(h.client, "ana@acme.com")
        operator = await register(h.client, "bob@acme.com")
        view = (await h.client.get("/rules", headers=operator)).json()
        assert view["persona"].startswith("You are Brain Agent")
        assert {g["id"] for g in view["guidelines"]} >= {"tone"}
        assert view["hard_rules"][0]["id"] == "external-email-needs-approval"
        assert view["files"] == [{"name": "default.yaml", "content": DEFAULT_RULES}]

        edited = DEFAULT_RULES.replace("Be concise and professional", "Be extremely terse")
        denied = await h.client.put(
            "/rules/default.yaml", json={"content": edited}, headers=operator
        )
        assert denied.status_code == 403
        assert (tmp_path / "default.yaml").read_text(encoding="utf-8") == DEFAULT_RULES

        saved = await h.client.put("/rules/default.yaml", json={"content": edited}, headers=admin)
        assert saved.status_code == 200
        assert saved.json()["version_hash"] != view["version_hash"]
        assert (await h.client.get("/rules", headers=operator)).json()["version_hash"] == (
            saved.json()["version_hash"]
        )
        assert os.listdir(tmp_path) == ["default.yaml"]  # no temp leftovers

        tid = await new_thread(h, admin)
        await h.client.post(f"/threads/{tid}/messages", json={"content": "hi"}, headers=admin)
        await settled(h.client, admin, tid)
        assert "Be extremely terse" in str(h.model.inputs[-1][0].content)

        extra = "version: 1\nguidelines:\n  - id: polite\n    text: Say please.\n"
        added = await h.client.put("/rules/extra.yaml", json={"content": extra}, headers=admin)
        assert added.status_code == 200 and (tmp_path / "extra.yaml").exists()


@pytest.mark.parametrize(
    "content",
    [
        "a: [unclosed",
        "version: 1\nhard_rules: nope\n",
        "version: 1\nguidelines:\n  - id: tone\n    text: duplicate of default.yaml\n",
    ],
)
async def test_invalid_rules_are_rejected_and_leave_files_untouched(
    tmp_path: Path, content: str
) -> None:
    async with running_api([], make_settings(rules_dir=rules_dir(tmp_path))) as h:
        admin = await register(h.client)
        before = (await h.client.get("/rules", headers=admin)).json()["version_hash"]
        rejected = await h.client.put("/rules/other.yaml", json={"content": content}, headers=admin)
        assert rejected.status_code == 422
        assert rejected.json()["error"]["code"] == "invalid_rules"
        assert os.listdir(tmp_path) == ["default.yaml"]
        assert (await h.client.get("/rules", headers=admin)).json()["version_hash"] == before


async def test_rules_cannot_be_emptied_or_written_outside_the_directory(tmp_path: Path) -> None:
    async with running_api([], make_settings(rules_dir=rules_dir(tmp_path))) as h:
        admin = await register(h.client)
        empty = await h.client.put("/rules/default.yaml", json={"content": ""}, headers=admin)
        no_rules = await h.client.put(
            "/rules/default.yaml", json={"content": "version: 1\n"}, headers=admin
        )
        assert (empty.status_code, no_rules.status_code) == (422, 422)
        for name in (
            "..%2Fevil.yaml",
            "%2E%2E%2F%2E%2E%2Fevil.yaml",
            "Evil.yaml",
            "a.yml",
            ".x.yaml",
        ):
            response = await h.client.put(
                f"/rules/{name}", json={"content": DEFAULT_RULES}, headers=admin
            )
            assert response.status_code in (404, 422), name
        assert sorted(p.name for p in tmp_path.parent.glob("*evil*")) == []
        assert (tmp_path / "default.yaml").read_text(encoding="utf-8") == DEFAULT_RULES


async def test_business_data_is_listed_read_only_with_filters() -> None:
    async with running_api([]) as h:
        headers = await register(h.client)
        crm, tasks = h.container.crm, h.container.tasks
        ana = await crm.create_contact(
            name="Ana",
            email="ana@acme.com",
            company="Acme",
            phone=None,
            tags=[],
            idempotency_key="1",
        )
        await crm.create_contact(
            name="Zed",
            email="zed@other.com",
            company="Other",
            phone=None,
            tags=[],
            idempotency_key="2",
        )
        await crm.create_deal(
            contact_id=ana.id,
            title="Big",
            amount=Decimal(5),
            currency="EUR",
            stage="won",
            idempotency_key="d1",
        )
        await crm.create_deal(
            contact_id=ana.id,
            title="Small",
            amount=Decimal(1),
            currency="EUR",
            stage="lead",
            idempotency_key="d2",
        )
        done = await tasks.create_task("Old", "", None, "low", None, idempotency_key="t1")
        await tasks.create_task("New", "", None, "high", None, idempotency_key="t2")
        await tasks.complete_task(done.id)
        await h.email.add_inbox_message(
            from_="x@y.com", to=["a@acme.com"], subject="Invoice", body_text="b"
        )
        await h.email.add_inbox_message(
            from_="x@y.com", to=["a@acme.com"], subject="Hello", body_text="b"
        )

        async def get(path: str) -> list[dict[str, object]]:
            response = await h.client.get(path, headers=headers)
            assert response.status_code == 200, response.text
            body: list[dict[str, object]] = response.json()
            return body

        assert [c["name"] for c in await get("/crm/contacts")] == ["Ana", "Zed"]
        assert [c["name"] for c in await get("/crm/contacts?q=other")] == ["Zed"]
        assert [d["title"] for d in await get("/crm/deals?stage=won")] == ["Big"]
        assert len(await get("/crm/deals")) == 2 and len(await get("/crm/deals?limit=1")) == 1
        assert [t["title"] for t in await get("/tasks?status=open")] == ["New"]
        assert [m["subject"] for m in await get("/emails?q=invoice")] == ["Invoice"]
        assert await get("/emails?folder=sent") == []

        for bad in ("/crm/contacts?limit=101", "/tasks?status=bogus", "/emails?folder=trash"):
            assert (await h.client.get(bad, headers=headers)).status_code == 422
        for path in ("/crm/contacts", "/crm/deals", "/tasks", "/emails"):
            assert (await h.client.get(path)).status_code == 401
            assert (await h.client.post(path, json={}, headers=headers)).status_code == 405


async def test_pending_approvals_list_only_my_paused_threads() -> None:
    async with running_api([EXTERNAL_EMAIL, AIMessage(content="Email sent.")]) as h:
        ana = await register(h.client, "ana@acme.com")
        bob = await register(h.client, "bob@acme.com")
        paused = await new_thread(h, ana)
        await new_thread(h, ana)  # idle: not listed
        await h.client.post(f"/threads/{paused}/messages", json={"content": "mail"}, headers=ana)
        await settled(h.client, ana, paused)

        pending = (await h.client.get("/approvals/pending", headers=ana)).json()
        assert [p["thread_id"] for p in pending] == [paused]
        assert pending[0]["interrupt"]["kind"] == "approval_required"
        assert pending[0]["interrupt"]["actions"][0]["action_id"] == "call-1"
        assert (await h.client.get("/approvals/pending", headers=bob)).json() == []

        await h.client.post(f"/threads/{paused}/approvals", json=APPROVE, headers=ana)
        await settled(h.client, ana, paused)
        assert (await h.client.get("/approvals/pending", headers=ana)).json() == []
