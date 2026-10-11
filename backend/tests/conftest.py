"""Shared fixtures: selector event loop and an isolated Postgres schema per integration test."""

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from urllib.parse import quote

import psycopg
import pytest
from _pytest.config import Config
from _pytest.nodes import Item
from psycopg import sql

from brain_agent.persistence.postgres import Persistence, open_persistence

DEFAULT_DATABASE_URL = "postgresql://brain:brain@127.0.0.1:5432/brain"


def pytest_asyncio_loop_factories(
    config: Config, item: Item
) -> dict[str, type[asyncio.AbstractEventLoop]]:
    # psycopg's async API cannot run on Windows' default ProactorEventLoop.
    return {"selector": asyncio.SelectorEventLoop}


@pytest.fixture(scope="session")
def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


@pytest.fixture(scope="session")
def _database_available(database_url: str) -> None:
    try:
        psycopg.connect(database_url, connect_timeout=3).close()
    except psycopg.OperationalError as exc:
        reason = f"PostgreSQL is not reachable at DATABASE_URL: {exc}"
        if os.environ.get("REQUIRE_INTEGRATION") == "1":
            pytest.fail(reason, pytrace=False)
        pytest.skip(reason)
    # Install pgvector once in ``public`` (as a real deployment has it) instead of letting the
    # first store setup create it inside a throwaway schema that the test then drops.
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector SCHEMA public")


def url_with_search_path(database_url: str, schema: str) -> str:
    # ``public`` stays on the path so extension types such as ``vector`` resolve.
    separator = "&" if "?" in database_url else "?"
    return f"{database_url}{separator}options={quote(f'-c search_path={schema},public')}"


@pytest.fixture
def schema_url(database_url: str, _database_available: None) -> Iterator[str]:
    """Database URL whose ``search_path`` is a throwaway schema, dropped after the test."""
    schema = f"test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        try:
            yield url_with_search_path(database_url, schema)
        finally:
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture
async def persistence(schema_url: str) -> AsyncIterator[Persistence]:
    async with open_persistence(schema_url) as opened:
        yield opened
