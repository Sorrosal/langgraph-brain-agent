"""FastAPI application factory."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from brain_agent import __version__
from brain_agent.api import auth
from brain_agent.api.container import ContainerFactory, build_container
from brain_agent.api.errors import install_error_handlers
from brain_agent.api.ratelimit import RateLimiter
from brain_agent.api.request_id import RequestIdMiddleware
from brain_agent.api.routes import brain, data, events, threads
from brain_agent.config import Settings, get_settings
from brain_agent.runtime.recovery import SupervisedLoop


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

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with factory(settings) as container:
            app.state.container = container
            stop = asyncio.Event()
            loop = SupervisedLoop(container.recovery.run_forever) if container.recovery else None
            app.state.recovery_loop = loop
            worker = asyncio.create_task(loop.run_forever(stop)) if loop else None
            try:
                yield
            finally:
                stop.set()
                container.events.close()  # ends the open event streams
                await container.supervisor.shutdown()
                if worker:
                    worker.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await worker

    app = FastAPI(title="Brain Agent", version=__version__, lifespan=lifespan)
    app.state.limiter = RateLimiter()
    app.state.hash_gate = asyncio.Semaphore(settings.auth_hash_concurrency)
    app.state.rules_lock = asyncio.Lock()
    app.state.recovery_loop = None
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
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
