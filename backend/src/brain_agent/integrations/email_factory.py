"""Choosing the email adapter from settings."""

from brain_agent.config import Settings
from brain_agent.integrations.email import EmailGateway
from brain_agent.integrations.memory import InMemoryEmailGateway
from brain_agent.integrations.postgres import OutboxEmailGateway, Pool
from brain_agent.integrations.smtp_imap import SmtpImapEmailGateway


def create_email_gateway(settings: Settings, pool: Pool | None) -> EmailGateway:
    """``smtp`` sends for real (validated, with a local copy when ``pool`` is given); ``outbox``
    stores mail in PostgreSQL, or in memory without a pool. Raises ``ConfigurationError``."""
    outbox = OutboxEmailGateway(pool, settings.email_from) if pool is not None else None
    if settings.email_provider == "smtp":
        return SmtpImapEmailGateway(settings, outbox)
    return outbox or InMemoryEmailGateway(settings.email_from)
