"""Application settings loaded from environment variables (and an optional ``.env`` file)."""

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

import structlog
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from brain_agent.errors import ConfigurationError

logger = structlog.get_logger(__name__)

MIN_JWT_SECRET_LENGTH = 32

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
    openai_embedding_model: str = "text-embedding-3-small"
    context_max_tokens: int = 12000
    """Approximate token budget of the conversation before older messages are summarised."""
    context_keep_last_messages: int = 12
    """Most recent messages that are never summarised away."""
    memory_recall_limit: int = 5
    memory_extraction_enabled: bool = True
    """Extract durable memories from each finished turn (one extra model call per turn)."""
    email_provider: Literal["outbox", "smtp"] = "outbox"
    """``outbox`` stores mail in PostgreSQL (nothing leaves the system); ``smtp`` really sends."""
    email_from: str = "agent@acme.com"
    smtp_host: str | None = None
    smtp_port: int = 465
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_security: Literal["ssl", "starttls", "none"] = "ssl"
    """``none`` (plain text) is only accepted for localhost."""
    imap_host: str | None = None
    imap_port: int = 993
    imap_username: str | None = None
    imap_password: SecretStr | None = None
    email_timeout_seconds: float = 20
    rules_dir: Path = REPO_ROOT / "rules"
    """Directory of ``*.yaml`` rule files (see ``rules/README.md``)."""
    jwt_secret: SecretStr | None = None
    """HS256 signing key. Required (32+ characters) in production; development generates one."""
    jwt_ttl_minutes: int = Field(default=60, ge=5, le=1440)
    auth_hash_concurrency: int = Field(default=4, ge=1)
    """Password hashes/verifications (argon2 is CPU- and memory-hungry) running at once."""
    rate_limit_login_per_minute: int = Field(default=10, ge=1)
    """Per client IP and email."""
    rate_limit_register_per_hour: int = Field(default=5, ge=1)
    """Per client IP."""
    rate_limit_messages_per_minute: int = Field(default=30, ge=1)
    """Per user."""
    rate_limit_rules_writes_per_minute: int = Field(default=10, ge=1)
    """Per user. All limits are in-process: with several replicas each one counts alone."""
    rate_limit_login_ip_per_minute: int = Field(default=30, ge=1)
    """Per client IP across all emails (the per-email limit above is checked as well)."""
    rate_limit_max_buckets: int = Field(default=10_000, ge=1)
    """Upper bound of in-memory rate-limit buckets; the least recently used are evicted."""
    sse_heartbeat_seconds: float = Field(default=15, gt=0)
    """Idle time after which an event stream sends a keep-alive comment."""
    allow_registration: bool | None = None
    """Open self-registration; unset means enabled in development only (never in production)."""
    cors_origins: list[str] = ["http://localhost:5173"]
    log_format: Literal["json", "console"] | None = None
    """Unset means ``json`` in production and ``console`` elsewhere."""
    otel_exporter_otlp_endpoint: str | None = None
    """OTLP/HTTP base URL (e.g. ``http://collector:4318``); unset disables OpenTelemetry."""

    @property
    def effective_log_format(self) -> Literal["json", "console"]:
        if self.log_format is not None:
            return self.log_format
        return "json" if self.environment == "production" else "console"

    @property
    def registration_enabled(self) -> bool:
        if self.allow_registration is None:
            return self.environment == "development"
        return self.allow_registration

    @model_validator(mode="after")
    def _resolve_jwt_secret(self) -> Self:
        secret = self.jwt_secret.get_secret_value() if self.jwt_secret else ""
        if self.environment == "production":
            if len(secret) < MIN_JWT_SECRET_LENGTH:
                raise ConfigurationError(
                    f"JWT_SECRET must be set to at least {MIN_JWT_SECRET_LENGTH} characters "
                    "in production."
                )
        elif not secret:
            logger.warning("jwt_secret_generated", detail="tokens are invalid after a restart")
            self.jwt_secret = SecretStr(secrets.token_urlsafe(48))
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide :class:`Settings` instance (built once, then cached)."""
    return Settings()
