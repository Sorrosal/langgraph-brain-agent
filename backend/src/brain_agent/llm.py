"""Chat model factory."""

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import SecretStr

from brain_agent.config import Settings
from brain_agent.errors import ConfigurationError

# Client-level retries for a single model call; the graph adds node-level retries on top.
DEFAULT_MAX_RETRIES = 2


EMBEDDING_DIMS = 1536
"""Output size of ``text-embedding-3-small``; the store index must be created with it."""


def _api_key(settings: Settings) -> SecretStr:
    api_key = settings.openai_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        raise ConfigurationError(
            "OPENAI_API_KEY is not set; add it to the environment or the repository .env file."
        )
    return api_key


def create_chat_model(settings: Settings, *, max_retries: int = DEFAULT_MAX_RETRIES) -> ChatOpenAI:
    """Build the OpenAI chat model used by the agent.

    Raises:
        ConfigurationError: if ``OPENAI_API_KEY`` is not configured.
    """
    return ChatOpenAI(
        model=settings.openai_model,
        api_key=_api_key(settings),
        temperature=0,
        max_retries=max_retries,
        timeout=settings.openai_timeout_seconds,
    )


def create_embeddings(settings: Settings) -> OpenAIEmbeddings:
    """Build the embeddings model behind semantic memory recall (``EMBEDDING_DIMS`` wide).

    Raises:
        ConfigurationError: if ``OPENAI_API_KEY`` is not configured.
    """
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        openai_api_key=_api_key(settings),
        dimensions=EMBEDDING_DIMS,
        request_timeout=settings.openai_timeout_seconds,
    )
