"""Assembly of the agent's tool set."""

from collections.abc import Iterable

from langchain_core.tools import BaseTool

from brain_agent.integrations.crm import CrmRepository
from brain_agent.integrations.tasks import TaskRepository
from brain_agent.tools.crm_tools import build_crm_tools
from brain_agent.tools.memory_tools import memory_tools
from brain_agent.tools.task_tools import build_task_tools


def build_business_tools(
    crm: CrmRepository,
    tasks: TaskRepository,
    *,
    include_memory_tools: bool = True,
    extra: Iterable[BaseTool] = (),
) -> list[BaseTool]:
    """CRM and task tools, plus ``remember``/``recall`` and any ``extra`` tools (e.g. email)."""
    return [
        *build_crm_tools(crm),
        *build_task_tools(tasks),
        *(memory_tools() if include_memory_tools else []),
        *extra,
    ]
