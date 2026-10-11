"""Thread and run endpoints."""

import asyncio
from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessage

from brain_agent.errors import ThreadBusyError
from brain_agent.runtime.supervisor import RunSupervisor
from tests.api_support import Harness, register, running_api
from tests.fakes import tool_call

EXTERNAL_EMAIL = tool_call(
    "send_email", {"to": ["bob@gmail.com"], "subject": "Hi", "body": "Hello"}, "call-1"
)
APPROVE = {"decisions": {"call-1": {"type": "approve"}}}


async def settled(client: httpx.AsyncClient, headers: dict[str, str], thread_id: str) -> Any:
    for _ in range(200):
        body = (await client.get(f"/threads/{thread_id}", headers=headers)).json()
        if body["run"]["status"] != "running":
            return body
        await asyncio.sleep(0.02)
    raise AssertionError("run did not settle")


async def new_thread(h: Harness, headers: dict[str, str]) -> str:
    response = await h.client.post("/threads", json={}, headers=headers)
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_thread_crud_pagination_and_ownership() -> None:
    async with running_api([]) as h:
        ana = await register(h.client, "ana@acme.com")
        bob = await register(h.client, "bob@acme.com")
        created = [
            (await h.client.post("/threads", json={"title": f"t{i}"}, headers=ana)).json()
            for i in range(3)
        ]
        listing = await h.client.get("/threads?limit=2", headers=ana)
        assert [t["title"] for t in listing.json()] == ["t2", "t1"]
        rest = await h.client.get("/threads?limit=2&offset=2", headers=ana)
        assert [t["title"] for t in rest.json()] == ["t0"]
        assert (await h.client.get("/threads", headers=bob)).json() == []

        tid = created[0]["id"]
        for response in (
            await h.client.get(f"/threads/{tid}", headers=bob),
            await h.client.post(f"/threads/{tid}/messages", json={"content": "x"}, headers=bob),
            await h.client.post(f"/threads/{tid}/approvals", json=APPROVE, headers=bob),
            await h.client.get("/threads/unknown", headers=ana),
        ):
            assert response.status_code == 404
        assert (await h.client.get("/threads")).status_code == 401


async def test_message_runs_in_background_and_reply_is_visible() -> None:
    async with running_api([AIMessage(content="Hello Ana!")]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)

        accepted = await h.client.post(
            f"/threads/{tid}/messages", json={"content": "Say hello please"}, headers=headers
        )
        assert accepted.status_code == 202
        assert accepted.json()["run"]["status"] == "running"

        state = await settled(h.client, headers, tid)
        assert state["run"]["status"] == "idle"
        assert state["title"] == "Say hello please"
        assert [(m["role"], m["content"]) for m in state["messages"]] == [
            ("human", "Say hello please"),
            ("ai", "Hello Ana!"),
        ]
        assert state["pending_interrupt"] is None


async def test_message_content_is_validated() -> None:
    async with running_api([]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        for content in ("", "x" * 8001):
            response = await h.client.post(
                f"/threads/{tid}/messages", json={"content": content}, headers=headers
            )
            assert response.status_code == 422


async def test_external_email_waits_for_approval_then_sends_once() -> None:
    async with running_api([EXTERNAL_EMAIL, AIMessage(content="Email sent.")]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        await h.client.post(
            f"/threads/{tid}/messages", json={"content": "Email bob"}, headers=headers
        )

        paused = await settled(h.client, headers, tid)
        assert paused["run"]["status"] == "interrupted"
        assert paused["pending_interrupt"]["kind"] == "approval_required"
        assert paused["pending_interrupt"]["actions"][0]["action_id"] == "call-1"
        assert await h.email.search("", folder="sent", limit=10) == []

        # Busy while waiting for a human; bad decisions are rejected before scheduling.
        busy = await h.client.post(
            f"/threads/{tid}/messages", json={"content": "again"}, headers=headers
        )
        bad = {"decisions": {"nope": {"type": "approve"}}}
        invalid = await h.client.post(f"/threads/{tid}/approvals", json=bad, headers=headers)
        assert (busy.status_code, busy.json()["error"]["code"]) == (409, "thread_busy")
        assert (invalid.status_code, invalid.json()["error"]["code"]) == (422, "invalid_approval")

        approved = await h.client.post(f"/threads/{tid}/approvals", json=APPROVE, headers=headers)
        assert approved.status_code == 202
        done = await settled(h.client, headers, tid)
        assert done["run"]["status"] == "idle" and done["pending_interrupt"] is None
        assert done["messages"][-1]["content"] == "Email sent."
        assert [a["decision"] for a in done["approvals"]] == ["approve"]
        assert len(await h.email.search("", folder="sent", limit=10)) == 1

        again = await h.client.post(f"/threads/{tid}/approvals", json=APPROVE, headers=headers)
        assert (again.status_code, again.json()["error"]["code"]) == (409, "no_pending_approval")


async def test_uncertain_resolution_requires_a_pending_uncertain_execution() -> None:
    async with running_api([]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        response = await h.client.post(
            f"/threads/{tid}/uncertain",
            json={"decisions": {"a": {"type": "skip"}}},
            headers=headers,
        )
        assert response.status_code == 409


async def test_posting_while_a_run_is_active_conflicts(monkeypatch: pytest.MonkeyPatch) -> None:
    async with running_api([]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        release = asyncio.Event()

        async def slow(*args: object, **kwargs: object) -> None:
            await release.wait()

        monkeypatch.setattr(h.container.runner, "run", slow)
        first = await h.client.post(
            f"/threads/{tid}/messages", json={"content": "one"}, headers=headers
        )
        second = await h.client.post(
            f"/threads/{tid}/messages", json={"content": "two"}, headers=headers
        )
        assert (first.status_code, second.status_code) == (202, 409)
        running = await h.client.get(f"/threads/{tid}", headers=headers)
        assert running.json()["run"]["status"] == "running"
        release.set()
        assert (await settled(h.client, headers, tid))["run"]["status"] == "idle"


async def test_failed_run_is_reported() -> None:
    async with running_api([ValueError("boom")]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        await h.client.post(f"/threads/{tid}/messages", json={"content": "go"}, headers=headers)
        assert (await settled(h.client, headers, tid))["run"]["status"] == "failed"


async def test_supervisor_allows_one_task_per_thread_and_cancels_on_shutdown() -> None:
    supervisor = RunSupervisor()
    started = asyncio.Event()

    async def forever() -> None:
        started.set()
        await asyncio.Event().wait()

    supervisor.start("t", lambda sink: forever())
    await started.wait()
    with pytest.raises(ThreadBusyError):
        supervisor.start("t", lambda sink: forever())
    assert supervisor.is_running("t")
    await supervisor.shutdown()
    assert not supervisor.is_running("t")
