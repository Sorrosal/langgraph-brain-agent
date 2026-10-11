"""Agent tools for long-term memory, bound to the store LangGraph injects."""

from typing import Annotated

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import InjectedStore
from langgraph.store.base import BaseStore

from brain_agent.brain.memory import MemoryKind, MemoryService, format_memories

DEFAULT_USER_ID = "default"
RECALL_LIMIT = 5


def user_id_of(config: RunnableConfig) -> str:
    """The user the run acts for: ``config["configurable"]["user_id"]``, else ``"default"``."""
    return str((config.get("configurable") or {}).get("user_id") or DEFAULT_USER_ID)


def thread_id_of(config: RunnableConfig) -> str | None:
    thread_id = (config.get("configurable") or {}).get("thread_id")
    return str(thread_id) if thread_id else None


@tool
async def remember(
    kind: MemoryKind,
    text: str,
    store: Annotated[BaseStore, InjectedStore()],
    config: RunnableConfig,
) -> str:
    """Save a durable fact, preference or episode about the user for future conversations."""
    service = MemoryService(store)
    await service.remember(user_id_of(config), kind, text, source_thread_id=thread_id_of(config))
    return f"Remembered ({kind}): {text}"


@tool
async def recall(
    query: str, store: Annotated[BaseStore, InjectedStore()], config: RunnableConfig
) -> str:
    """Search long-term memory (and shared organisation knowledge) for what is relevant."""
    found = await MemoryService(store).recall(
        user_id_of(config), query, limit=RECALL_LIMIT, include_org=True
    )
    return format_memories(found) or "No relevant memories."


# Saving is deduplicated, so replaying it after a crash is harmless.
remember.metadata = {"risk": "low", "retry_safe": True}
recall.metadata = {"risk": "low", "retry_safe": True}


def memory_tools() -> list[BaseTool]:
    """The ``remember`` and ``recall`` tools."""
    return [remember, recall]
