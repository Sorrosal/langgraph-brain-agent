"""Tests for context assembly: recalled memories, compaction and memory extraction."""

from typing import Any

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from brain_agent.brain.context import ContextBudget, compact_messages
from brain_agent.brain.memory import MemoryService
from brain_agent.graph.builder import AgentGraph, build_graph
from tests.fakes import BagOfWordsEmbeddings, ScriptedChatModel, tool_call


def _store() -> InMemoryStore:
    return InMemoryStore(
        index={
            "dims": BagOfWordsEmbeddings.DIMS,
            "embed": BagOfWordsEmbeddings(),
            "fields": ["text"],
        }
    )


def _config(thread: str = "t", user: str = "alice") -> Any:
    return {"configurable": {"thread_id": thread, "user_id": user}}


def _system(model: ScriptedChatModel, call: int) -> str:
    """All system text the model got on ``call`` (stable prompt + per-turn context), minus the
    clock line so two calls of the same turn compare equal."""
    texts = [str(m.content) for m in model.inputs[call] if isinstance(m, SystemMessage)]
    assert texts
    lines = "\n".join(texts).splitlines()
    return "\n".join(line for line in lines if not line.startswith("- Current date and time"))


def _extraction(*items: tuple[str, str]) -> AIMessage:
    payload = [{"kind": kind, "text": text} for kind, text in items]
    return tool_call("ExtractedMemories", {"items": payload}, "extract")


# --- load_context -----------------------------------------------------------------------


async def test_load_context_injects_relevant_memories_into_system_prompt() -> None:
    store = _store()
    service = MemoryService(store)
    await service.remember("alice", "preference", "likes dark roast coffee", source_thread_id="t0")
    await service.remember("alice", "fact", "dog is named Rex", source_thread_id="t0")
    await service.add_org_knowledge("Coffee budget is 50 euros per month")
    model = ScriptedChatModel(script=[AIMessage("ok"), AIMessage("ok")])
    graph = build_graph(model, [], store=store, memory_recall_limit=2)

    await graph.ainvoke(
        {"messages": [HumanMessage("coffee budget: which dark roast coffee to order")]}, _config()
    )
    await graph.ainvoke(
        {"messages": [HumanMessage("coffee budget: which dark roast coffee to order")]},
        _config(user="bob"),
    )

    alice = _system(model, 0)
    assert "likes dark roast coffee" in alice
    assert "Coffee budget is 50 euros per month" in alice
    assert "Rex" not in alice  # limited to the 2 most relevant
    assert "dark roast" not in _system(model, 1)  # other users do not see alice's memories


async def test_load_context_only_runs_at_the_start_of_a_user_turn() -> None:
    store = _store()
    await MemoryService(store).remember("alice", "fact", "tea fan", source_thread_id="t")

    @tool
    def lookup(query: str) -> str:
        """Look up a record."""
        return "found"

    model = ScriptedChatModel(script=[tool_call("lookup", {"query": "x"}, "c1"), AIMessage("done")])
    graph = build_graph(model, [lookup], store=store, checkpointer=InMemorySaver())

    result = await graph.ainvoke({"messages": [HumanMessage("tea?")]}, _config())

    assert "tea fan" in _system(model, 0)
    assert _system(model, 1) == _system(model, 0)  # kept for the whole turn, not recomputed
    assert "tea fan" in result["context"]


# --- compaction -------------------------------------------------------------------------


def _history() -> list[AnyMessage]:
    return [
        HumanMessage("first question " * 20, id="h1"),
        AIMessage("", tool_calls=[{"name": "lookup", "args": {}, "id": "c1"}], id="a1"),
        ToolMessage("result " * 20, tool_call_id="c1", id="tm1"),
        AIMessage("first answer " * 20, id="a2"),
        HumanMessage("second question", id="h2"),
        AIMessage("", tool_calls=[{"name": "lookup", "args": {}, "id": "c2"}], id="a3"),
        ToolMessage("result", tool_call_id="c2", id="tm2"),
        AIMessage("second answer", id="a4"),
    ]


async def test_compact_messages_never_splits_tool_call_pairs() -> None:
    model = ScriptedChatModel(script=[AIMessage("NEW SUMMARY")])
    messages = _history()

    # keep_last=2 would cut between a3 and its tool result tm2; the cut must move before a3.
    result = await compact_messages(
        messages, "old summary", model, ContextBudget(max_tokens=10, keep_last_messages=2)
    )

    assert result is not None
    summary, removals = result
    assert summary == "NEW SUMMARY"
    assert all(isinstance(r, RemoveMessage) for r in removals)
    assert [r.id for r in removals] == ["h1", "a1", "tm1", "a2", "h2"]
    prompt = "\n".join(str(m.content) for m in model.inputs[0])
    assert "old summary" in prompt  # merged with the previous summary
    assert "first question" in prompt
    assert "second answer" not in prompt  # kept messages are not summarised


async def test_compact_messages_noop_under_budget_or_when_nothing_is_old_enough() -> None:
    model = ScriptedChatModel(script=[])
    messages = _history()

    assert await compact_messages(messages, "", model, ContextBudget(10_000, 3)) is None
    assert await compact_messages(messages, "", model, ContextBudget(10, 50)) is None
    assert model.calls == 0


async def test_graph_summarises_old_messages_and_model_sees_the_summary() -> None:
    model = ScriptedChatModel(
        script=[
            AIMessage("answer one " * 30),
            AIMessage("SUMMARY OF TURN ONE"),  # summarize after turn 1 (over budget)
            AIMessage("answer two"),
        ]
    )
    graph = build_graph(
        model, [], checkpointer=InMemorySaver(), context_budget=ContextBudget(40, 1)
    )

    first = await graph.ainvoke({"messages": [HumanMessage("question one " * 30)]}, _config())
    second = await graph.ainvoke({"messages": [HumanMessage("question two")]}, _config())

    assert first["summary"] == "SUMMARY OF TURN ONE"
    assert [m.content for m in first["messages"]] == [first["messages"][-1].content]
    assert "Conversation summary so far" in _system(model, 2)
    assert "SUMMARY OF TURN ONE" in _system(model, 2)
    assert second["messages"][-1].content == "answer two"


# --- memorize ---------------------------------------------------------------------------


async def _facts(store: InMemoryStore, user: str = "alice") -> list[str]:
    return sorted(m.text for m in await MemoryService(store).list(user))


def _memorizing_graph(model: ScriptedChatModel, store: InMemoryStore) -> AgentGraph:
    return build_graph(model, [], store=store, memory_extraction=True, checkpointer=InMemorySaver())


async def test_memorize_extracts_and_stores_durable_memories() -> None:
    store = _store()
    model = ScriptedChatModel(
        script=[
            AIMessage("Noted, Madrid it is."),
            _extraction(("fact", "lives in Madrid"), ("preference", "prefers email")),
        ]
    )

    await _memorizing_graph(model, store).ainvoke(
        {"messages": [HumanMessage("I live in Madrid and prefer email")]}, _config()
    )

    assert await _facts(store) == ["lives in Madrid", "prefers email"]
    stored = await MemoryService(store).list("alice", "fact")
    assert stored[0].source_thread_id == "t"


async def test_memorize_keeps_at_most_three_items() -> None:
    store = _store()
    items = [("fact", f"fact number {n}") for n in range(5)]
    model = ScriptedChatModel(script=[AIMessage("ok"), _extraction(*items)])

    await _memorizing_graph(model, store).ainvoke({"messages": [HumanMessage("hi")]}, _config())

    assert len(await _facts(store)) == 3


async def test_memorize_failure_does_not_fail_the_turn() -> None:
    store = _store()
    model = ScriptedChatModel(script=[AIMessage("fine"), RuntimeError("extractor down")])

    result = await _memorizing_graph(model, store).ainvoke(
        {"messages": [HumanMessage("hello")]}, _config()
    )

    assert result["messages"][-1].content == "fine"
    assert await _facts(store) == []


async def test_memorize_is_idempotent_when_the_node_runs_again() -> None:
    store = _store()
    same = _extraction(("fact", "lives in Madrid"))
    model = ScriptedChatModel(script=[AIMessage("ok"), same, same])
    graph = _memorizing_graph(model, store)
    config = _config()

    await graph.ainvoke({"messages": [HumanMessage("I live in Madrid")]}, config)
    snapshot = await graph.aget_state(config)
    await graph.ainvoke(None, await _replay_config(graph, config, snapshot), durability="sync")

    assert await _facts(store) == ["lives in Madrid"]
    assert model.calls == 3  # the extractor really ran twice


async def _replay_config(graph: AgentGraph, config: Any, snapshot: Any) -> Any:
    """Config of the checkpoint just before ``memorize`` ran, to re-execute that node."""
    async for state in graph.aget_state_history(config):
        if state.next == ("memorize",):
            return state.config
    raise AssertionError("no checkpoint before memorize")


async def test_memorize_is_off_by_default() -> None:
    store = _store()
    model = ScriptedChatModel(script=[AIMessage("ok")])

    await build_graph(model, [], store=store).ainvoke(
        {"messages": [HumanMessage("I live in Madrid")]}, _config()
    )

    assert model.calls == 1
    assert await _facts(store) == []
