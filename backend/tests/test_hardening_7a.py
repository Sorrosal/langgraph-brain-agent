"""Phase 7a: bounded rate limiter, shutdown, terminal events, safe errors, headers, telemetry."""

import asyncio
import io
import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool, tool
from langgraph.checkpoint.memory import InMemorySaver
from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from brain_agent.api.ratelimit import RateLimiter
from brain_agent.errors import (
    IntegrationError,
    InvalidApprovalError,
    ThreadBusyError,
    safe_error,
)
from brain_agent.graph.builder import build_graph
from brain_agent.hitl import ApprovalResponse
from brain_agent.observability import tracing
from brain_agent.observability.logging import configure_logging
from brain_agent.runtime.runner import AgentRunner
from tests.api_support import make_settings, register, running_api
from tests.fakes import FakeRunLedger, InMemoryToolLedger, ScriptedChatModel, tool_call
from tests.test_api_threads import new_thread


def test_rate_limiter_caps_buckets_with_lru_eviction() -> None:
    limiter = RateLimiter(max_buckets=3)
    for key in ("a", "b", "c"):
        limiter.hit(key, 5, 60)
    limiter.hit("a", 5, 60)  # "a" is now the most recently used
    limiter.hit("d", 5, 60)  # evicts "b", the least recently used
    assert limiter.size == 3
    assert limiter.has("a") and not limiter.has("b")
    for n in range(50):
        limiter.hit(f"k{n}", 5, 60)
    assert limiter.size == 3


def test_rate_limiter_drops_refilled_idle_buckets() -> None:
    now = [0.0]
    limiter = RateLimiter(max_buckets=100, clock=lambda: now[0])
    for n in range(10):
        limiter.hit(f"k{n}", 2, 60)  # each is one token short
    now[0] = 61
    limiter.hit("fresh", 2, 60)
    assert limiter.size == 1


async def test_login_is_also_limited_per_ip_across_emails() -> None:
    settings = make_settings(rate_limit_login_per_minute=2, rate_limit_login_ip_per_minute=3)
    async with running_api([], settings) as h:
        codes = []
        for n in range(5):
            body = {"email": f"u{n}@acme.com", "password": "wrong-password-1"}
            codes.append((await h.client.post("/auth/login", json=body)).status_code)
        assert codes == [401, 401, 401, 429, 429]


async def test_shutdown_signal_ends_open_streams_promptly() -> None:
    async with running_api([], make_settings(sse_heartbeat_seconds=30)) as h:
        headers = await register(h.client)
        tid = await new_thread(h, headers)
        stream = h.sse(f"/threads/{tid}/events", headers)
        async with stream:
            await asyncio.sleep(0.01)
            h.app.state.shutdown.set()  # what the shutdown hook does before connections drain
            await asyncio.wait_for(stream.wait_finished(), 1)
        assert stream.finished


async def test_busy_thread_does_not_publish_run_failed() -> None:
    # The owner of the live run emits its own terminal event; a rejected caller must not
    # make clients watching that run believe it failed.
    ledger = FakeRunLedger()
    await ledger.mark_running("t", "someone-else", 30)
    graph = build_graph(
        ScriptedChatModel(script=[AIMessage(content="x")]), [], checkpointer=InMemorySaver()
    )
    runner = AgentRunner(graph, runs=ledger, owner_id="me")
    events: list[tuple[str, dict[str, Any]]] = []

    with pytest.raises(ThreadBusyError):
        await runner.run("t", "hi", sink=lambda kind, data: events.append((kind, data)))

    assert events == []


async def test_early_failure_publishes_run_failed() -> None:
    @tool
    def wire_money(amount: int) -> str:
        """Send money."""
        return "sent"

    wire_money.metadata = {"risk": "high"}
    model = ScriptedChatModel(script=[tool_call("wire_money", {"amount": 1}, "c1")])
    graph = build_graph(model, [wire_money], checkpointer=InMemorySaver())
    runner = AgentRunner(graph, runs=FakeRunLedger(), owner_id="me")
    paused = await runner.run("t", "pay")
    assert paused.pending_approval is not None
    events: list[tuple[str, dict[str, Any]]] = []

    with pytest.raises(InvalidApprovalError):
        await runner.approve(
            "t",
            ApprovalResponse(decisions={}),
            sink=lambda kind, data: events.append((kind, data)),
        )

    assert [k for k, _ in events] == ["run_failed"]


def test_safe_error_keeps_integration_messages_only() -> None:
    assert safe_error(IntegrationError("smtp down")) == "IntegrationError: smtp down"
    assert len(safe_error(IntegrationError("x" * 500))) < 230
    assert safe_error(ValueError("password=hunter2")) == "ValueError"


async def test_failed_work_never_stores_raw_exception_text() -> None:
    ledger, tools, saver = FakeRunLedger(), InMemoryToolLedger(), InMemorySaver()

    @tool
    def leaky(query: str) -> str:
        """Fail with a secret in the message."""
        raise ValueError("token=sk-secret-123")

    def runner(script: list[AIMessage]) -> AgentRunner:
        graph = build_graph(
            ScriptedChatModel(script=script), [leaky], checkpointer=saver, tool_ledger=tools
        )
        return AgentRunner(graph, runs=ledger, owner_id="o")

    with pytest.raises(ValueError, match="sk-secret"):
        await runner([tool_call("leaky", {"query": "x"}, "call-1")]).run("t", "go")
    record = await tools.get("t:call-1")
    assert record is not None and "sk-secret" not in str(record.error)
    assert "sk-secret" not in (ledger.records["t"].last_error or "")

    again = runner([AIMessage(content="ok")])
    await again.run("t", "again")
    state = await again.get_state("t")
    closing = [m for m in state.values["messages"] if isinstance(m, ToolMessage)]
    assert closing and all("sk-secret" not in m.text for m in closing)


async def test_500_responses_carry_cors_and_security_headers() -> None:
    async with running_api([]) as h:

        @h.app.get("/boom")
        async def boom() -> None:
            raise RuntimeError("secret internals")

        response = await h.client.get("/boom", headers={"Origin": "http://localhost:5173"})
        assert response.status_code == 500
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "secret internals" not in response.text
        assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


async def test_security_headers_on_api_but_sse_keeps_no_cache() -> None:
    async with running_api([]) as h:
        headers = await register(h.client)
        me = await h.client.get("/auth/me", headers=headers)
        assert me.headers["x-content-type-options"] == "nosniff"
        assert me.headers["referrer-policy"] == "no-referrer"
        assert me.headers["x-frame-options"] == "DENY"
        assert me.headers["cache-control"] == "no-store"
        tid = await new_thread(h, headers)
        async with h.sse(f"/threads/{tid}/events", headers) as stream:
            assert stream.headers["cache-control"] == "no-cache"
            assert stream.headers["x-content-type-options"] == "nosniff"


@pytest.fixture
def clean_logging() -> Iterator[None]:
    yield
    configure_logging(make_settings(log_format="console"), io.StringIO())
    structlog.reset_defaults()


async def test_json_logs_carry_request_id_and_stdlib_is_routed(clean_logging: None) -> None:
    stream = io.StringIO()
    configure_logging(make_settings(log_format="json"), stream)
    with structlog.contextvars.bound_contextvars(request_id="req-12345678"):
        structlog.get_logger("t").info("inside", thread_id="th1")
        logging.getLogger("stdlib.lib").warning("from stdlib")
    lines = [json.loads(line) for line in stream.getvalue().splitlines() if line.startswith("{")]
    inside = next(entry for entry in lines if entry["event"] == "inside")
    assert inside["request_id"] == "req-12345678" and inside["thread_id"] == "th1"
    assert inside["level"] == "info" and "timestamp" in inside
    stdlib = next(entry for entry in lines if entry["event"] == "from stdlib")
    assert stdlib["request_id"] == "req-12345678" and stdlib["level"] == "warning"


def test_log_format_defaults_follow_the_environment() -> None:
    assert make_settings(environment="production").effective_log_format == "json"
    assert make_settings(environment="development").effective_log_format == "console"
    assert make_settings(log_format="json", environment="test").effective_log_format == "json"


@pytest.fixture
def telemetry() -> Iterator[tuple[InMemorySpanExporter, InMemoryMetricReader]]:
    exporter, reader = InMemorySpanExporter(), InMemoryMetricReader()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracing.install(provider, MeterProvider(metric_readers=[reader]))
    yield exporter, reader
    tracing.install(None, None)


def test_tracing_is_disabled_by_default() -> None:
    assert tracing.configure_tracing(make_settings()) is None
    assert not tracing.enabled()
    assert not isinstance(trace.get_tracer_provider(), TracerProvider)


async def test_a_run_produces_runner_and_tool_spans_and_counters(
    telemetry: tuple[InMemorySpanExporter, InMemoryMetricReader],
) -> None:
    exporter, reader = telemetry

    def echo(query: str) -> str:
        """Echo."""
        return query

    echo_tool = StructuredTool.from_function(echo, metadata={"retry_safe": True})

    graph = build_graph(
        ScriptedChatModel(
            script=[tool_call("echo", {"query": "x"}, "c1"), AIMessage(content="done")]
        ),
        [echo_tool],
        checkpointer=InMemorySaver(),
        tool_ledger=InMemoryToolLedger(),
    )
    await AgentRunner(graph, runs=FakeRunLedger(), owner_id="o").run("thread-7", "go")

    spans = {s.name: s for s in exporter.get_finished_spans()}
    run = spans["agent.run"].attributes or {}
    assert run["thread_id"] == "thread-7" and run["operation"] == "run"
    assert run["outcome"] == "ok"
    call = spans["tool.execute"].attributes or {}
    assert call["tool.name"] == "echo" and call["tool.retry_safe"] is True
    assert call["ledger.outcome"] == "executed"
    data = reader.get_metrics_data()
    assert data is not None
    points = {
        m.name: [dict(p.attributes or {}) for p in m.data.data_points]
        for rm in data.resource_metrics
        for sm in rm.scope_metrics
        for m in sm.metrics
    }
    assert "brain_agent.runs.started" in points
    assert {"status": "completed"} in points["brain_agent.runs.completed"]
    assert {"outcome": "executed"} in points["brain_agent.tool_executions"]
