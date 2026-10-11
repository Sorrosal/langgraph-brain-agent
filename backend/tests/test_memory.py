"""Tests for the long-term memory service and the agent memory tools."""

import asyncio
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from brain_agent.brain.memory import MemoryService
from brain_agent.graph.builder import build_graph
from brain_agent.persistence.postgres import open_persistence
from brain_agent.tools.memory_tools import memory_tools
from tests.fakes import BagOfWordsEmbeddings, ScriptedChatModel, tool_call

DIMS = BagOfWordsEmbeddings.DIMS


def _memory_store() -> InMemoryStore:
    return InMemoryStore(index={"dims": DIMS, "embed": BagOfWordsEmbeddings(), "fields": ["text"]})


@pytest.fixture(params=["memory", "postgres"])
async def store(request: pytest.FixtureRequest) -> AsyncIterator[BaseStore]:
    if request.param == "memory":
        yield _memory_store()
        return
    schema_url: str = request.getfixturevalue("schema_url")
    async with open_persistence(
        schema_url, embeddings=BagOfWordsEmbeddings(), embedding_dims=DIMS
    ) as persistence:
        yield persistence.store


async def test_remember_dedupes_normalized_text(store: BaseStore) -> None:
    service = MemoryService(store)

    first = await service.remember("u1", "fact", "Lives in  Madrid", source_thread_id="t1")
    again = await service.remember("u1", "fact", " lives in madrid ", source_thread_id="t2")

    assert again.id == first.id
    assert again.source_thread_id == "t1"  # the original is kept
    assert [m.text for m in await service.list("u1")] == ["Lives in  Madrid"]
    # The same text under another kind is a distinct memory.
    other = await service.remember("u1", "preference", "lives in madrid", source_thread_id="t1")
    assert other.id != first.id


async def test_recall_orders_by_semantic_similarity(store: BaseStore) -> None:
    service = MemoryService(store)
    for text in ("likes dark roast coffee", "dog is named Rex", "works at Acme as accountant"):
        await service.remember("u1", "fact", text, source_thread_id="t")

    hits = await service.recall("u1", "what coffee does the user like", limit=2)

    assert hits[0].text == "likes dark roast coffee"
    assert len(hits) == 2
    assert hits[0].score is not None
    assert hits[0].score >= hits[1].score  # type: ignore[operator]


async def test_recall_filters_kinds_and_isolates_users(store: BaseStore) -> None:
    service = MemoryService(store)
    await service.remember("a@acme.com", "fact", "coffee fact", source_thread_id="t")
    await service.remember("a@acme.com", "preference", "coffee preference", source_thread_id="t")
    await service.remember("u2", "fact", "coffee of someone else", source_thread_id="t")

    only_pref = await service.recall("a@acme.com", "coffee", kinds=["preference"])
    both = await service.recall("a@acme.com", "coffee")

    assert [m.text for m in only_pref] == ["coffee preference"]
    assert {m.text for m in both} == {"coffee fact", "coffee preference"}
    assert [m.text for m in await service.list("u2")] == ["coffee of someone else"]
    assert [m.kind for m in await service.list("a@acme.com", "fact")] == ["fact"]


async def test_forget_removes_only_that_memory(store: BaseStore) -> None:
    service = MemoryService(store)
    keep = await service.remember("u1", "fact", "keep me", source_thread_id="t")
    drop = await service.remember("u1", "episode", "drop me", source_thread_id="t")

    assert await service.forget("u1", drop.id) is True
    assert await service.forget("u1", drop.id) is False
    assert await service.forget("u2", keep.id) is False  # other users cannot delete it

    assert [m.id for m in await service.list("u1")] == [keep.id]


async def test_org_knowledge_is_shared_by_all_users(store: BaseStore) -> None:
    service = MemoryService(store)
    await service.add_org_knowledge("Refund policy: refunds within 30 days")
    await service.remember("u1", "fact", "likes tea", source_thread_id="t")

    for user in ("u1", "u2"):
        hits = await service.recall(user, "refund policy", include_org=True)
        assert hits[0].text == "Refund policy: refunds within 30 days"
    assert await service.recall("u2", "refund policy") == []  # opt-in, never in user lists
    assert [m.text for m in await service.list("u1")] == ["likes tea"]


async def test_recall_without_index_falls_back_to_recency() -> None:
    service = MemoryService(InMemoryStore())
    await service.remember("u1", "fact", "older", source_thread_id="t")
    await asyncio.sleep(0.05)  # distinct timestamps
    await service.remember("u1", "fact", "newer", source_thread_id="t")

    hits = await service.recall("u1", "anything", limit=1)

    assert [m.text for m in hits] == ["newer"]
    assert hits[0].score is None


# --- agent tools in a graph run ---------------------------------------------------------


def _agent(
    model: ScriptedChatModel, store: BaseStore, checkpointer: InMemorySaver
) -> Callable[[str, str, str], Any]:
    graph = build_graph(model, memory_tools(), checkpointer=checkpointer, store=store)

    async def run(thread: str, user: str, text: str) -> Any:
        config: Any = {"configurable": {"thread_id": thread, "user_id": user}}
        return await graph.ainvoke({"messages": [HumanMessage(text)]}, config)

    return run


async def test_memory_tools_share_memories_across_threads_per_user() -> None:
    store = _memory_store()
    model = ScriptedChatModel(
        script=[
            tool_call("remember", {"kind": "preference", "text": "likes dark roast coffee"}, "r1"),
            AIMessage("saved"),
            tool_call("recall", {"query": "coffee"}, "c1"),  # same user, new thread
            AIMessage("done"),
            tool_call("recall", {"query": "coffee"}, "c2"),  # other user
            AIMessage("done"),
        ]
    )
    run = _agent(model, store, InMemorySaver())

    await run("t1", "alice", "remember I like dark roast coffee")
    same = await run("t2", "alice", "what coffee do I like?")
    other = await run("t3", "bob", "what coffee do I like?")

    def result(state: Any) -> str:
        tool_messages = [m for m in state["messages"] if isinstance(m, ToolMessage)]
        return str(tool_messages[-1].content)

    assert "dark roast" in result(same)
    assert "dark roast" not in result(other)


def test_memory_tools_are_low_risk_and_retry_safe() -> None:
    for tool in memory_tools():
        assert tool.metadata is not None
        assert tool.metadata["retry_safe"] is True
        assert tool.metadata["risk"] == "low"
