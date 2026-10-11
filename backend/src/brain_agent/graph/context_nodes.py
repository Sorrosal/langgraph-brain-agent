"""Nodes that assemble context around the reasoning loop: recall, memorize and summarize."""

from collections.abc import Awaitable
from typing import Any, Protocol

import structlog
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from pydantic import BaseModel

from brain_agent.brain.context import ContextBudget, compact_messages, over_budget
from brain_agent.brain.memory import MemoryKind, MemoryService, format_memories
from brain_agent.graph.state import AgentState
from brain_agent.tools.memory_tools import thread_id_of, user_id_of

logger = structlog.get_logger(__name__)

LOAD_CONTEXT_NODE = "load_context"
MEMORIZE_NODE = "memorize"
SUMMARIZE_NODE = "summarize"

MAX_EXTRACTED_MEMORIES = 3

EXTRACTION_INSTRUCTIONS = (
    "Extract durable information worth remembering for future conversations from the last "
    "exchange: stable facts about the user or their business, explicit preferences, or notable "
    "episodes (what was decided or done). Skip small talk, anything temporary and anything "
    f"already obvious. Return at most {MAX_EXTRACTED_MEMORIES} short, self-contained items; "
    "return none if nothing qualifies."
)


class ExtractedMemory(BaseModel):
    kind: MemoryKind
    text: str


class ExtractedMemories(BaseModel):
    """Durable memories found in the last turn."""

    items: list[ExtractedMemory]


class ContextNode(Protocol):
    """Async node signature LangGraph recognises as accepting the run config."""

    def __call__(self, state: AgentState, config: RunnableConfig) -> Awaitable[dict[str, Any]]: ...


def make_load_context(recall_limit: int) -> ContextNode:
    """Node that puts memories (and org knowledge) relevant to the user's message in ``context``.

    It only acts when the last message is a human one, i.e. at the start of a turn; the block
    then stays in the state for the rest of the turn. Memory failures degrade to no context.
    """

    async def load_context(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        last = state["messages"][-1] if state["messages"] else None
        if not isinstance(last, HumanMessage):
            return {}
        try:
            found = await MemoryService(get_store()).recall(
                user_id_of(config), last.text, limit=recall_limit, include_org=True
            )
        except Exception:
            logger.exception("context_recall_failed")
            return {"context": ""}
        return {"context": format_memories(found)}

    return load_context


def _last_turn(state: AgentState) -> str | None:
    """Transcript of the latest user turn (from the last human message), if any."""
    messages = state["messages"]
    start = next((i for i in range(len(messages) - 1, -1, -1) if messages[i].type == "human"), None)
    if start is None:
        return None
    return "\n".join(f"{m.type}: {m.text}" for m in messages[start:] if m.text)


def make_memorize(model: BaseChatModel) -> ContextNode:
    """Node that extracts durable memories from the finished turn and stores them.

    Storing is deduplicated, so re-running the node is harmless. Any failure is logged and the
    turn completes normally.
    """
    extractor = model.with_structured_output(ExtractedMemories)

    async def memorize(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        transcript = _last_turn(state)
        if not transcript:
            return {}
        try:
            result = await extractor.ainvoke(
                [SystemMessage(content=EXTRACTION_INSTRUCTIONS), HumanMessage(content=transcript)],
                config,
            )
            service = MemoryService(get_store())
            parsed = ExtractedMemories.model_validate(result)
            for item in parsed.items[:MAX_EXTRACTED_MEMORIES]:
                if item.text.strip():
                    await service.remember(
                        user_id_of(config),
                        item.kind,
                        item.text,
                        source_thread_id=thread_id_of(config),
                    )
        except Exception:
            logger.exception("memory_extraction_failed")
        return {}

    return memorize


def make_summarize(model: BaseChatModel, budget: ContextBudget) -> ContextNode:
    """Node that folds the oldest messages into ``summary`` when the history is over budget."""

    async def summarize(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        messages = state["messages"]
        if not over_budget(messages, budget):
            return {}
        try:
            compacted = await compact_messages(messages, state.get("summary", ""), model, budget)
        except Exception:
            logger.exception("context_summary_failed")
            return {}
        if compacted is None:
            return {}
        summary, removals = compacted
        return {"summary": summary, "messages": removals}

    return summarize
