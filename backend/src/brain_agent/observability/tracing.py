"""Optional OpenTelemetry tracing and metrics.

Disabled unless ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set: the default :class:`Telemetry` is built
from the API's no-op providers, so instrumented code costs next to nothing. The provider is
held here rather than in OpenTelemetry's process-global slot, which can only be set once.
Exception messages are never recorded on spans (they may hold secrets).
"""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from opentelemetry.metrics import MeterProvider, NoOpMeterProvider
from opentelemetry.sdk.metrics import MeterProvider as SdkMeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NoOpTracerProvider, TracerProvider
from opentelemetry.util.types import AttributeValue

from brain_agent.config import Settings

SERVICE_NAME = "brain-agent"


class Telemetry:
    """The tracer and counters the application records to."""

    def __init__(
        self, tracer_provider: TracerProvider | None, meter_provider: MeterProvider | None
    ) -> None:
        self.enabled = tracer_provider is not None or meter_provider is not None
        self.tracer = (tracer_provider or NoOpTracerProvider()).get_tracer(SERVICE_NAME)
        meter = (meter_provider or NoOpMeterProvider()).get_meter(SERVICE_NAME)
        self.runs_started = meter.create_counter("brain_agent.runs.started")
        self.runs_completed = meter.create_counter("brain_agent.runs.completed")
        self.tool_executions = meter.create_counter("brain_agent.tool_executions")


_telemetry = Telemetry(None, None)
_sdk_providers: list[Any] = []


def install(tracer_provider: TracerProvider | None, meter_provider: MeterProvider | None) -> None:
    """Replace the active telemetry (``None, None`` restores the no-op one)."""
    global _telemetry
    _telemetry = Telemetry(tracer_provider, meter_provider)


def telemetry() -> Telemetry:
    return _telemetry


def enabled() -> bool:
    return _telemetry.enabled


def configure_tracing(settings: Settings) -> SdkTracerProvider | None:
    """Install OTLP/HTTP tracing and metrics when an endpoint is configured; else do nothing."""
    endpoint = settings.otel_exporter_otlp_endpoint
    if not endpoint:
        return None
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    base = endpoint.rstrip("/")
    resource = Resource.create({"service.name": SERVICE_NAME})
    tracer_provider = SdkTracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(f"{base}/v1/traces")))
    meter_provider = SdkMeterProvider(
        resource=resource,
        metric_readers=[PeriodicExportingMetricReader(OTLPMetricExporter(f"{base}/v1/metrics"))],
    )
    _sdk_providers[:] = [tracer_provider, meter_provider]
    install(tracer_provider, meter_provider)
    return tracer_provider


def instrument_app(app: Any, tracer_provider: SdkTracerProvider) -> None:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)


def shutdown_tracing() -> None:
    """Flush and stop the providers created by :func:`configure_tracing`."""
    providers, _sdk_providers[:] = list(_sdk_providers), []
    install(None, None)
    for provider in providers:
        provider.shutdown()


@dataclass
class RunObservation:
    """Outcome holder for a runner span; ``outcome`` is written to the span on exit."""

    outcome: str = "ok"


@contextmanager
def observe_run(thread_id: str, operation: str) -> Iterator[RunObservation]:
    t = _telemetry
    t.runs_started.add(1, {"operation": operation})
    observation = RunObservation()
    attributes: dict[str, AttributeValue] = {"thread_id": thread_id, "operation": operation}
    with t.tracer.start_as_current_span(
        "agent.run", attributes=attributes, record_exception=False, set_status_on_exception=False
    ) as span:
        try:
            yield observation
        except BaseException as exc:
            if observation.outcome == "ok":
                cancelled = isinstance(exc, asyncio.CancelledError)
                observation.outcome = "cancelled" if cancelled else "failed"
            t.runs_completed.add(1, {"status": observation.outcome})
            raise
        finally:
            span.set_attribute("outcome", observation.outcome)


@dataclass
class ToolObservation:
    """Ledger outcome of a tool call: executed, replayed, escalated or failed."""

    outcome: str = "executed"


@contextmanager
def observe_tool(name: str, retry_safe: bool) -> Iterator[ToolObservation]:
    t = _telemetry
    observation = ToolObservation()
    attributes: dict[str, AttributeValue] = {"tool.name": name, "tool.retry_safe": retry_safe}
    with t.tracer.start_as_current_span(
        "tool.execute", attributes=attributes, record_exception=False, set_status_on_exception=False
    ) as span:
        try:
            yield observation
        finally:
            span.set_attribute("ledger.outcome", observation.outcome)
            t.tool_executions.add(1, {"outcome": observation.outcome})
