"""Application settings loaded from environment variables (and an optional ``.env`` file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py -> brain_agent -> src -> backend
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

# Resolved from this file rather than the working directory. Later files take priority,
# so a ``backend/.env`` overrides the repository-level ``.env``.
ENV_FILES = (REPO_ROOT / ".env", BACKEND_DIR / ".env")

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    """Runtime configuration for the Brain Agent backend."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 60
    database_url: str = "postgresql://brain:brain@127.0.0.1:5432/brain"
    log_level: LogLevel = "INFO"
    environment: Environment = "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` instance (built once, then cached)."""
    return Settings()
