"""Chat model factory."""

from langchain_openai import ChatOpenAI

from brain_agent.config import Settings
from brain_agent.errors import ConfigurationError

# Client-level retries for a single model call; the graph adds node-level retries on top.
DEFAULT_MAX_RETRIES = 2


def create_chat_model(settings: Settings, *, max_retries: int = DEFAULT_MAX_RETRIES) -> ChatOpenAI:
    """Build the OpenAI chat model used by the agent.

    Raises:
        ConfigurationError: if ``OPENAI_API_KEY`` is not configured.
    """
    api_key = settings.openai_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        raise ConfigurationError(
            "OPENAI_API_KEY is not set; add it to the environment or the repository .env file."
        )
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=api_key,
        temperature=0,
        max_retries=max_retries,
        timeout=settings.openai_timeout_seconds,
    )
