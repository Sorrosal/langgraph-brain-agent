"""Tests for the chat model factory (no network access)."""

import pytest
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from brain_agent.config import Settings
from brain_agent.errors import ConfigurationError
from brain_agent.llm import (
    DEFAULT_MAX_RETRIES,
    EMBEDDING_DIMS,
    create_chat_model,
    create_embeddings,
)


@pytest.fixture(autouse=True)
def _no_ambient_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


@pytest.mark.parametrize("key", [None, SecretStr(""), SecretStr("   ")])
def test_missing_api_key_raises_configuration_error(key: SecretStr | None) -> None:
    settings = Settings(_env_file=None, openai_api_key=key)

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        create_chat_model(settings)


def test_returns_configured_chat_openai() -> None:
    settings = Settings(_env_file=None, openai_api_key=SecretStr("sk-test"), openai_model="gpt-4.1")

    model = create_chat_model(settings)

    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "gpt-4.1"
    assert model.temperature == 0
    assert model.max_retries == DEFAULT_MAX_RETRIES
    assert isinstance(model.openai_api_key, SecretStr)
    assert model.openai_api_key.get_secret_value() == "sk-test"


def test_request_timeout_comes_from_settings() -> None:
    settings = Settings(_env_file=None, openai_api_key=SecretStr("sk-test"))
    assert create_chat_model(settings).request_timeout == 60

    custom = Settings(
        _env_file=None, openai_api_key=SecretStr("sk-test"), openai_timeout_seconds=12.5
    )
    assert create_chat_model(custom).request_timeout == 12.5


def test_embeddings_use_configured_model_and_fixed_dimensions() -> None:
    settings = Settings(_env_file=None, openai_api_key=SecretStr("sk-test"))

    embeddings = create_embeddings(settings)

    assert embeddings.model == "text-embedding-3-small"
    assert embeddings.dimensions == EMBEDDING_DIMS == 1536
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        create_embeddings(Settings(_env_file=None, openai_api_key=None))


def test_context_and_memory_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert (settings.context_max_tokens, settings.context_keep_last_messages) == (12000, 12)
    assert settings.memory_recall_limit == 5
    assert settings.memory_extraction_enabled is True
