"""Tests for the chat model factory (no network access)."""

import pytest
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from brain_agent.config import Settings
from brain_agent.errors import ConfigurationError
from brain_agent.llm import DEFAULT_MAX_RETRIES, create_chat_model


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
