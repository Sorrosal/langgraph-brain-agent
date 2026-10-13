"""Conversation threads: create, inspect and drive runs in the background."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Query, Request
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from pydantic import BaseModel, Field, field_validator

from brain_agent.api.auth import Container, CurrentUser
from brain_agent.api.ratelimit import enforce
from brain_agent.errors import NotFoundError, ThreadBusyError
from brain_agent.hitl.models import ApprovalResponse, PendingInterrupt, UncertainResponse
from brain_agent.persistence.threads import Thread
from brain_agent.runtime.supervisor import RunSupervisor

router = APIRouter(prefix="/threads", tags=["threads"])

RunStatus = Literal["idle", "running", "interrupted", "failed"]
TITLE_LENGTH = 80
RUN_FAILED = "run_failed"


class CreateThread(BaseModel):
    title: str = Field(default="", max_length=200)


class SendMessage(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    timezone: str | None = Field(default=None, max_length=64)
    """IANA time zone of the user's device, e.g. ``Europe/Madrid``; unknown zones are dropped."""
    language: Literal["en", "es"] | None = None
    """Language of the user's interface."""

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str | None) -> str | None:
        if not value:
            return None
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            return None
        return value


class ThreadOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, thread: Thread) -> "ThreadOut":
        return cls(
            id=thread.id,
            title=thread.title,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
        )


class MessageOut(BaseModel):
    id: str | None
    role: Literal["human", "ai", "tool"]
    content: str
    tool_calls: list[dict[str, Any]] = []
    tool_call_id: str | None = None
    status: str | None = None


class RunOut(BaseModel):
    status: RunStatus
    error: str | None = None


class ThreadDetail(ThreadOut):
    messages: list[MessageOut]
    summary: str | None
    pending_interrupt: PendingInterrupt | None
    run: RunOut
    approvals: list[dict[str, Any]]
    context_report: dict[str, Any] | None = None
    """What the agent's last model call was given (sections and approximate tokens)."""


class CheckpointOut(BaseModel):
    checkpoint_id: str
    step: int
    created_at: datetime | None
    source: str
    """``input`` (user input), ``loop`` (a superstep), ``update`` or ``fork``."""
    writes: list[str]
    """Nodes whose execution produced this checkpoint."""
    next: list[str]
    """Nodes that run next from it; empty once the run is finished."""
    message_count: int


class RunAccepted(BaseModel):
    run: RunOut


def _message(message: BaseMessage) -> MessageOut | None:
    if message.type not in ("human", "ai", "tool"):
        return None  # system prompts are an implementation detail
    return MessageOut(
        id=message.id,
        role=message.type,
        content=message.text,
        tool_calls=[dict(c) for c in message.tool_calls] if isinstance(message, AIMessage) else [],
        tool_call_id=message.tool_call_id if isinstance(message, ToolMessage) else None,
        status=message.status if isinstance(message, ToolMessage) else None,
    )


async def owned_thread(container: Container, user: CurrentUser, thread_id: str) -> Thread:
    thread = await container.threads.get(thread_id, user.id)
    if thread is None:  # also for other users' threads: never leak that the id exists
        raise NotFoundError("thread", thread_id)
    return thread


@contextmanager
def admission(supervisor: RunSupervisor, thread_id: str) -> Iterator[None]:
    """Hold the thread's run slot while a request validates and schedules its run.

    The slot is taken before any ``await``, so of two concurrent requests only one is admitted;
    it is released on any failure before the run starts.
    """
    supervisor.reserve(thread_id)
    try:
        yield
    except BaseException:
        supervisor.release(thread_id)
        raise


async def _run_status(container: Container, thread_id: str, interrupted: bool) -> RunOut:
    record = await container.runs.get(thread_id)
    failure = container.supervisor.last_failure(thread_id)
    if container.supervisor.is_running(thread_id) or (record and record.status == "running"):
        return RunOut(status="running")  # a lapsed lease is picked up by the recovery worker
    if record and record.status == "failed":
        return RunOut(status="failed", error=RUN_FAILED)  # the ledger keeps the raw text
    if interrupted:
        return RunOut(status="interrupted")
    if failure:
        return RunOut(status="failed", error=failure)
    return RunOut(status="idle")


@router.post("", status_code=201, response_model=ThreadOut)
async def create_thread(body: CreateThread, container: Container, user: CurrentUser) -> ThreadOut:
    return ThreadOut.of(await container.threads.create(user.id, body.title.strip()))


@router.get("", response_model=list[ThreadOut])
async def list_threads(
    container: Container,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ThreadOut]:
    return [ThreadOut.of(t) for t in await container.threads.list(user.id, limit, offset)]


@router.get("/{thread_id}", response_model=ThreadDetail)
async def get_thread(thread_id: str, container: Container, user: CurrentUser) -> ThreadDetail:
    thread = await owned_thread(container, user, thread_id)
    snapshot = await container.runner.get_state(thread_id)
    values = snapshot.values or {}
    pending = await container.runner.get_pending_interrupt(thread_id)
    messages = [m for m in map(_message, values.get("messages", [])) if m is not None]
    return ThreadDetail(
        **ThreadOut.of(thread).model_dump(),
        messages=messages,
        summary=values.get("summary") or None,
        pending_interrupt=pending,
        run=await _run_status(container, thread_id, pending is not None),
        approvals=values.get("approvals", []),
        context_report=values.get("context_report"),
    )


@router.get("/{thread_id}/history", response_model=list[CheckpointOut])
async def get_history(
    thread_id: str,
    container: Container,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[CheckpointOut]:
    """Checkpoints of the thread, newest first (the state inspector)."""
    await owned_thread(container, user, thread_id)
    history = await container.runner.get_history(thread_id, limit)
    return [CheckpointOut(**entry) for entry in history]


@router.post("/{thread_id}/messages", status_code=202, response_model=RunAccepted)
async def post_message(
    thread_id: str, body: SendMessage, container: Container, user: CurrentUser, request: Request
) -> RunAccepted:
    enforce(request, "messages", user.id, container.settings.rate_limit_messages_per_minute, 60)
    await owned_thread(container, user, thread_id)
    runner = container.runner
    with admission(container.supervisor, thread_id):
        if await runner.get_pending_interrupt(thread_id) is not None:
            raise ThreadBusyError(thread_id, approval_pending=True)
        session = {
            key: value
            for key, value in {
                "user_name": user.display_name,
                "role": user.role,
                "timezone": body.timezone,
                "language": body.language,
            }.items()
            if value
        }
        title = " ".join(body.content.split())[:TITLE_LENGTH]
        await container.threads.touch(thread_id, title_if_empty=title)
        container.supervisor.start(
            thread_id,
            lambda sink: runner.run(
                thread_id, body.content, user_id=user.id, session=session, sink=sink
            ),
        )
    return RunAccepted(run=RunOut(status="running"))


@router.post("/{thread_id}/approvals", status_code=202, response_model=RunAccepted)
async def post_approval(
    thread_id: str, body: ApprovalResponse, container: Container, user: CurrentUser
) -> RunAccepted:
    await owned_thread(container, user, thread_id)
    with admission(container.supervisor, thread_id):
        await container.runner.validate_approval(thread_id, body)
        container.supervisor.start(
            thread_id,
            lambda sink: container.runner.approve(thread_id, body, user_id=user.id, sink=sink),
        )
    return RunAccepted(run=RunOut(status="running"))


@router.post("/{thread_id}/uncertain", status_code=202, response_model=RunAccepted)
async def post_uncertain(
    thread_id: str, body: UncertainResponse, container: Container, user: CurrentUser
) -> RunAccepted:
    await owned_thread(container, user, thread_id)
    with admission(container.supervisor, thread_id):
        await container.runner.validate_uncertain(thread_id, body.decisions)
        container.supervisor.start(
            thread_id,
            lambda sink: container.runner.resolve_uncertain(
                thread_id, body.decisions, user_id=user.id, sink=sink
            ),
        )
    return RunAccepted(run=RunOut(status="running"))
