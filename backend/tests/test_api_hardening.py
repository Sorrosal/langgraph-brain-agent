"""Rate limits, anti-enumeration, request ids, safe failures and background supervision."""

import asyncio
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest
import structlog
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from brain_agent.api import auth
from brain_agent.api.ratelimit import RateLimiter
from brain_agent.runtime.recovery import SupervisedLoop
from brain_agent.runtime.supervisor import RunSupervisor
from tests.api_support import PASSWORD, make_settings, register, running_api
from tests.test_api_threads import new_thread, settled


def test_token_bucket_refills_over_time() -> None:
    now = [0.0]
    limiter = RateLimiter(clock=lambda: now[0])
    assert [limiter.hit("k", 2, 60) for _ in range(3)] == [None, None, 30.0]
    assert limiter.hit("other", 2, 60) is None  # keys are independent
    now[0] = 30
    assert limiter.hit("k", 2, 60) is None and limiter.hit("k", 2, 60) is not None


async def test_login_is_throttled_per_ip_and_email() -> None:
    async with running_api([], make_settings(rate_limit_login_per_minute=2)) as h:
        body = {"email": "ana@acme.com", "password": "wrong-password-1"}
        codes = [(await h.client.post("/auth/login", json=body)).status_code for _ in range(3)]
        assert codes == [401, 401, 429]
        blocked = await h.client.post("/auth/login", json=body)
        assert int(blocked.headers["Retry-After"]) >= 1
        assert blocked.json()["error"]["code"] == "rate_limited"
        other = await h.client.post("/auth/login", json={**body, "email": "bob@acme.com"})
        assert other.status_code == 401


async def test_register_and_message_limits() -> None:
    settings = make_settings(rate_limit_register_per_hour=2, rate_limit_messages_per_minute=1)
    async with running_api([AIMessage(content="a"), AIMessage(content="b")], settings) as h:
        headers = await register(h.client, "a@acme.com")
        again = {"email": "b@acme.com", "password": PASSWORD}
        assert (await h.client.post("/auth/register", json=again)).status_code == 202
        assert (await h.client.post("/auth/register", json=again)).status_code == 429

        tid = await new_thread(h, headers)
        url = f"/threads/{tid}/messages"
        assert (await h.client.post(url, json={"content": "x"}, headers=headers)).status_code == 202
        await settled(h.client, headers, tid)
        limited = await h.client.post(url, json={"content": "x"}, headers=headers)
        assert limited.status_code == 429 and "Retry-After" in limited.headers


async def test_rules_writes_are_throttled(tmp_path: Any) -> None:
    (tmp_path / "default.yaml").write_text(
        "version: 1\nhard_rules:\n  - id: r\n    description: d\n    action: block\n"
        "    when: {tool: send_email}\n",
        encoding="utf-8",
    )
    settings = make_settings(rules_dir=tmp_path, rate_limit_rules_writes_per_minute=1)
    async with running_api([], settings) as h:
        admin = await register(h.client)
        body = {"content": "x: ["}
        assert (
            await h.client.put("/rules/default.yaml", json=body, headers=admin)
        ).status_code == 422
        assert (
            await h.client.put("/rules/default.yaml", json=body, headers=admin)
        ).status_code == 429


async def test_registering_an_existing_email_looks_like_a_new_registration() -> None:
    async with running_api([]) as h:
        body = {"email": "ana@acme.com", "password": PASSWORD}
        first = await h.client.post("/auth/register", json=body)
        duplicate = await h.client.post(
            "/auth/register", json={"email": "ANA@acme.com", "password": "another-password-9"}
        )
        assert (first.status_code, first.json()) == (202, {"status": "accepted"})
        assert (duplicate.status_code, duplicate.json()) == (202, {"status": "accepted"})
        login = await h.client.post("/auth/login", json=body)
        assert login.status_code == 200  # the original password still works
        other = await h.client.post(
            "/auth/login", json={"email": "ana@acme.com", "password": "another-password-9"}
        )
        assert other.status_code == 401


async def test_argon2_verifications_are_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    active = peak = 0
    lock = threading.Lock()

    def slow_verify(password: str, hashed: str) -> bool:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return False

    monkeypatch.setattr(auth._hasher, "verify", slow_verify)
    async with running_api([], make_settings(auth_hash_concurrency=2)) as h:
        results = await asyncio.gather(
            *(
                h.client.post("/auth/login", json={"email": f"u{i}@acme.com", "password": "x"})
                for i in range(8)
            )
        )
        assert {r.status_code for r in results} == {401}
        assert peak == 2


def test_settings_bounds() -> None:
    for field, value in (
        ("jwt_ttl_minutes", 4),
        ("jwt_ttl_minutes", 1441),
        ("auth_hash_concurrency", 0),
    ):
        with pytest.raises(ValidationError):
            make_settings(**{field: value})
    assert make_settings(jwt_ttl_minutes=5).jwt_ttl_minutes == 5


async def test_request_id_is_echoed_generated_and_in_server_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with running_api([]) as h:
        headers = await register(h.client)
        echoed = await h.client.get("/health", headers={"X-Request-ID": "client-id-12345"})
        generated = await h.client.get("/health", headers={"X-Request-ID": "bad id\twith junk"})
        assert echoed.headers["X-Request-ID"] == "client-id-12345"
        assert (
            len(generated.headers["X-Request-ID"]) >= 16
            and " " not in generated.headers["X-Request-ID"]
        )

        async def explode(*args: object) -> None:
            raise RuntimeError("database password is hunter2")

        monkeypatch.setattr(h.container.threads, "list", explode)
        with structlog.testing.capture_logs() as logs:
            response = await h.client.get(
                "/threads", headers={**headers, "X-Request-ID": "trace-me-1234"}
            )
        error = response.json()["error"]
        assert response.status_code == 500
        assert error == {
            "code": "internal_error",
            "message": "Internal server error",
            "request_id": "trace-me-1234",
        }
        assert response.headers["X-Request-ID"] == "trace-me-1234"
        logged = next(e for e in logs if e["event"] == "unhandled_exception")
        assert logged["request_id"] == "trace-me-1234" and logged["exc_info"]
        assert "hunter2" not in response.text


async def test_failed_run_never_exposes_exception_text_and_clears_on_next_run() -> None:
    async with running_api([ValueError("secret-detail-xyz"), AIMessage(content="Back.")]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        await h.client.post(f"/threads/{tid}/messages", json={"content": "go"}, headers=headers)
        failed = await settled(h.client, headers, tid)
        assert failed["run"] == {"status": "failed", "error": "run_failed", "code": None}
        assert h.container.supervisor.last_failure(tid) == "run_failed"

        await h.client.post(f"/threads/{tid}/messages", json={"content": "again"}, headers=headers)
        recovered = await settled(h.client, headers, tid)
        assert recovered["run"] == {"status": "idle", "error": None, "code": None}
        assert h.container.supervisor.last_failure(tid) is None


async def test_concurrent_posts_admit_exactly_one_run(monkeypatch: pytest.MonkeyPatch) -> None:
    async with running_api([]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        delays = iter([0.01, 0.1])
        original = h.container.runner.get_pending_interrupt

        async def slow_pending(thread_id: str) -> Any:
            await asyncio.sleep(next(delays, 0))
            return await original(thread_id)

        async def instant(*args: object, **kwargs: object) -> None:
            return None

        monkeypatch.setattr(h.container.runner, "get_pending_interrupt", slow_pending)
        monkeypatch.setattr(h.container.runner, "run", instant)
        responses = await asyncio.gather(
            *(
                h.client.post(f"/threads/{tid}/messages", json={"content": "x"}, headers=headers)
                for _ in range(2)
            )
        )
        assert sorted(r.status_code for r in responses) == [202, 409]


async def test_rejected_admission_releases_the_thread() -> None:
    async with running_api([AIMessage(content="ok")]) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        bad = await h.client.post(
            f"/threads/{tid}/approvals",
            json={"decisions": {"x": {"type": "approve"}}},
            headers=headers,
        )
        assert bad.status_code == 409
        ok = await h.client.post(f"/threads/{tid}/messages", json={"content": "x"}, headers=headers)
        assert ok.status_code == 202


async def test_supervisor_records_only_safe_failure_codes() -> None:
    supervisor = RunSupervisor()

    async def boom() -> None:
        raise RuntimeError("secret")

    supervisor.start("t", lambda sink: boom())
    await asyncio.sleep(0.01)
    assert supervisor.last_failure("t") == "run_failed"


async def test_supervised_loop_restarts_a_crashing_worker_with_backoff() -> None:
    calls = 0
    running = asyncio.Event()

    async def worker(stop: asyncio.Event) -> None:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("crashed")
        running.set()
        await stop.wait()

    loop = SupervisedLoop(worker, initial_backoff=0.01, max_backoff=0.02)
    stop = asyncio.Event()
    task = asyncio.create_task(loop.run_forever(stop))
    await asyncio.wait_for(running.wait(), 1)
    assert (calls, loop.restarts, loop.healthy) == (3, 2, True)
    stop.set()
    await asyncio.wait_for(task, 1)
    assert not loop.healthy


async def test_ready_reports_degraded_when_the_recovery_worker_is_down() -> None:
    async with running_api([]) as h:
        assert (await h.client.get("/ready")).json() == {"status": "ready"}
        h.app.state.recovery_loop = SimpleNamespace(healthy=False)
        degraded = await h.client.get("/ready")
        assert (degraded.status_code, degraded.json()["status"]) == (200, "degraded")
