"""Conversation management, stopping runs, dismissing and expiring approvals, org knowledge."""

import asyncio
import contextlib
import logging
from datetime import timedelta
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from brain_agent.graph.builder import build_graph
from brain_agent.observability.logging import RedactTokens
from brain_agent.runtime.expiry import expire_stale_approvals
from brain_agent.runtime.runner import CANCELLED, AgentRunner
from tests.api_support import register, running_api
from tests.fakes import FakeRunLedger, ScriptedChatModel, tool_call
from tests.test_api_threads import EXTERNAL_EMAIL, new_thread, settled


async def test_rename_delete_and_ownership() -> None:
    async with running_api([]) as h:
        ana = await register(h.client, "ana@acme.com")
        bob = await register(h.client, "bob@acme.com")
        tid = await new_thread(h, ana)

        renamed = await h.client.patch(f"/threads/{tid}", json={"title": "  Q4 plan "}, headers=ana)
        assert (renamed.status_code, renamed.json()["title"]) == (200, "Q4 plan")
        assert (
            await h.client.patch(f"/threads/{tid}", json={"title": ""}, headers=ana)
        ).status_code == 422
        assert (
            await h.client.patch(f"/threads/{tid}", json={"title": "x"}, headers=bob)
        ).status_code == 404
        assert (await h.client.delete(f"/threads/{tid}", headers=bob)).status_code == 404

        assert (await h.client.delete(f"/threads/{tid}", headers=ana)).status_code == 204
        assert (await h.client.get(f"/threads/{tid}", headers=ana)).status_code == 404
        assert (await h.client.get("/threads", headers=ana)).json() == []


async def test_busy_threads_cannot_be_deleted_and_idle_ones_cannot_be_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with running_api([]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        assert (await h.client.post(f"/threads/{tid}/cancel", headers=headers)).status_code == 409

        release = asyncio.Event()

        async def slow(*args: object, **kwargs: object) -> None:
            await release.wait()

        monkeypatch.setattr(h.container.runner, "run", slow)
        await h.client.post(f"/threads/{tid}/messages", json={"content": "x"}, headers=headers)
        assert (await h.client.delete(f"/threads/{tid}", headers=headers)).status_code == 409

        cancelled = await h.client.post(f"/threads/{tid}/cancel", headers=headers)
        assert cancelled.status_code == 202
        await settled(h.client, headers, tid)
        assert (await h.client.delete(f"/threads/{tid}", headers=headers)).status_code == 204


async def test_a_cancelled_run_ends_failed_and_the_next_message_fixes_forward() -> None:
    started = asyncio.Event()

    @tool
    async def wait_forever() -> str:
        """Never finishes."""
        started.set()
        await asyncio.Event().wait()
        return "never"

    model = ScriptedChatModel(
        script=[tool_call("wait_forever", {}, "c1"), AIMessage("Next answer.")]
    )
    runs = FakeRunLedger()
    runner = AgentRunner(
        build_graph(model, [wait_forever], checkpointer=InMemorySaver()), runs=runs
    )
    events: list[tuple[str, dict[str, Any]]] = []

    def sink(type: str, data: dict[str, Any]) -> None:
        events.append((type, data))

    run = asyncio.create_task(runner.run("t", "go", sink=sink))
    await started.wait()
    runner.request_cancel("t")
    run.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await run

    record = await runs.get("t")
    assert record is not None and (record.status, record.last_error) == ("failed", CANCELLED)
    assert ("run_failed", {"code": "run_cancelled", "message": CANCELLED}) in events

    result = await runner.run("t", "never mind")
    assert (result.status, result.last_message) == ("completed", "Next answer.")


async def test_dismiss_rejects_the_pending_action_and_the_agent_carries_on() -> None:
    async with running_api([EXTERNAL_EMAIL, AIMessage("Understood, not sent.")]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        await h.client.post(f"/threads/{tid}/messages", json={"content": "mail"}, headers=headers)
        assert (await settled(h.client, headers, tid))["pending_interrupt"] is not None

        pending = (await h.client.get("/approvals/pending", headers=headers)).json()
        assert pending[0]["expires_at"] > pending[0]["updated_at"]

        assert (await h.client.post(f"/threads/{tid}/dismiss", headers=headers)).status_code == 202
        body = await settled(h.client, headers, tid)
        assert body["pending_interrupt"] is None
        assert body["messages"][-1]["content"] == "Understood, not sent."
        assert await h.email.search("", folder="sent", limit=10) == []
        assert (await h.client.post(f"/threads/{tid}/dismiss", headers=headers)).status_code == 409


async def test_stale_approvals_expire_in_the_background() -> None:
    async with running_api([EXTERNAL_EMAIL, AIMessage("It expired.")]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        await h.client.post(f"/threads/{tid}/messages", json={"content": "mail"}, headers=headers)
        assert (await settled(h.client, headers, tid))["pending_interrupt"] is not None

        c = h.container
        resumed = await expire_stale_approvals(
            runs=c.runs,
            threads=c.threads,
            runner=c.runner,
            supervisor=c.supervisor,
            ttl=timedelta(hours=1),
        )
        assert resumed == [tid]
        assert (await settled(h.client, headers, tid))["pending_interrupt"] is None


async def test_org_knowledge_is_shared_and_admin_managed() -> None:
    async with running_api([]) as h:
        admin = await register(h.client, "ana@acme.com")  # the first account is the admin
        operator = await register(h.client, "bob@acme.com")
        fact = {"text": "Invoices are paid on the 5th"}

        assert (
            await h.client.post("/org-knowledge", json=fact, headers=operator)
        ).status_code == 403
        added = await h.client.post("/org-knowledge", json=fact, headers=admin)
        assert added.status_code == 201
        listed = (await h.client.get("/org-knowledge", headers=operator)).json()
        assert [k["text"] for k in listed] == [fact["text"]]

        item = added.json()["id"]
        assert (
            await h.client.delete(f"/org-knowledge/{item}", headers=operator)
        ).status_code == 403
        assert (await h.client.delete(f"/org-knowledge/{item}", headers=admin)).status_code == 204
        assert (await h.client.delete(f"/org-knowledge/{item}", headers=admin)).status_code == 404


def test_access_tokens_never_reach_the_logs() -> None:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s"',
        ("127.0.0.1", "GET", "/threads/t/events?access_token=eyJ.secret.sig&after=3"),
        None,
    )
    assert RedactTokens().filter(record)
    assert "secret" not in record.getMessage()
    assert "access_token=[redacted]&after=3" in record.getMessage()
