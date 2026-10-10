"""Thread-oriented runner over a compiled, checkpointed agent graph."""

from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import StateSnapshot

from brain_agent.errors import ConfigurationError
from brain_agent.graph.builder import AgentGraph
from brain_agent.graph.state import AgentState

RunStatus = Literal["completed", "interrupted"]


@dataclass(frozen=True, slots=True)
class RunResult:
    """Outcome of a run or resume on a thread."""

    thread_id: str
    status: RunStatus
    last_message: str | None
    next_nodes: tuple[str, ...]


class AgentRunner:
    """Runs the agent graph per conversation thread with synchronous checkpointing.

    Every superstep is persisted before the next one starts (``durability="sync"``), so a run
    that dies mid-way can be continued with :meth:`resume` from any process sharing the
    same checkpointer.
    """

    def __init__(self, graph: AgentGraph) -> None:
        if not isinstance(graph.checkpointer, BaseCheckpointSaver):
            raise ConfigurationError("AgentRunner requires a graph compiled with a checkpointer")
        self._graph = graph

    async def run(self, thread_id: str, message: str) -> RunResult:
        """Send a user message on ``thread_id`` and run the agent until it stops."""
        config = _thread_config(thread_id)
        # A new user message starts a new run, so the step budget starts again.
        update: AgentState = {"messages": [HumanMessage(content=message)], "step_count": 0}
        await self._graph.ainvoke(update, config, durability="sync")
        return await self._result(thread_id)

    async def resume(self, thread_id: str) -> RunResult:
        """Continue an unfinished run from its last checkpoint; no-op if nothing is pending."""
        config = _thread_config(thread_id)
        snapshot = await self._graph.aget_state(config)
        if snapshot.next:
            await self._graph.ainvoke(None, config, durability="sync")
        return await self._result(thread_id)

    async def get_state(self, thread_id: str) -> StateSnapshot:
        """Return the latest checkpointed state of ``thread_id``."""
        return await self._graph.aget_state(_thread_config(thread_id))

    async def _result(self, thread_id: str) -> RunResult:
        snapshot = await self.get_state(thread_id)
        messages: list[BaseMessage] = (snapshot.values or {}).get("messages", [])
        return RunResult(
            thread_id=thread_id,
            status="interrupted" if snapshot.next else "completed",
            last_message=messages[-1].text if messages else None,
            next_nodes=tuple(snapshot.next),
        )


def _thread_config(thread_id: str) -> RunnableConfig:
    if not thread_id.strip():
        raise ValueError("thread_id must be a non-empty string")
    return {"configurable": {"thread_id": thread_id}}
