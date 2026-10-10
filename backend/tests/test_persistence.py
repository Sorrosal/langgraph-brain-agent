"""Integration tests for the Postgres persistence layer and the run registry."""

import asyncio

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from brain_agent.errors import LeaseLostError, ThreadBusyError
from brain_agent.graph.builder import build_graph
from brain_agent.persistence.postgres import Persistence, open_persistence
from brain_agent.runtime.recovery import RecoveryWorker
from brain_agent.runtime.runner import AgentRunner
from tests.fakes import ScriptedChatModel, tool_call

pytestmark = pytest.mark.integration


async def _expire_lease(persistence: Persistence, thread_id: str) -> None:
    async with persistence.pool.connection() as conn:
        await conn.execute(
            "UPDATE agent_runs SET lease_expires_at = now() - interval '1 second' "
            "WHERE thread_id = %s",
            (thread_id,),
        )


async def test_open_persistence_exposes_ready_components(persistence: Persistence) -> None:
    await persistence.store.aput(("memories", "u1"), "k", {"fact": "likes tea"})
    item = await persistence.store.aget(("memories", "u1"), "k")
    assert item is not None
    assert item.value == {"fact": "likes tea"}

    assert await persistence.checkpointer.aget_tuple({"configurable": {"thread_id": "t"}}) is None
    assert await persistence.runs.get("nope") is None


async def test_open_persistence_is_idempotent(schema_url: str) -> None:
    async with open_persistence(schema_url):
        pass
    async with open_persistence(schema_url) as again:
        await again.runs.mark_running("t", "o", 30)
        assert (await again.runs.get("t")) is not None


async def test_mark_running_creates_a_leased_row(persistence: Persistence) -> None:
    await persistence.runs.mark_running("t1", "owner-a", 30)

    record = await persistence.runs.get("t1")

    assert record is not None
    assert (record.status, record.owner, record.attempts) == ("running", "owner-a", 0)
    assert record.lease_expires_at is not None
    assert record.last_error is None


async def test_heartbeat_only_extends_a_lease_held_by_the_owner(persistence: Persistence) -> None:
    runs = persistence.runs
    token = await runs.mark_running("t1", "owner-a", 5)
    before = await runs.get("t1")
    assert before is not None

    assert await runs.heartbeat("t1", "owner-a", token, 60) is True
    assert await runs.heartbeat("t1", "intruder", token, 60) is False
    assert await runs.heartbeat("t1", "owner-a", token + 1, 60) is False
    assert await runs.heartbeat("missing", "owner-a", token, 60) is False

    after = await runs.get("t1")
    assert after is not None
    assert before.lease_expires_at is not None
    assert after.lease_expires_at is not None
    assert after.lease_expires_at > before.lease_expires_at


async def test_mark_finished_releases_the_lease(persistence: Persistence) -> None:
    runs = persistence.runs
    token = await runs.mark_running("t1", "owner-a", 30)

    assert await runs.mark_finished("t1", "owner-a", token, "failed", error="boom") is True

    record = await runs.get("t1")
    assert record is not None
    assert (record.status, record.owner, record.lease_expires_at) == ("failed", None, None)
    assert record.last_error == "boom"
    assert await runs.heartbeat("t1", "owner-a", token, 30) is False


async def test_mark_running_resets_attempts_unless_told_otherwise(
    persistence: Persistence,
) -> None:
    runs = persistence.runs
    await runs.mark_running("t1", "dead", 30)
    await _expire_lease(persistence, "t1")
    await runs.claim_orphans("rescuer", 30, 5)

    await runs.mark_running("t1", "rescuer", 30, reset_attempts=False)
    kept = await runs.get("t1")
    await runs.mark_running("t1", "rescuer", 30)
    reset = await runs.get("t1")

    assert kept is not None
    assert reset is not None
    assert kept.attempts == 1
    assert reset.attempts == 0


async def test_fencing_token_increments_on_every_claim(persistence: Persistence) -> None:
    runs = persistence.runs
    first = await runs.mark_running("t1", "a", 30)
    again = await runs.mark_running("t1", "a", 30)
    await _expire_lease(persistence, "t1")
    assert await runs.claim_orphans("rescuer", 30, 5) == ["t1"]
    claimed = await runs.get("t1")
    taken = await runs.mark_running("t1", "rescuer", 30, reset_attempts=False)

    assert claimed is not None
    assert (first, again, claimed.fencing_token, taken) == (1, 2, 3, 4)


async def test_mark_running_refuses_a_live_foreign_lease(persistence: Persistence) -> None:
    runs = persistence.runs
    token = await runs.mark_running("t1", "a", 30)

    with pytest.raises(ThreadBusyError):
        await runs.mark_running("t1", "b", 30)
    record = await runs.get("t1")
    assert record is not None
    assert (record.owner, record.fencing_token) == ("a", token)

    await _expire_lease(persistence, "t1")
    assert await runs.mark_running("t1", "b", 30) == token + 1  # expired: takeover allowed


async def test_a_stale_owner_cannot_overwrite_status(persistence: Persistence) -> None:
    runs = persistence.runs
    stale = await runs.mark_running("t1", "a", 30)
    await _expire_lease(persistence, "t1")
    fresh = await runs.mark_running("t1", "b", 30)

    assert await runs.heartbeat("t1", "a", stale, 30) is False
    assert await runs.record_error("t1", "a", stale, "late") is False
    assert await runs.mark_finished("t1", "a", stale, "completed") is False

    record = await runs.get("t1")
    assert record is not None
    assert (record.status, record.owner, record.fencing_token) == ("running", "b", fresh)
    assert record.last_error is None
    assert await runs.mark_finished("t1", "b", fresh, "completed") is True


async def test_lease_loss_stops_a_real_run_and_leaves_the_new_owner_alone(
    persistence: Persistence,
) -> None:
    started = asyncio.Event()

    @tool
    async def slow(query: str) -> str:
        """Hang until cancelled."""
        started.set()
        await asyncio.sleep(30)
        return query

    graph = build_graph(
        ScriptedChatModel(script=[tool_call("slow", {"query": "x"}, "call-1")]),
        [slow],
        checkpointer=persistence.checkpointer,
    )
    runner = AgentRunner(
        graph, runs=persistence.runs, owner_id="old", lease_seconds=5, heartbeat_interval=0.05
    )
    task = asyncio.create_task(runner.run("t1", "go"))
    await asyncio.wait_for(started.wait(), timeout=10)
    # The old owner's heartbeat can renew the lease between expiry and takeover: expire again.
    fresh = None
    while fresh is None:
        await _expire_lease(persistence, "t1")
        try:
            fresh = await persistence.runs.mark_running("t1", "new", 30)
        except ThreadBusyError:
            await asyncio.sleep(0)

    with pytest.raises(LeaseLostError):
        await asyncio.wait_for(task, timeout=10)

    record = await persistence.runs.get("t1")
    assert record is not None
    assert (record.status, record.owner, record.fencing_token) == ("running", "new", fresh)


async def test_concurrent_persistence_setup_does_not_race(schema_url: str) -> None:
    async def open_and_close() -> None:
        async with open_persistence(schema_url) as opened:
            await opened.runs.mark_running("t", "o", 30)

    await asyncio.gather(*(open_and_close() for _ in range(3)))


async def test_status_check_constraint_rejects_unknown_values(persistence: Persistence) -> None:
    await persistence.runs.mark_running("t1", "o", 30)

    with pytest.raises(Exception, match="agent_runs_status_check"):
        async with persistence.pool.connection() as conn:
            await conn.execute("UPDATE agent_runs SET status = 'weird' WHERE thread_id = 't1'")


async def test_claim_orphans_only_takes_expired_running_runs(persistence: Persistence) -> None:
    runs = persistence.runs
    await runs.mark_running("alive", "other", 300)
    await runs.mark_running("orphan", "dead", 300)
    token = await runs.mark_running("done", "other", 300)
    await runs.mark_finished("done", "other", token, "completed")
    for thread_id in ("orphan", "done"):
        await _expire_lease(persistence, thread_id)

    claimed = await runs.claim_orphans("rescuer", 60, 10)

    assert claimed == ["orphan"]
    record = await runs.get("orphan")
    assert record is not None
    assert (record.status, record.owner, record.attempts) == ("running", "rescuer", 1)
    assert await runs.claim_orphans("rescuer", 60, 10) == []  # now leased to the rescuer


async def test_claim_orphans_respects_the_limit(persistence: Persistence) -> None:
    for i in range(3):
        await persistence.runs.mark_running(f"t{i}", "dead", 30)
        await _expire_lease(persistence, f"t{i}")

    assert len(await persistence.runs.claim_orphans("rescuer", 60, 2)) == 2
    assert len(await persistence.runs.claim_orphans("rescuer", 60, 2)) == 1


async def test_claim_orphans_fails_poison_pills(persistence: Persistence) -> None:
    runs = persistence.runs
    await runs.mark_running("poison", "dead", 30)
    for expected_attempts in (1, 2):
        await _expire_lease(persistence, "poison")
        assert await runs.claim_orphans("rescuer", 30, 5, max_attempts=2) == ["poison"]
        record = await runs.get("poison")
        assert record is not None
        assert record.attempts == expected_attempts

    await _expire_lease(persistence, "poison")
    assert await runs.claim_orphans("rescuer", 30, 5, max_attempts=2) == []

    record = await runs.get("poison")
    assert record is not None
    assert record.status == "failed"
    assert record.last_error is not None
    assert "max" in record.last_error


async def test_two_workers_cannot_claim_the_same_orphan(persistence: Persistence) -> None:
    runs = persistence.runs
    for i in range(6):
        await runs.mark_running(f"t{i}", "dead", 30)
        await _expire_lease(persistence, f"t{i}")

    first, second = await asyncio.gather(
        runs.claim_orphans("worker-1", 60, 6), runs.claim_orphans("worker-2", 60, 6)
    )

    assert sorted(first + second) == [f"t{i}" for i in range(6)]
    assert set(first).isdisjoint(second)


async def test_claim_skips_rows_locked_by_a_concurrent_claim(persistence: Persistence) -> None:
    runs = persistence.runs
    await runs.mark_running("locked", "dead", 30)
    await runs.mark_running("free", "dead", 30)
    for thread_id in ("locked", "free"):
        await _expire_lease(persistence, thread_id)

    async with persistence.pool.connection() as holder, holder.transaction():
        await holder.execute("SELECT 1 FROM agent_runs WHERE thread_id = 'locked' FOR UPDATE")

        claimed = await asyncio.wait_for(runs.claim_orphans("rescuer", 60, 10), timeout=10)

        assert claimed == ["free"]  # did not block on, or steal, the locked row

    assert await runs.claim_orphans("rescuer", 60, 10) == ["locked"]


async def test_runner_persists_threads_in_postgres(persistence: Persistence) -> None:
    model = ScriptedChatModel(script=[AIMessage(content="Hi"), AIMessage(content="Ada")])
    graph = build_graph(model, [], checkpointer=persistence.checkpointer, store=persistence.store)

    await AgentRunner(graph, runs=persistence.runs).run("t1", "I am Ada")
    # A different runner/graph (a "restarted process") sees the same thread.
    restarted = AgentRunner(
        build_graph(
            ScriptedChatModel(script=[AIMessage(content="Ada")]),
            [],
            checkpointer=persistence.checkpointer,
        ),
        runs=persistence.runs,
    )
    result = await restarted.run("t1", "who am I?")

    assert result.last_message == "Ada"
    state = await restarted.get_state("t1")
    assert len(state.values["messages"]) == 4
    record = await persistence.runs.get("t1")
    assert record is not None
    assert record.status == "completed"


async def test_run_error_semantics_are_recorded_in_postgres(persistence: Persistence) -> None:
    @tool
    def flaky(query: str) -> str:
        """Fail transiently."""
        raise ConnectionError("db down")

    model = ScriptedChatModel(script=[tool_call("flaky", {"query": "x"}, "call-1")])
    graph = build_graph(model, [flaky], checkpointer=persistence.checkpointer)
    runner = AgentRunner(graph, runs=persistence.runs)

    with pytest.raises(ConnectionError):
        await runner.run("t1", "go")

    record = await persistence.runs.get("t1")
    assert record is not None
    assert record.status == "running"
    assert record.last_error is not None
    assert "db down" in record.last_error


async def test_a_run_that_keeps_failing_is_marked_failed_after_max_attempts(
    persistence: Persistence,
) -> None:
    attempts: list[int] = []

    @tool
    def flaky(query: str) -> str:
        """Always fail transiently."""
        attempts.append(1)
        raise ConnectionError("still down")

    graph = build_graph(
        ScriptedChatModel(script=[tool_call("flaky", {"query": "x"}, "call-1")]),
        [flaky],
        checkpointer=persistence.checkpointer,
    )
    runner = AgentRunner(graph, runs=persistence.runs, owner_id="worker")
    worker = RecoveryWorker(
        runner,
        persistence.runs,
        interval_seconds=0.05,
        max_attempts=2,
        batch_size=5,
    )
    with pytest.raises(ConnectionError):
        await runner.run("poison", "go")

    recovered: list[str] = []
    for _ in range(4):
        await _expire_lease(persistence, "poison")
        recovered += await worker.run_once()

    record = await persistence.runs.get("poison")
    assert record is not None
    assert (record.status, record.attempts) == ("failed", 2)
    assert recovered == ["poison", "poison"]
    assert len(attempts) == 3  # initial run + two recovery attempts, then given up
