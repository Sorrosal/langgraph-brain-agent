"""FastAPI application factory."""

import asyncio
import contextlib
import signal
import threading
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager
from datetime import timedelta
from functools import partial
from types import FrameType
from typing import Any

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from brain_agent import __version__
from brain_agent.api import auth
from brain_agent.api.container import ContainerFactory, build_container
from brain_agent.api.errors import UnhandledErrorMiddleware, install_error_handlers
from brain_agent.api.ratelimit import RateLimiter
from brain_agent.api.request_id import RequestIdMiddleware
from brain_agent.api.routes import brain, data, events, threads
from brain_agent.api.security_headers import SecurityHeadersMiddleware
from brain_agent.config import Settings, get_settings
from brain_agent.observability.logging import configure_logging
from brain_agent.observability.tracing import configure_tracing, instrument_app, shutdown_tracing
from brain_agent.runtime.expiry import expire_stale_approvals, expiry_loop
from brain_agent.runtime.recovery import SupervisedLoop


def chain_handler(
    old: Any, notify: Callable[[], object]
) -> Callable[[int, FrameType | None], None]:
    """Signal handler that runs ``notify`` and then keeps the previous handler's semantics.

    ``SIG_DFL`` means the process should terminate, so the default action is restored and the
    signal re-raised; ``SIG_IGN`` stays ignored; a callable handler is called.
    """

    def handler(num: int, frame: FrameType | None) -> None:
        notify()
        if old == signal.SIG_DFL:
            signal.signal(num, signal.SIG_DFL)
            signal.raise_signal(num)
        elif callable(old):
            old(num, frame)

    return handler


@contextlib.contextmanager
def _signal_on_termination(on_signal: asyncio.Event) -> Iterator[None]:
    """Set ``on_signal`` when SIGINT/SIGTERM arrives, then defer to the previous handler.

    uvicorn waits for open connections before it runs the lifespan shutdown, so a long-lived
    event stream would block it; this fires as soon as the signal is received. Only possible
    from the main thread; elsewhere (tests, embedded servers) the explicit event is used.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    loop = asyncio.get_running_loop()
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    for sig, old in previous.items():
        signal.signal(sig, chain_handler(old, lambda: loop.call_soon_threadsafe(on_signal.set)))
    try:
        yield
    finally:
        for sig, old in previous.items():
            signal.signal(sig, old)


def create_app(
    settings: Settings | None = None, *, container_factory: ContainerFactory | None = None
) -> FastAPI:
    """Build the FastAPI application.

    Usable directly or via ``uvicorn brain_agent.api.app:create_app --factory``. The lifespan
    opens the container (``container_factory`` replaces the PostgreSQL/OpenAI one, for tests),
    starts the recovery worker and, on shutdown, cancels active runs and stops both.
    """
    settings = settings or get_settings()
    factory = container_factory or build_container
    configure_logging(settings)
    tracer_provider = configure_tracing(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.shutdown.clear()
        try:
            with _signal_on_termination(app.state.shutdown):
                async with _serve(app):
                    yield
        finally:
            if tracer_provider is not None:
                shutdown_tracing()

    @asynccontextmanager
    async def _serve(app: FastAPI) -> AsyncIterator[None]:
        async with factory(settings) as container:
            app.state.container = container
            stop = asyncio.Event()
            loop = SupervisedLoop(container.recovery.run_forever) if container.recovery else None
            app.state.recovery_loop = loop
            worker = asyncio.create_task(loop.run_forever(stop)) if loop else None
            sweep = partial(
                expire_stale_approvals,
                runs=container.runs,
                threads=container.threads,
                runner=container.runner,
                supervisor=container.supervisor,
                ttl=timedelta(hours=settings.approval_ttl_hours),
            )
            expiry = SupervisedLoop(
                expiry_loop(sweep, settings.approval_sweep_seconds), name="approval-expiry"
            )
            expiry_worker = asyncio.create_task(expiry.run_forever(stop))
            try:
                yield
            finally:
                app.state.shutdown.set()
                stop.set()
                container.events.close()  # ends the open event streams
                await container.supervisor.shutdown()
                for task in (worker, expiry_worker):
                    if task:
                        task.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await task

    app = FastAPI(title="Brain Agent", version=__version__, lifespan=lifespan)
    app.state.limiter = RateLimiter(max_buckets=settings.rate_limit_max_buckets)
    app.state.shutdown = asyncio.Event()
    app.state.hash_gate = asyncio.Semaphore(settings.auth_hash_concurrency)
    app.state.recovery_loop = None
    # Innermost first: the error catcher needs the request id, and 500s must pass through CORS.
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    if tracer_provider is not None:
        instrument_app(app, tracer_provider)
    app.include_router(auth.router)
    app.include_router(threads.router)
    app.include_router(events.router)
    app.include_router(brain.router)
    app.include_router(data.router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/ready")
    async def ready(response: Response) -> dict[str, str]:
        """``ready`` when serving; ``degraded`` (still 200) when the recovery worker is down."""
        container = getattr(app.state, "container", None)
        try:
            if container is None:
                raise RuntimeError("not started")
            await container.ping()
            if not container.rules.ruleset.hard_rules:
                raise RuntimeError("no rules loaded")
        except Exception:
            response.status_code = 503
            return {"status": "unavailable"}
        loop = app.state.recovery_loop
        if loop is not None and not loop.healthy:
            return {"status": "degraded", "detail": "recovery worker is not running"}
        return {"status": "ready"}

    return app
