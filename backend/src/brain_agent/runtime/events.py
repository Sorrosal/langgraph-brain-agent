"""Domain events of a run and the in-process broker that fans them out to SSE clients.

Single-replica only: the broker lives in one process, so a client connected to replica A never
sees the events of a run executing on replica B. Multi-replica fan-out (e.g. PostgreSQL
``LISTEN/NOTIFY`` or Redis) is phase 7 work; until then clients that miss events fall back to
``GET /threads/{id}``, which always reflects the checkpointed state.
"""

import asyncio
import time
from collections import deque
from collections.abc import AsyncGenerator, Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from brain_agent.errors import LeaseLostError, ThreadBusyError
from brain_agent.graph.nodes import REASON_NODE
from brain_agent.graph.retry import is_transient_error

DEFAULT_BUFFER_SIZE = 500
DEFAULT_IDLE_SECONDS = 600.0
MAX_RESULT_CHARS = 2000


@dataclass(frozen=True, slots=True)
class Event:
    id: int
    """Strictly increasing per thread (also across idle clean-ups)."""
    type: str
    data: dict[str, Any]


class EventSink(Protocol):
    """Receives the events of one thread's run, in order."""

    def __call__(self, type: str, data: dict[str, Any]) -> None: ...


FAILURES = {
    "lease_lost": "The run was taken over by another worker.",
    "thread_busy": "The thread is busy.",
    "temporarily_unavailable": "A dependency was temporarily unavailable; the run will be retried.",
    "run_failed": "The run failed.",
}


def failure_code(exc: BaseException) -> str:
    """Stable, safe code for a failed run; the exception text itself is never exposed."""
    if isinstance(exc, LeaseLostError):
        return "lease_lost"
    if isinstance(exc, ThreadBusyError):
        return "thread_busy"
    if isinstance(exc, Exception) and is_transient_error(exc):
        return "temporarily_unavailable"
    return "run_failed"


def failure_data(exc: BaseException) -> dict[str, Any]:
    code = failure_code(exc)
    return {"code": code, "message": FAILURES[code]}


def _truncate(text: str) -> str:
    return text if len(text) <= MAX_RESULT_CHARS else text[:MAX_RESULT_CHARS] + "…"


def _message_events(node: str, messages: Iterable[BaseMessage]) -> Iterable[tuple[str, Any]]:
    for message in messages:
        if isinstance(message, AIMessage) and node == REASON_NODE:
            for call in message.tool_calls:
                yield "tool_call", {"name": call["name"], "args": call["args"], "id": call["id"]}
        elif isinstance(message, ToolMessage):
            yield (
                "tool_result",
                {
                    "id": message.tool_call_id,
                    "name": message.name,
                    "status": message.status,
                    "content": _truncate(message.text),
                },
            )


def translate(mode: str, data: Any) -> list[tuple[str, dict[str, Any]]]:
    """Map one LangGraph ``stream_mode=["messages", "updates"]`` item to domain events."""
    if mode == "messages":
        chunk, metadata = data
        if metadata.get("langgraph_node") == REASON_NODE and isinstance(chunk, AIMessage):
            return [("token", {"text": chunk.text})] if chunk.text else []
        return []
    events: list[tuple[str, dict[str, Any]]] = []
    for node, update in data.items():
        if node == "__interrupt__":
            events += [("interrupt", dict(i.value)) for i in update if isinstance(i.value, dict)]
            continue
        if isinstance(update, dict):
            events += _message_events(node, update.get("messages") or [])
        events.append(("node", {"node": node}))
    return events


class _Channel:
    __slots__ = ("buffer", "changed", "next_id", "subscribers", "touched")

    def __init__(self, size: int, now: float, first_id: int) -> None:
        self.buffer: deque[Event] = deque(maxlen=size)
        self.next_id = first_id
        self.changed = asyncio.Event()
        self.subscribers = 0
        self.touched = now


class EventBroker:
    """Per-thread pub/sub with a bounded replay buffer (the last ``buffer_size`` events)."""

    def __init__(
        self,
        *,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        idle_seconds: float = DEFAULT_IDLE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._size = buffer_size
        self._idle = idle_seconds
        self._clock = clock
        self._channels: dict[str, _Channel] = {}
        self._closed = False
        self._last_sweep = clock()
        self._issued = 0  # highest id handed out, so a recreated channel never reuses ids

    @property
    def thread_count(self) -> int:
        return len(self._channels)

    def subscriber_count(self, thread_id: str) -> int:
        channel = self._channels.get(thread_id)
        return channel.subscribers if channel else 0

    def latest_id(self, thread_id: str) -> int:
        """Id of the newest buffered event, or 0 when there is none."""
        channel = self._channels.get(thread_id)
        return channel.buffer[-1].id if channel and channel.buffer else 0

    def _channel(self, thread_id: str) -> _Channel:
        channel = self._channels.get(thread_id)
        if channel is None:
            # Millisecond epoch start (not 1): ids also stay increasing across idle clean-ups.
            first = max(time.time_ns() // 1_000_000, self._issued + 1)
            channel = self._channels[thread_id] = _Channel(self._size, self._clock(), first)
        return channel

    def publish(self, thread_id: str, type: str, data: dict[str, Any]) -> Event:
        now = self._clock()
        if now - self._last_sweep >= self._idle / 4:
            self.sweep()
        channel = self._channel(thread_id)
        event = Event(channel.next_id, type, data)
        channel.next_id += 1
        self._issued = max(self._issued, event.id)
        channel.buffer.append(event)
        channel.touched = now
        waiters, channel.changed = channel.changed, asyncio.Event()
        waiters.set()
        return event

    def sink(self, thread_id: str) -> EventSink:
        def emit(type: str, data: dict[str, Any]) -> None:
            self.publish(thread_id, type, data)

        return emit

    def sweep(self) -> None:
        """Forget threads nobody listens to and nothing happened on for ``idle_seconds``."""
        now = self._last_sweep = self._clock()
        for thread_id, channel in list(self._channels.items()):
            if channel.subscribers == 0 and now - channel.touched > self._idle:
                del self._channels[thread_id]

    async def subscribe(self, thread_id: str, after_id: int = 0) -> AsyncGenerator[Event]:
        """Buffered events newer than ``after_id``, then live ones, until :meth:`close`.

        Events older than the buffer are gone: a client resuming from too far back is simply
        served what is left and should re-read the thread state.
        """
        channel = self._channel(thread_id)
        channel.subscribers += 1
        last = after_id
        try:
            while not self._closed:
                changed = channel.changed  # taken before reading, so no publish is missed
                for event in tuple(channel.buffer):
                    if event.id > last:
                        last = event.id
                        yield event
                await changed.wait()
        finally:
            channel.subscribers -= 1
            channel.touched = self._clock()

    def close(self) -> None:
        """Wake every subscriber and end their streams (application shutdown)."""
        self._closed = True
        for channel in self._channels.values():
            waiters, channel.changed = channel.changed, asyncio.Event()
            waiters.set()
