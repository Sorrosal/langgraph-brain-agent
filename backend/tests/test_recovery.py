"""Tests for the recovery worker using in-memory doubles (no Postgres)."""

import asyncio

import pytest

from brain_agent.runtime.recovery import RecoveryWorker, recover_on_startup
from brain_agent.runtime.runner import RunResult
from tests.fakes import FakeRunLedger


class FakeResumer:
    """Records resumes; ``failing`` thread ids raise."""

    owner_id = "recovery-owner"

    def __init__(self, failing: set[str] | None = None) -> None:
        self.resumed: list[str] = []
        self.failing = failing or set()
        self.resumed_event = asyncio.Event()

    async def resume(self, thread_id: str) -> RunResult:
        self.resumed.append(thread_id)
        self.resumed_event.set()
        if thread_id in self.failing:
            raise RuntimeError(f"cannot resume {thread_id}")
        return RunResult(thread_id, "completed", "ok", ())


async def _orphans(ledger: FakeRunLedger, *thread_ids: str) -> None:
    for thread_id in thread_ids:
        await ledger.mark_running(thread_id, "dead-owner", 30)
        ledger.expire(thread_id)


def _worker(
    resumer: FakeResumer, ledger: FakeRunLedger, *, batch_size: int = 10, max_attempts: int = 3
) -> RecoveryWorker:
    return RecoveryWorker(
        resumer,
        ledger,
        interval_seconds=0.01,
        lease_seconds=30,
        max_attempts=max_attempts,
        batch_size=batch_size,
    )


async def test_run_once_resumes_every_claimed_orphan() -> None:
    ledger, resumer = FakeRunLedger(), FakeResumer()
    await _orphans(ledger, "a", "b")

    recovered = await _worker(resumer, ledger).run_once()

    assert sorted(recovered) == ["a", "b"]
    assert sorted(resumer.resumed) == ["a", "b"]
    assert ledger.records["a"].owner == "recovery-owner"
    assert ledger.records["a"].attempts == 1


async def test_run_once_without_orphans_does_nothing() -> None:
    ledger, resumer = FakeRunLedger(), FakeResumer()
    await ledger.mark_running("alive", "other", 30)

    assert await _worker(resumer, ledger).run_once() == []
    assert resumer.resumed == []


async def test_one_failing_resume_does_not_stop_the_others() -> None:
    ledger, resumer = FakeRunLedger(), FakeResumer(failing={"bad"})
    await _orphans(ledger, "first", "bad", "last")

    recovered = await _worker(resumer, ledger).run_once()

    assert sorted(recovered) == ["bad", "first", "last"]
    assert sorted(resumer.resumed) == ["bad", "first", "last"]


async def test_run_once_respects_batch_size() -> None:
    ledger, resumer = FakeRunLedger(), FakeResumer()
    await _orphans(ledger, "a", "b", "c")

    recovered = await _worker(resumer, ledger, batch_size=2).run_once()

    assert len(recovered) == 2


async def test_orphans_over_max_attempts_are_failed_not_resumed() -> None:
    ledger, resumer = FakeRunLedger(), FakeResumer()
    await _orphans(ledger, "poison")
    ledger.records["poison"].attempts = 2

    recovered = await _worker(resumer, ledger, max_attempts=2).run_once()

    assert recovered == []
    assert resumer.resumed == []
    assert ledger.records["poison"].status == "failed"


async def test_run_forever_polls_until_stopped() -> None:
    ledger, resumer = FakeRunLedger(), FakeResumer()
    worker = _worker(resumer, ledger)
    stop = asyncio.Event()
    task = asyncio.create_task(worker.run_forever(stop))

    await _orphans(ledger, "late")
    await asyncio.wait_for(resumer.resumed_event.wait(), timeout=5)
    stop.set()
    await asyncio.wait_for(task, timeout=5)

    assert resumer.resumed == ["late"]


async def test_run_forever_survives_registry_errors() -> None:
    class FlakyLedger(FakeRunLedger):
        failures = 2

        async def claim_orphans(
            self, owner: str, lease_seconds: float, limit: int, *, max_attempts: int = 3
        ) -> list[str]:
            if self.failures:
                self.failures -= 1
                raise ConnectionError("db restarting")
            return await super().claim_orphans(
                owner, lease_seconds, limit, max_attempts=max_attempts
            )

    ledger, resumer = FlakyLedger(), FakeResumer()
    await _orphans(ledger, "x")
    stop = asyncio.Event()
    task = asyncio.create_task(_worker(resumer, ledger).run_forever(stop))

    await asyncio.wait_for(resumer.resumed_event.wait(), timeout=5)
    stop.set()
    await asyncio.wait_for(task, timeout=5)


async def test_recover_on_startup_drains_all_batches() -> None:
    ledger, resumer = FakeRunLedger(), FakeResumer()
    await _orphans(ledger, "a", "b", "c", "d", "e")

    recovered = await recover_on_startup(_worker(resumer, ledger, batch_size=2))

    assert sorted(recovered) == ["a", "b", "c", "d", "e"]


async def test_recover_on_startup_stops_when_nothing_is_claimed() -> None:
    ledger, resumer = FakeRunLedger(), FakeResumer()

    assert await recover_on_startup(_worker(resumer, ledger)) == []


def test_worker_validates_settings() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        _worker(FakeResumer(), FakeRunLedger(), batch_size=0)
