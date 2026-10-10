"""Child process for the crash-recovery test: starts a run whose tool blocks until killed.

Run as ``python -m tests.crash_worker <database_url> <thread_id> <lease_seconds>`` from the
backend directory. It prints ``STARTED`` once the tool is executing, i.e. after the model's
tool-call step has been checkpointed, and then waits to be killed.
"""

import asyncio
import sys

from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool, tool

from brain_agent.graph.builder import build_graph
from brain_agent.persistence.postgres import open_persistence
from brain_agent.runtime.runner import AgentRunner
from tests.fakes import ScriptedChatModel, tool_call

TOOL_NAME = "slow_lookup"


def make_lookup_tool(*, block: bool, invocations: list[str] | None = None) -> BaseTool:
    """Tool that either blocks forever (``block``) or returns a record."""

    @tool(TOOL_NAME)
    async def slow_lookup(query: str) -> str:
        """Look up a record."""
        if invocations is not None:
            invocations.append(query)
        if block:
            print("STARTED", flush=True)
            await asyncio.sleep(3600)
        return f"record for {query}"

    return slow_lookup


async def main(database_url: str, thread_id: str, lease_seconds: float) -> None:
    model = ScriptedChatModel(
        script=[tool_call(TOOL_NAME, {"query": "ACME"}, "call-1"), AIMessage(content="unused")]
    )
    async with open_persistence(database_url) as persistence:
        graph = build_graph(
            model, [make_lookup_tool(block=True)], checkpointer=persistence.checkpointer
        )
        runner = AgentRunner(
            graph,
            runs=persistence.runs,
            owner_id="crash-worker",
            lease_seconds=lease_seconds,
        )
        await runner.run(thread_id, "find ACME")


if __name__ == "__main__":
    url, thread, lease = sys.argv[1], sys.argv[2], float(sys.argv[3])
    # psycopg's async API needs a selector loop on Windows (the default there is Proactor).
    asyncio.run(main(url, thread, lease), loop_factory=asyncio.SelectorEventLoop)
