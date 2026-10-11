"""Helpers to run the API against in-memory adapters and a scripted model."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from brain_agent.api.app import create_app
from brain_agent.api.container import AppContainer, assemble_container
from brain_agent.config import Settings
from brain_agent.integrations.memory import (
    InMemoryCrmRepository,
    InMemoryEmailGateway,
    InMemoryTaskRepository,
)
from brain_agent.persistence.threads import InMemoryThreadRepository
from brain_agent.persistence.users import InMemoryUserRepository
from tests.fakes import FakeRunLedger, InMemoryToolLedger, ScriptedChatModel

PASSWORD = "correct-horse-1"


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "test",
        "jwt_secret": "s" * 40,
        "allow_registration": True,
        "memory_extraction_enabled": False,
    }
    return Settings(_env_file=None, **{**values, **overrides})


async def _ping_ok() -> None:
    return None


@dataclass
class Harness:
    client: httpx.AsyncClient
    container: AppContainer
    model: ScriptedChatModel
    email: InMemoryEmailGateway


@asynccontextmanager
async def running_api(
    script: list[AIMessage | Exception],
    settings: Settings | None = None,
    ping: Callable[[], Awaitable[None]] = _ping_ok,
) -> AsyncIterator[Harness]:
    settings = settings or make_settings()
    model = ScriptedChatModel(script=script)
    email = InMemoryEmailGateway()

    def factory(resolved: Settings) -> AbstractAsyncContextManager[AppContainer]:
        @asynccontextmanager
        async def build() -> AsyncIterator[AppContainer]:
            yield assemble_container(
                resolved,
                model=model,
                checkpointer=InMemorySaver(),
                store=InMemoryStore(),
                runs=FakeRunLedger(),
                tool_ledger=InMemoryToolLedger(),
                crm=InMemoryCrmRepository(),
                tasks=InMemoryTaskRepository(),
                email=email,
                users=InMemoryUserRepository(),
                threads=InMemoryThreadRepository(),
                ping=ping,
            )

        return build()

    app = create_app(settings, container_factory=factory)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield Harness(client, app.state.container, model, email)


async def register(
    client: httpx.AsyncClient, email: str = "ana@acme.com", password: str = PASSWORD
) -> dict[str, str]:
    response = await client.post(
        "/auth/register", json={"email": email, "password": password, "display_name": "Ana"}
    )
    assert response.status_code == 201, response.text
    login = await client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}
