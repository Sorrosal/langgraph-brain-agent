"""Task domain model and the repository port."""

from datetime import date, datetime
from typing import Literal, Protocol

from pydantic import BaseModel

Priority = Literal["low", "normal", "high"]
TaskStatus = Literal["open", "done"]


class Task(BaseModel):
    id: str
    title: str
    description: str
    due_date: date | None = None
    priority: Priority
    status: TaskStatus
    assignee: str | None = None
    created_at: datetime


class TaskRepository(Protocol):
    """Tasks. ``create_task`` is idempotent on ``idempotency_key``; ``complete_task`` raises
    :class:`NotFoundError` for an unknown id; ``delete_task`` returns ``False`` if already gone."""

    async def create_task(
        self,
        title: str,
        description: str,
        due_date: date | None,
        priority: Priority,
        assignee: str | None,
        *,
        idempotency_key: str,
    ) -> Task: ...

    async def list_tasks(
        self, status: TaskStatus | None, assignee: str | None, limit: int
    ) -> list[Task]:
        """Tasks in creation order."""
        ...

    async def complete_task(self, task_id: str) -> Task: ...

    async def delete_task(self, task_id: str) -> bool: ...
