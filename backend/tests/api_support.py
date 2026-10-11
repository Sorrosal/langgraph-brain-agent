"""Helpers to run the API against in-memory adapters and a scripted model."""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI
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


@dataclass(frozen=True)
class SseEvent:
    id: int
    event: str
    data: Any


class SseStream:
    """Talks ASGI to the app directly: httpx buffers a streaming body until it ends."""

    def __init__(self, app: FastAPI, path: str, headers: dict[str, str] | None = None) -> None:
        path, _, query = path.partition("?")
        self.status = 0
        self.headers: dict[str, str] = {}
        self._chunks: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._started = asyncio.Event()
        self._disconnect = asyncio.Event()
        self._sent_request = False
        self._buffer = ""
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query.encode(),
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
            "client": ("127.0.0.1", 5000),
            "server": ("test", 80),
        }
        self._task = asyncio.create_task(app(scope, self._receive, self._send))  # type: ignore[arg-type]

    async def _receive(self) -> dict[str, Any]:
        if not self._sent_request:
            self._sent_request = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await self._disconnect.wait()
        return {"type": "http.disconnect"}

    async def _send(self, message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            self.status = message["status"]
            self.headers = {k.decode(): v.decode() for k, v in message["headers"]}
            self._started.set()
        elif message["type"] == "http.response.body":
            if message.get("body"):
                await self._chunks.put(message["body"])
            if not message.get("more_body"):
                await self._chunks.put(None)

    async def __aenter__(self) -> "SseStream":
        await asyncio.wait_for(self._started.wait(), 2)
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Disconnect the client; the app must then finish by itself."""
        self._disconnect.set()
        await asyncio.wait_for(self._task, 2)

    @property
    def finished(self) -> bool:
        return self._task.done()

    async def frame(self) -> str:
        """Next raw frame (an event or a ``:`` comment)."""
        while "\n\n" not in self._buffer:
            chunk = await asyncio.wait_for(self._chunks.get(), 2)
            assert chunk is not None, "stream ended"
            self._buffer += chunk.decode()
        frame, _, self._buffer = self._buffer.partition("\n\n")
        return frame

    async def until(self, final: str) -> list[SseEvent]:
        """Events up to and including the first ``final`` one (comments skipped)."""
        found: list[SseEvent] = []
        while not found or found[-1].event != final:
            frame = await self.frame()
            if frame.startswith(":"):
                continue
            fields = dict(line.split(": ", 1) for line in frame.splitlines())
            found.append(SseEvent(int(fields["id"]), fields["event"], json.loads(fields["data"])))
        return found

    async def body(self) -> str:
        parts = []
        while (chunk := await self._chunks.get()) is not None:
            parts.append(chunk.decode())
        return "".join(parts)


@dataclass
class Harness:
    client: httpx.AsyncClient
    container: AppContainer
    model: ScriptedChatModel
    email: InMemoryEmailGateway
    app: FastAPI

    def sse(self, path: str, headers: dict[str, str] | None = None) -> SseStream:
        return SseStream(self.app, path, headers)


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
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield Harness(client, app.state.container, model, email, app)


async def register(
    client: httpx.AsyncClient, email: str = "ana@acme.com", password: str = PASSWORD
) -> dict[str, str]:
    response = await client.post(
        "/auth/register", json={"email": email, "password": password, "display_name": "Ana"}
    )
    assert response.status_code == 202, response.text
    login = await client.post("/auth/login", json={"email": email, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}
