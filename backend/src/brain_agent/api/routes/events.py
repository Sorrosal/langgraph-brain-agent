"""Server-sent events: the live run of a thread (tokens, nodes, tool calls, interrupts)."""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import StreamingResponse

from brain_agent.api.auth import Container, StreamUser
from brain_agent.api.routes.threads import owned_thread
from brain_agent.runtime.events import Event

router = APIRouter(prefix="/threads", tags=["events"])


def frame(event: Event) -> str:
    data = json.dumps(event.data, default=str, separators=(",", ":"))
    return f"id: {event.id}\nevent: {event.type}\ndata: {data}\n\n"


async def _stream(
    request: Request, container: Container, thread_id: str, after: int
) -> AsyncIterator[str]:
    """Replay then follow; sends a comment when idle and stops with the client or the app."""
    events = container.events.subscribe(thread_id, after)
    heartbeat = container.settings.sse_heartbeat_seconds
    pending: asyncio.Future[Event] | None = None
    stopping = asyncio.ensure_future(request.app.state.shutdown.wait())
    try:
        while True:
            # A waiting anext() must survive heartbeats: cancelling it would close the iterator.
            pending = pending or asyncio.ensure_future(anext(events))
            done, _ = await asyncio.wait(
                {pending, stopping}, timeout=heartbeat, return_when=asyncio.FIRST_COMPLETED
            )
            if stopping.done():
                return  # the server is shutting down: do not hold its connections open
            if not done:
                if await request.is_disconnected():
                    return
                yield ": keep-alive\n\n"
                continue
            future, pending = pending, None
            try:
                event = future.result()
            except StopAsyncIteration:
                return  # the broker was closed: the application is shutting down
            yield frame(event)
    finally:
        stopping.cancel()
        if pending is not None:
            pending.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await pending
        await events.aclose()


@router.get("/{thread_id}/events")
async def stream_events(
    thread_id: str,
    request: Request,
    container: Container,
    user: StreamUser,
    last_event_id: Annotated[str | None, Header()] = None,
    after: Annotated[int | None, Query(ge=0)] = None,
) -> StreamingResponse:
    """Events of the thread as ``text/event-stream``.

    Resumes after ``Last-Event-ID`` (or ``?after=``); without either, only new events are sent
    (use ``GET /threads/{id}`` for the current state). Single replica: see ``runtime.events``.
    """
    await owned_thread(container, user, thread_id)
    if after is None and last_event_id and last_event_id.isdecimal():
        after = int(last_event_id)
    if after is None:
        after = container.events.latest_id(thread_id)
    return StreamingResponse(
        _stream(request, container, thread_id, after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
