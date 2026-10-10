"""Tests for application settings."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from brain_agent import config as config_module
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


def test_env_file_paths_do_not_depend_on_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    backend_dir = Path(config_module.__file__).resolve().parents[2]
    repo_root = backend_dir.parent

    env_files = Settings.model_config["env_file"]

    assert isinstance(env_files, tuple)
    assert all(Path(path).is_absolute() for path in env_files)
    assert env_files == (repo_root / ".env", backend_dir / ".env")


def test_env_file_override_still_reads_given_file(tmp_path: Path) -> None:
    env_file = tmp_path / "test-settings.env"
    env_file.write_text("OPENAI_MODEL=gpt-from-file\nLOG_LEVEL=WARNING\n", encoding="utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.openai_model == "gpt-from-file"
    assert settings.log_level == "WARNING"


@pytest.mark.parametrize("value", ["TRACE", "verbose", ""])
def test_rejects_invalid_log_level(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("LOG_LEVEL", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("value", ["staging", "prod", ""])
def test_rejects_invalid_environment(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("ENVIRONMENT", value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
