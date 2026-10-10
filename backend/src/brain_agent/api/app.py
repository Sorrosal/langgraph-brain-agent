"""FastAPI application factory."""

from fastapi import FastAPI

from brain_agent import __version__


def create_app() -> FastAPI:
    """Build and return the FastAPI application.

    Usable directly or via ``uvicorn brain_agent.api.app:create_app --factory``.
    """
    app = FastAPI(title="Brain Agent", version=__version__)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app
