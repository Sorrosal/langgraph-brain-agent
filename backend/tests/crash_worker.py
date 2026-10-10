"""Child process for the crash-recovery test: starts a run whose tool blocks until killed.

Run as ``python -m tests.crash_worker <database_url> <thread_id> <lease_seconds> [mode]`` from
the backend directory. It prints ``STARTED`` once the crash point is reached and then waits to
be killed. Modes (``lookup`` by default):

* ``lookup``: the tool blocks, i.e. the model's tool-call step is checkpointed and the tools
  node is mid-flight;
* ``email-block``: ``send_email`` inserts its side effect into ``side_effects`` (the simulated
  external provider) and then blocks: crash after the side effect, before the ledger outcome;
* ``email-committed``: ``send_email`` completes and the ledger records ``succeeded``, but the
  process blocks when the tools node's writes are about to be checkpointed.
"""

import asyncio
import sys
from collections.abc import Sequence
from typing import Any

import psycopg
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from brain_agent.graph.builder import build_graph
from brain_agent.persistence.postgres import open_persistence
from brain_agent.runtime.runner import AgentRunner
from brain_agent.tools.idempotency import current_idempotency_key
from tests.fakes import ScriptedChatModel, tool_call

TOOL_NAME = "slow_lookup"
EMAIL_TOOL = "send_email"
EMAIL_ARGS = {"to": "ops@example.com"}
SIDE_EFFECTS_DDL = "CREATE TABLE side_effects (id serial PRIMARY KEY, recipient text, key text)"


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


def make_email_tool(database_url: str, *, block: bool = False) -> BaseTool:
    """Non-retry-safe tool whose only effect is a ``side_effects`` row (the 'provider')."""

    @tool(EMAIL_TOOL)
    async def send_email(to: str) -> str:
        """Send an email."""
        async with await psycopg.AsyncConnection.connect(database_url, autocommit=True) as conn:
            await conn.execute(
                "INSERT INTO side_effects (recipient, key) VALUES (%s, %s)",
                (to, current_idempotency_key()),
            )
        if block:
            print("STARTED", flush=True)
            await asyncio.sleep(3600)
        return f"sent to {to}"

    return send_email


class BlockingSaver(AsyncPostgresSaver):
    """Checkpointer that hangs when the tools node's results are about to be persisted."""

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        for _channel, value in writes:
            if isinstance(value, list) and any(isinstance(m, ToolMessage) for m in value):
                print("STARTED", flush=True)
                await asyncio.sleep(3600)
        await super().aput_writes(config, writes, task_id, task_path)


async def main(database_url: str, thread_id: str, lease_seconds: float, mode: str) -> None:
    call = (
        tool_call(TOOL_NAME, {"query": "ACME"}, "call-1")
        if mode == "lookup"
        else tool_call(EMAIL_TOOL, EMAIL_ARGS, "call-1")
    )
    model = ScriptedChatModel(script=[call, AIMessage(content="unused")])
    async with open_persistence(database_url) as persistence:
        checkpointer = (
            BlockingSaver(persistence.pool)
            if mode == "email-committed"
            else persistence.checkpointer
        )
        tools = [
            make_lookup_tool(block=True)
            if mode == "lookup"
            else make_email_tool(database_url, block=mode == "email-block")
        ]
        graph = build_graph(
            model,
            tools,
            checkpointer=checkpointer,
            tool_ledger=None if mode == "lookup" else persistence.tool_ledger,
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
    run_mode = sys.argv[4] if len(sys.argv) > 4 else "lookup"
    # psycopg's async API needs a selector loop on Windows (the default there is Proactor).
    asyncio.run(main(url, thread, lease, run_mode), loop_factory=asyncio.SelectorEventLoop)
