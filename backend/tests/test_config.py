"""Tests for application settings."""

from collections.abc import Iterator

import pytest
from pydantic import SecretStr

from brain_agent.config import Settings, get_settings

SETTINGS_ENV_VARS = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "DATABASE_URL",
    "LOG_LEVEL",
    "ENVIRONMENT",
)


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Strip real environment values and reset the settings cache around every test."""
    for name in SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.openai_api_key is None
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.database_url == "postgresql://brain:brain@localhost:5432/brain"
    assert settings.log_level == "INFO"
    assert settings.environment == "development"


def test_reads_values_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@db:5432/other")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENVIRONMENT", "production")

    settings = Settings(_env_file=None)

    assert isinstance(settings.openai_api_key, SecretStr)
    assert settings.openai_api_key.get_secret_value() == "sk-test"
    assert settings.openai_model == "gpt-4.1"
    assert settings.database_url == "postgresql://u:p@db:5432/other"
    assert settings.log_level == "DEBUG"
    assert settings.environment == "production"


def test_api_key_is_not_leaked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret")

    settings = Settings(_env_file=None)

    assert "sk-super-secret" not in repr(settings)
    assert "sk-super-secret" not in str(settings)


def test_get_settings_is_cached() -> None:
    first = get_settings()
    second = get_settings()

    assert first is second
    assert isinstance(first, Settings)
