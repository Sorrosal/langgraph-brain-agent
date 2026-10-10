"""Integration test: a real process crash (SIGKILL-style) loses no state."""

import asyncio
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from brain_agent.graph.builder import build_graph
from brain_agent.graph.nodes import TOOLS_NODE
from brain_agent.persistence.postgres import Persistence
from brain_agent.runtime.recovery import RecoveryWorker
from brain_agent.runtime.runner import AgentRunner
from tests.crash_worker import make_lookup_tool
from tests.fakes import ScriptedChatModel

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[1]
LEASE_SECONDS = 2.0
STARTUP_TIMEOUT = 60.0


def _spawn_crash_worker(database_url: str, thread_id: str) -> subprocess.Popen[str]:
    # Plain Popen rather than asyncio subprocesses: those need the Proactor loop on Windows,
    # which psycopg cannot use.
    return subprocess.Popen(
        [sys.executable, "-m", "tests.crash_worker", database_url, thread_id, str(LEASE_SECONDS)],
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _wait_for_line(proc: subprocess.Popen[str], expected: str, timeout: float) -> bool:
    """Block until the child prints ``expected``; a reader thread keeps the wait bounded."""
    seen = threading.Event()

    def read() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            if line.strip() == expected:
                seen.set()
                return

    threading.Thread(target=read, daemon=True).start()
    return seen.wait(timeout)


async def test_run_killed_mid_tool_is_resumed_by_another_process(
    persistence: Persistence, schema_url: str
) -> None:
    thread_id = f"crash-{uuid.uuid4().hex[:8]}"
    child = _spawn_crash_worker(schema_url, thread_id)
    try:
        started = await asyncio.to_thread(_wait_for_line, child, "STARTED", STARTUP_TIMEOUT)
        assert started, f"child never reached the tool (exit code {child.poll()})"
        child.kill()  # hard kill: no cleanup, no finally blocks, no graceful shutdown
        await asyncio.to_thread(child.wait, 30)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(30)
        if child.stdout is not None:
            child.stdout.close()

    # The child's run is checkpointed mid-flight: next up is the tools node, row is leased.
    crashed = await persistence.runs.get(thread_id)
    assert crashed is not None
    assert (crashed.status, crashed.owner, crashed.attempts) == ("running", "crash-worker", 0)

    parent_model = ScriptedChatModel(script=[AIMessage(content="ACME found.")])
    invocations: list[str] = []
    graph = build_graph(
        parent_model,
        [make_lookup_tool(block=False, invocations=invocations)],
        checkpointer=persistence.checkpointer,
    )
    runner = AgentRunner(
        graph, runs=persistence.runs, owner_id="recovery-process", lease_seconds=LEASE_SECONDS
    )
    pending = await runner.get_state(thread_id)
    assert pending.next == (TOOLS_NODE,)
    worker = RecoveryWorker(
        runner,
        persistence.runs,
        interval_seconds=0.2,
        max_attempts=3,
        batch_size=10,
    )

    recovered: list[str] = []
    deadline = time.monotonic() + 30
    while not recovered and time.monotonic() < deadline:
        recovered = await worker.run_once()  # empty until the dead process's lease expires
        if not recovered:
            await asyncio.sleep(0.25)

    assert recovered == [thread_id]
    state = await runner.get_state(thread_id)
    assert state.next == ()
    messages = state.values["messages"]
    assert [type(m) for m in messages] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
    assert messages[2].text == "record for ACME"
    assert messages[-1].text == "ACME found."
    # The checkpointed reasoning step was not replayed: only the final answer needed the model.
    assert parent_model.calls == 1
    assert any(isinstance(m, ToolMessage) for m in parent_model.inputs[0])
    assert invocations == ["ACME"]
    record = await persistence.runs.get(thread_id)
    assert record is not None
    assert (record.status, record.attempts) == ("completed", 1)
