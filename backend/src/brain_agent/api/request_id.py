"""``X-Request-ID`` propagation: accept a well-formed incoming id or generate one."""

import re
import uuid

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

HEADER = "X-Request-ID"
_VALID = re.compile(r"[A-Za-z0-9._-]{8,64}")


def request_id_of(scope: Scope) -> str | None:
    request_id: str | None = scope.get("state", {}).get("request_id")
    return request_id


class RequestIdMiddleware:
    """Pure ASGI (not ``BaseHTTPMiddleware``) so streaming responses are untouched."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(HEADER.lower().encode(), b"").decode("latin-1")
        request_id = incoming if _VALID.fullmatch(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[HEADER] = request_id
            await send(message)

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            await self.app(scope, receive, send_with_id)
