"""Integration tests: a process killed around a tool's side effect never repeats it."""

import asyncio
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psycopg
import pytest
from langchain_core.messages import AIMessage

from brain_agent.graph.builder import build_graph
from brain_agent.graph.nodes import TOOLS_NODE
from brain_agent.hitl.models import ConfirmDone, UncertainExecutionInterrupt
from brain_agent.persistence.postgres import Persistence
from brain_agent.runtime.recovery import RecoveryWorker
from brain_agent.runtime.runner import AgentRunner
from tests.crash_worker import EMAIL_ARGS, SIDE_EFFECTS_DDL, make_email_tool
from tests.fakes import ScriptedChatModel
from tests.test_crash_recovery import LEASE_SECONDS, STARTUP_TIMEOUT, _wait_for_line

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _spawn(database_url: str, thread_id: str, mode: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tests.crash_worker",
            database_url,
            thread_id,
            str(LEASE_SECONDS),
            mode,
        ],
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


async def _crash_child_at_marker(database_url: str, thread_id: str, mode: str) -> None:
    child = _spawn(database_url, thread_id, mode)
    try:
        started = await asyncio.to_thread(_wait_for_line, child, "STARTED", STARTUP_TIMEOUT)
        assert started, f"child never reached the crash point (exit code {child.poll()})"
        child.kill()  # hard kill: no cleanup, no finally blocks
        await asyncio.to_thread(child.wait, 30)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(30)
        if child.stdout is not None:
            child.stdout.close()


def _side_effects(database_url: str) -> list[str]:
    with psycopg.connect(database_url, autocommit=True) as conn:
        rows = conn.execute("SELECT recipient FROM side_effects ORDER BY id").fetchall()
    return [row[0] for row in rows]


async def _recover(runner: AgentRunner, persistence: Persistence, thread_id: str) -> None:
    worker = RecoveryWorker(runner, persistence.runs, interval_seconds=0.2)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if await worker.run_once() == [thread_id]:  # empty until the dead lease expires
            return
        await asyncio.sleep(0.25)
    pytest.fail("the orphaned run was never claimed")


@pytest.fixture
def side_effects_url(schema_url: str) -> str:
    with psycopg.connect(schema_url, autocommit=True) as conn:
        conn.execute(SIDE_EFFECTS_DDL)
    return schema_url


def _parent_runner(
    persistence: Persistence, schema_url: str, script: list[AIMessage | Exception]
) -> tuple[AgentRunner, ScriptedChatModel]:
    model = ScriptedChatModel(script=script)
    graph = build_graph(
        model,
        [make_email_tool(schema_url)],  # a repeated execution would insert a second row
        checkpointer=persistence.checkpointer,
        tool_ledger=persistence.tool_ledger,
    )
    runner = AgentRunner(
        graph, runs=persistence.runs, owner_id="recovery-process", lease_seconds=LEASE_SECONDS
    )
    return runner, model


async def test_crash_after_side_effect_pauses_for_a_human_instead_of_sending_again(
    persistence: Persistence, side_effects_url: str
) -> None:
    thread_id = f"email-{uuid.uuid4().hex[:8]}"
    await _crash_child_at_marker(side_effects_url, thread_id, "email-block")
    assert _side_effects(side_effects_url) == ["ops@example.com"]
    key = f"{thread_id}:call-1"
    stuck = await persistence.tool_ledger.get(key)
    assert stuck is not None and stuck.status == "started"  # outcome unknown

    runner, model = _parent_runner(persistence, side_effects_url, [AIMessage(content="Emailed.")])
    await _recover(runner, persistence, thread_id)

    assert _side_effects(side_effects_url) == ["ops@example.com"]  # not sent again
    paused = await runner.resume(thread_id)  # reconciles, no re-run
    assert paused.status == "interrupted" and paused.next_nodes == (TOOLS_NODE,)
    assert isinstance(paused.pending_interrupt, UncertainExecutionInterrupt)
    assert paused.pending_interrupt.args == EMAIL_ARGS
    row = await persistence.runs.get(thread_id)
    assert row is not None and (row.status, row.owner) == ("interrupted", None)

    done = await runner.resolve_uncertain(thread_id, ConfirmDone())

    assert (done.status, done.last_message) == ("completed", "Emailed.")
    assert _side_effects(side_effects_url) == ["ops@example.com"]
    record = await persistence.tool_ledger.get(key)
    assert record is not None and record.status == "succeeded"
    assert model.calls == 1


async def test_crash_after_ledger_commit_replays_the_stored_result_without_a_human(
    persistence: Persistence, side_effects_url: str
) -> None:
    thread_id = f"email-{uuid.uuid4().hex[:8]}"
    await _crash_child_at_marker(side_effects_url, thread_id, "email-committed")
    key = f"{thread_id}:call-1"
    committed = await persistence.tool_ledger.get(key)
    assert committed is not None and committed.status == "succeeded"
    runner, model = _parent_runner(persistence, side_effects_url, [AIMessage(content="Emailed.")])
    assert (await runner.get_state(thread_id)).next == (TOOLS_NODE,)  # tools writes were lost

    await _recover(runner, persistence, thread_id)

    state = await runner.get_state(thread_id)
    assert state.next == ()
    assert _side_effects(side_effects_url) == ["ops@example.com"]  # replayed, not re-sent
    tool_message = state.values["messages"][-2]
    assert tool_message.text == "sent to ops@example.com"
    assert state.values["messages"][-1].text == "Emailed."
    assert model.calls == 1
    row = await persistence.runs.get(thread_id)
    assert row is not None and row.status == "completed"


async def test_postgres_ledger_is_atomic_and_matches_the_in_memory_semantics(
    persistence: Persistence,
) -> None:
    ledger = persistence.tool_ledger
    await ledger.setup()  # idempotent

    first, second = await asyncio.gather(
        ledger.begin("t:c1", "t", "send_email", "h1"), ledger.begin("t:c1", "t", "send_email", "h1")
    )
    assert sorted([first.is_new, second.is_new]) == [False, True]
    assert (first.status, first.attempts) == ("started", 1)

    await ledger.complete("t:c1", {"content": "ok", "status": "success"})
    done = await ledger.get("t:c1")
    assert done is not None and (done.status, done.result) == (
        "succeeded",
        {"content": "ok", "status": "success"},
    )
    assert not (await ledger.begin("t:c1", "t", "send_email", "h1")).is_new

    await ledger.fail("t:c1", "boom")
    await ledger.restart("t:c1", "h2")
    again = await ledger.get("t:c1")
    assert again is not None and (again.status, again.attempts, again.args_hash, again.error) == (
        "started",
        2,
        "h2",
        None,
    )
    assert await ledger.get("missing") is None
