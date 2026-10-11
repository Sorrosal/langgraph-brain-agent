"""Read-only business data for the dashboard, and the approval queue."""

import asyncio
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from brain_agent.api.auth import Container, CurrentUser
from brain_agent.hitl.models import PendingInterrupt
from brain_agent.integrations.crm import Contact, Deal, DealStage
from brain_agent.integrations.email import EmailMessage, Folder
from brain_agent.integrations.tasks import Task, TaskStatus

router = APIRouter(tags=["data"])

Limit = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=200)]
APPROVAL_SCAN_THREADS = 100
APPROVAL_SCAN_CONCURRENCY = 8


@router.get("/crm/contacts", response_model=list[Contact])
async def list_contacts(
    container: Container, _: CurrentUser, q: Search = "", limit: Limit = 50
) -> list[Contact]:
    return await container.crm.search_contacts(q, limit)


@router.get("/crm/deals", response_model=list[Deal])
async def list_deals(
    container: Container, _: CurrentUser, stage: DealStage | None = None, limit: Limit = 50
) -> list[Deal]:
    return (await container.crm.list_deals(None, stage))[:limit]


@router.get("/tasks", response_model=list[Task])
async def list_tasks(
    container: Container, _: CurrentUser, status: TaskStatus | None = None, limit: Limit = 50
) -> list[Task]:
    return await container.tasks.list_tasks(status, None, limit)


@router.get("/emails", response_model=list[EmailMessage])
async def list_emails(
    container: Container,
    _: CurrentUser,
    folder: Folder = "inbox",
    q: Search = "",
    limit: Limit = 50,
) -> list[EmailMessage]:
    return await container.email.search(q, folder=folder, limit=limit)


class PendingApproval(BaseModel):
    thread_id: str
    title: str
    updated_at: datetime
    interrupt: PendingInterrupt


@router.get("/approvals/pending", response_model=list[PendingApproval])
async def pending_approvals(container: Container, user: CurrentUser) -> list[PendingApproval]:
    """Threads of the user paused on a decision, most recently active first.

    Looks at the user's latest ``APPROVAL_SCAN_THREADS`` threads: the checkpointer has no index
    of paused threads. An indexed query is a phase 7 follow-up.
    """
    threads = await container.threads.list(user.id, APPROVAL_SCAN_THREADS, 0)
    gate = asyncio.Semaphore(APPROVAL_SCAN_CONCURRENCY)

    async def pending(thread_id: str) -> PendingInterrupt | None:
        async with gate:
            return await container.runner.get_pending_interrupt(thread_id)

    found = await asyncio.gather(*(pending(t.id) for t in threads))
    return [
        PendingApproval(thread_id=t.id, title=t.title, updated_at=t.updated_at, interrupt=p)
        for t, p in zip(threads, found, strict=True)
        if p is not None
    ]
