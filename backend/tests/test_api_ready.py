"""Liveness/readiness, error bodies and the Postgres-backed container wiring."""

import asyncio

import pytest
from langchain_core.messages import AIMessage

from brain_agent.api.container import build_container
from tests.api_support import make_settings, register, running_api
from tests.fakes import ScriptedChatModel


async def test_ready_reports_ok_and_unavailable() -> None:
    async with running_api([]) as h:
        assert (await h.client.get("/ready")).status_code == 200

    async def down() -> None:
        raise ConnectionError("db down")

    async with running_api([], ping=down) as h:
        response = await h.client.get("/ready")
        assert response.status_code == 503
        assert (await h.client.get("/health")).status_code == 200


async def test_cors_allows_configured_origin() -> None:
    async with running_api([]) as h:
        response = await h.client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_errors_use_the_common_body() -> None:
    async with running_api([]) as h:
        headers = await register(h.client)
        body = (await h.client.get("/threads/missing", headers=headers)).json()
        assert body["error"]["code"] == "not_found"
        assert set(body["error"]) == {"code", "message"}


@pytest.mark.integration
async def test_postgres_container_round_trip(schema_url: str) -> None:
    settings = make_settings(database_url=schema_url)
    model = ScriptedChatModel(script=[AIMessage(content="Stored reply.")])
    async with build_container(settings, model=model) as container:
        await container.ping()
        user = await container.users.create("pg@acme.com", "hash", "Pg")
        assert user.role == "admin"
        thread = await container.threads.create(user.id, "")
        container.supervisor.start(
            thread.id,
            lambda sink: container.runner.run(thread.id, "hi", user_id=user.id, sink=sink),
        )
        for _ in range(200):
            if not container.supervisor.is_running(thread.id):
                break
            await asyncio.sleep(0.02)
        snapshot = await container.runner.get_state(thread.id)
        assert snapshot.values["messages"][-1].content == "Stored reply."
        record = await container.runs.get(thread.id)
        assert record is not None and record.status == "completed"
        assert await container.threads.get(thread.id, "someone-else") is None
        assert [t.id for t in await container.threads.list(user.id, 10, 0)] == [thread.id]
