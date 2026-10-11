"""Task tools over a :class:`TaskRepository`."""

from datetime import date

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from brain_agent.integrations.tasks import Priority, TaskRepository, TaskStatus
from brain_agent.tools.support import idempotency_key_or_new, make_tool, to_json

LIST_LIMIT_MAX = 100


class CreateTaskArgs(BaseModel):
    title: str = Field(min_length=1, description="Short task title.")
    description: str = Field(default="", description="Details of what has to be done.")
    due_date: date | None = Field(default=None, description="Due date, ISO format YYYY-MM-DD.")
    priority: Priority = Field(default="normal", description="Task priority.")
    assignee: str | None = Field(default=None, description="Who is responsible.")


class ListTasksArgs(BaseModel):
    status: TaskStatus | None = Field(default=None, description="Only tasks with this status.")
    assignee: str | None = Field(default=None, description="Only tasks of this assignee.")
    limit: int = Field(default=20, ge=1, le=LIST_LIMIT_MAX, description="Maximum results.")


class TaskIdArgs(BaseModel):
    task_id: str = Field(description="Id of the task, as returned by list_tasks.")


def build_task_tools(repo: TaskRepository) -> list[BaseTool]:
    """The task tools, all safe to repeat after a crash."""

    async def create_task(
        title: str,
        description: str = "",
        due_date: date | None = None,
        priority: Priority = "normal",
        assignee: str | None = None,
    ) -> str:
        task = await repo.create_task(
            title,
            description,
            due_date,
            priority,
            assignee,
            idempotency_key=idempotency_key_or_new(),
        )
        return to_json(task)

    async def list_tasks(
        status: TaskStatus | None = None, assignee: str | None = None, limit: int = 20
    ) -> str:
        return to_json(list(await repo.list_tasks(status, assignee, limit)))

    async def complete_task(task_id: str) -> str:
        return to_json(await repo.complete_task(task_id))

    async def delete_task(task_id: str) -> str:
        return to_json({"deleted": await repo.delete_task(task_id)})

    return [
        make_tool(
            "create_task",
            "Create a task (to-do). Returns the created task as JSON, including its id.",
            CreateTaskArgs,
            create_task,
            "medium",
        ),
        make_tool(
            "list_tasks",
            "List tasks in creation order, optionally filtered by status and/or assignee. "
            "Returns a JSON list of tasks with their ids.",
            ListTasksArgs,
            list_tasks,
            "low",
        ),
        make_tool(
            "complete_task",
            "Mark a task as done. Returns the updated task as JSON.",
            TaskIdArgs,
            complete_task,
            "medium",
        ),
        make_tool(
            "delete_task",
            'Permanently delete a task. Requires human approval. Returns {"deleted": true|false}.',
            TaskIdArgs,
            delete_task,
            "high",
            approval_reason="Deleted tasks cannot be recovered.",
        ),
    ]
