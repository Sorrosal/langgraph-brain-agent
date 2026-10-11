"""Assembly of the agent's tool set."""

from collections.abc import Iterable

from langchain_core.tools import BaseTool

from brain_agent.integrations.crm import CrmRepository
from brain_agent.integrations.email import EmailGateway
from brain_agent.integrations.tasks import TaskRepository
from brain_agent.tools.crm_tools import build_crm_tools
from brain_agent.tools.email_tools import build_email_tools
from brain_agent.tools.memory_tools import memory_tools
from brain_agent.tools.task_tools import build_task_tools


def build_business_tools(
    crm: CrmRepository,
    tasks: TaskRepository,
    *,
    email: EmailGateway | None = None,
    include_memory_tools: bool = True,
    extra: Iterable[BaseTool] = (),
) -> list[BaseTool]:
    """CRM and task tools, email tools when an ``email`` gateway is given, ``remember``/``recall``
    and any ``extra`` tools."""
    return [
        *build_crm_tools(crm),
        *build_task_tools(tasks),
        *(build_email_tools(email) if email is not None else []),
        *(memory_tools() if include_memory_tools else []),
        *extra,
    ]
