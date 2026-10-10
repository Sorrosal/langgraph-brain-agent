"""Tests for the minimal API app factory and health endpoint."""

import httpx
from fastapi import FastAPI

from brain_agent import __version__
from brain_agent.api.app import create_app


def test_create_app_returns_fastapi_instance() -> None:
    app = create_app()
    assert isinstance(app, FastAPI)


async def test_health_endpoint_reports_ok_and_version() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


async def test_unknown_route_returns_404() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/does-not-exist")

    assert response.status_code == 404
