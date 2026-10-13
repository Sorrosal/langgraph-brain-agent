"""Composition root: wires persistence, rules, tools, model, graph and runtime into one object."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

from brain_agent.brain.context import ContextBudget
from brain_agent.brain.memory import MemoryService
from brain_agent.brain.rules import RulesEngine, YamlRuleSource
from brain_agent.config import Settings
from brain_agent.graph.builder import build_graph
from brain_agent.integrations.crm import CrmRepository
from brain_agent.integrations.email import EmailGateway
from brain_agent.integrations.email_factory import create_email_gateway
from brain_agent.integrations.tasks import TaskRepository
from brain_agent.llm import create_chat_model, create_embeddings
from brain_agent.persistence.postgres import open_persistence
from brain_agent.persistence.runs import RunLedger
from brain_agent.persistence.threads import ThreadRepository
from brain_agent.persistence.tool_ledger import ToolLedger
from brain_agent.persistence.users import UserRepository
from brain_agent.runtime.events import EventBroker
from brain_agent.runtime.recovery import RecoveryWorker
from brain_agent.runtime.runner import AgentRunner, RunResult
from brain_agent.runtime.supervisor import RunSupervisor
from brain_agent.tools.registry import build_business_tools
from brain_agent.tools.rules_tools import build_rules_tools

Ping = Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class AppContainer:
    """Everything the API needs while serving requests."""

    settings: Settings
    users: UserRepository
    threads: ThreadRepository
    runner: AgentRunner
    runs: RunLedger
    supervisor: RunSupervisor
    rules: RulesEngine
    memory: MemoryService
    events: EventBroker
    crm: CrmRepository
    tasks: TaskRepository
    email: EmailGateway
    ping: Ping
    """Raises when the database is unreachable."""
    recovery: RecoveryWorker | None = None
    rules_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    """Serialises rule file writes from the API and the agent."""


ContainerFactory = Callable[[Settings], AbstractAsyncContextManager[AppContainer]]


class _OwnerAwareResumer:
    """Lets the recovery worker resume a run on behalf of the thread's owner."""

    def __init__(self, runner: AgentRunner, threads: ThreadRepository, events: EventBroker) -> None:
        self._runner = runner
        self._threads = threads
        self._events = events

    @property
    def owner_id(self) -> str:
        return self._runner.owner_id

    @property
    def lease_seconds(self) -> float:
        return self._runner.lease_seconds

    async def resume(self, thread_id: str) -> RunResult:
        user_id = await self._threads.owner_of(thread_id)
        sink = self._events.sink(thread_id)
        if user_id is None:
            return await self._runner.resume(thread_id, sink=sink)
        return await self._runner.resume(thread_id, user_id=user_id, sink=sink)


def assemble_container(
    settings: Settings,
    *,
    model: BaseChatModel,
    checkpointer: BaseCheckpointSaver[Any],
    store: BaseStore,
    runs: RunLedger,
    tool_ledger: ToolLedger,
    crm: CrmRepository,
    tasks: TaskRepository,
    email: EmailGateway,
    users: UserRepository,
    threads: ThreadRepository,
    ping: Ping,
) -> AppContainer:
    """Build rules, tools, graph and runner on top of the given adapters.

    Raises ``RulesError`` when the rules cannot be loaded: the service never starts without them.
    """
    rules = RulesEngine.from_source(YamlRuleSource(settings.rules_dir))
    rules_lock = asyncio.Lock()
    rules_tools = build_rules_tools(settings.rules_dir, rules, users, rules_lock)
    graph = build_graph(
        model,
        build_business_tools(crm, tasks, email=email, extra=rules_tools),
        checkpointer=checkpointer,
        store=store,
        tool_ledger=tool_ledger,
        rules=rules,
        context_budget=ContextBudget(
            settings.context_max_tokens, settings.context_keep_last_messages
        ),
        memory_extraction=settings.memory_extraction_enabled,
        memory_recall_limit=settings.memory_recall_limit,
    )
    runner = AgentRunner(graph, runs=runs)
    events = EventBroker()
    return AppContainer(
        settings=settings,
        users=users,
        threads=threads,
        runner=runner,
        runs=runs,
        supervisor=RunSupervisor(events),
        rules=rules,
        memory=MemoryService(store),
        events=events,
        crm=crm,
        tasks=tasks,
        email=email,
        ping=ping,
        recovery=RecoveryWorker(_OwnerAwareResumer(runner, threads, events), runs),
        rules_lock=rules_lock,
    )


@asynccontextmanager
async def build_container(
    settings: Settings, *, model: BaseChatModel | None = None
) -> AsyncIterator[AppContainer]:
    """Open the PostgreSQL-backed container; ``model`` replaces the OpenAI chat model (tests)."""
    embeddings = (
        create_embeddings(settings)
        if settings.openai_api_key and settings.openai_api_key.get_secret_value().strip()
        else None
    )
    async with open_persistence(settings.database_url, embeddings=embeddings) as persistence:

        async def ping() -> None:
            async with persistence.pool.connection() as conn:
                await conn.execute("SELECT 1")

        yield assemble_container(
            settings,
            model=model or create_chat_model(settings),
            checkpointer=persistence.checkpointer,
            store=persistence.store,
            runs=persistence.runs,
            tool_ledger=persistence.tool_ledger,
            crm=persistence.crm,
            tasks=persistence.tasks,
            email=create_email_gateway(settings, persistence.pool),
            users=persistence.users,
            threads=persistence.threads,
            ping=ping,
        )
