"""Real mail through the standard library: SMTP to send, IMAP to read the inbox.

SMTP has no idempotency, so a crash between "message accepted" and "result recorded" leaves the
outcome unknown: ``retry_safe`` is ``False`` and the tool ledger escalates that to a human. The
deterministic ``Message-ID`` and ``X-Idempotency-Key`` headers let that human (or the recipient's
server) recognise a duplicate. Errors carry only the failure type, never server replies that
could echo credentials.
"""

import asyncio
import contextlib
import hashlib
import html
import imaplib
import re
import smtplib
import ssl
from datetime import UTC, datetime
from email import message_from_bytes, policy
from email.message import EmailMessage as MimeMessage
from email.message import Message
from email.utils import formatdate, getaddresses, parseaddr, parsedate_to_datetime
from typing import Any

import structlog

from brain_agent.config import Settings
from brain_agent.errors import ConfigurationError, IntegrationError, NotFoundError
from brain_agent.integrations.email import (
    EmailMessage,
    Folder,
    OutgoingEmail,
    SendResult,
    message_id_for,
    normalize_address,
)
from brain_agent.integrations.postgres import OutboxEmailGateway

logger = structlog.get_logger(__name__)

LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_UNSAFE_QUERY_CHARS = re.compile(r"[\x00-\x20\x7f]+")
_TAGS = re.compile(r"<[^>]*>")
_HIDDEN_BLOCKS = re.compile(r"<(style|script)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)


def validate_smtp_settings(settings: Settings) -> None:
    if not settings.smtp_host:
        raise ConfigurationError("smtp_host is required when email_provider is 'smtp'")
    if settings.smtp_security == "none" and settings.smtp_host not in LOCAL_HOSTS:
        raise ConfigurationError("smtp_security 'none' is only allowed for localhost")
    if settings.smtp_username and settings.smtp_password is None:
        raise ConfigurationError("smtp_password is required when smtp_username is set")


def quote_imap_string(query: str) -> str:
    """``query`` as one IMAP quoted string: control characters (CR/LF included) become spaces,
    non-ASCII is dropped, and backslash and quote are escaped, so it cannot end the command."""
    ascii_query = query.encode("ascii", "ignore").decode()
    flat = _UNSAFE_QUERY_CHARS.sub(" ", ascii_query).strip()
    return '"' + flat.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _address(value: str) -> str:
    try:
        return normalize_address(value)
    except ValueError:
        return value.strip()


def _html_to_text(markup: str) -> str:
    text = html.unescape(_TAGS.sub(" ", _HIDDEN_BLOCKS.sub(" ", markup)))
    return re.sub(r"\s+", " ", text).strip()


def _body_text(message: Message) -> str:
    body = message.get_body(preferencelist=("plain", "html"))  # type: ignore[attr-defined]
    if body is None:
        return ""
    content = str(body.get_content())
    return content.strip() if body.get_content_type() == "text/plain" else _html_to_text(content)


def parse_message(uid: str, raw: bytes) -> EmailMessage:
    message = message_from_bytes(raw, policy=policy.default)
    try:
        received = parsedate_to_datetime(str(message["Date"]))
    except (TypeError, ValueError):
        received = datetime.now(UTC)

    def addresses(header: str) -> list[str]:
        return [_address(a) for _, a in getaddresses(message.get_all(header, [])) if a]

    return EmailMessage(
        id=uid,
        message_id_header=str(message["Message-ID"] or ""),
        from_=_address(parseaddr(str(message["From"] or ""))[1]),
        to=addresses("To"),
        cc=addresses("Cc"),
        subject=str(message["Subject"] or ""),
        body_text=_body_text(message),
        received_at=received,
        folder="inbox",
    )


class SmtpImapEmailGateway:
    """Sends over SMTP and reads the INBOX over IMAP; the "sent" folder is the local outbox
    table (when a pool-backed ``outbox`` is given) that also keeps a copy of every send."""

    provider = "smtp"
    retry_safe = False

    def __init__(self, settings: Settings, outbox: OutboxEmailGateway | None = None) -> None:
        validate_smtp_settings(settings)
        self._settings = settings
        self._outbox = outbox

    # --- sending ---------------------------------------------------------------------------

    async def send(self, email: OutgoingEmail, *, idempotency_key: str) -> SendResult:
        header = message_id_for(idempotency_key)
        await asyncio.to_thread(self._send_sync, email, idempotency_key, header)
        message_id = hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]
        if self._outbox is not None:
            try:
                message_id = (await self._outbox.send(email, idempotency_key=idempotency_key)).id
            except Exception as exc:  # the mail is out; a lost audit copy must not fail the send
                logger.warning("email_copy_failed", error=type(exc).__name__)
        return SendResult(
            id=message_id, message_id_header=header, provider=self.provider, deduplicated=False
        )

    def _send_sync(self, email: OutgoingEmail, key: str, header: str) -> None:
        s = self._settings
        message = MimeMessage()
        message["From"] = s.email_from
        message["To"] = ", ".join(email.to)
        if email.cc:
            message["Cc"] = ", ".join(email.cc)
        message["Subject"] = email.subject
        message["Date"] = formatdate()
        message["Message-ID"] = header
        message["X-Idempotency-Key"] = key
        if email.reply_to_message_id:
            message["In-Reply-To"] = email.reply_to_message_id
            message["References"] = email.reply_to_message_id
        message.set_content(email.body_text)
        recipients = list(dict.fromkeys([*email.to, *email.cc]))
        try:
            assert s.smtp_host is not None
            if s.smtp_security == "ssl":
                client: smtplib.SMTP = smtplib.SMTP_SSL(
                    s.smtp_host,
                    s.smtp_port,
                    timeout=s.email_timeout_seconds,
                    context=ssl.create_default_context(),
                )
            else:
                client = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.email_timeout_seconds)
            with client:
                if s.smtp_security == "starttls":
                    client.starttls(context=ssl.create_default_context())
                if s.smtp_username and s.smtp_password:
                    client.login(s.smtp_username, s.smtp_password.get_secret_value())
                client.send_message(message, from_addr=_address(s.email_from), to_addrs=recipients)
        except (smtplib.SMTPException, OSError) as exc:
            raise IntegrationError(f"SMTP send failed ({type(exc).__name__})") from exc

    # --- reading ---------------------------------------------------------------------------

    async def search(
        self, query: str, *, folder: Folder = "inbox", limit: int = 10
    ) -> list[EmailMessage]:
        if folder == "sent":
            return (
                await self._outbox.search(query, folder="sent", limit=limit) if self._outbox else []
            )
        return await asyncio.to_thread(self._imap, self._search_sync, query, limit)

    async def get(self, message_id: str) -> EmailMessage:
        if not message_id.isdigit():
            if self._outbox is None:
                raise NotFoundError("email", message_id)
            return await self._outbox.get(message_id)
        return await asyncio.to_thread(self._imap, self._get_sync, message_id)

    def _imap(self, action: Any, *args: Any) -> Any:
        s = self._settings
        if not (s.imap_host and s.imap_username and s.imap_password):
            raise IntegrationError("IMAP is not configured (imap_host, username and password)")
        try:
            client = imaplib.IMAP4_SSL(s.imap_host, s.imap_port, timeout=s.email_timeout_seconds)
            try:
                client.login(s.imap_username, s.imap_password.get_secret_value())
                client.select("INBOX", readonly=True)
                return action(client, *args)
            finally:
                with contextlib.suppress(imaplib.IMAP4.error, OSError):
                    client.logout()
        except (imaplib.IMAP4.error, OSError) as exc:
            raise IntegrationError(f"IMAP request failed ({type(exc).__name__})") from exc

    @staticmethod
    def _fetch(client: imaplib.IMAP4, uid: str) -> EmailMessage | None:
        status, data = client.uid("FETCH", uid, "(BODY.PEEK[])")
        if status != "OK":
            raise IntegrationError("IMAP fetch was rejected")
        for part in data:
            if isinstance(part, tuple) and isinstance(part[1], bytes):
                return parse_message(uid, part[1])
        return None

    def _search_sync(self, client: imaplib.IMAP4, query: str, limit: int) -> list[EmailMessage]:
        criteria = ("TEXT", quote_imap_string(query)) if query.strip() else ("ALL",)
        status, data = client.uid("SEARCH", None, *criteria)  # type: ignore[arg-type]
        if status != "OK":
            raise IntegrationError("IMAP search was rejected")
        uids = sorted((u.decode() for u in (data[0] or b"").split()), key=int)
        found = (self._fetch(client, uid) for uid in reversed(uids[-limit:]))
        return [message for message in found if message is not None]

    def _get_sync(self, client: imaplib.IMAP4, uid: str) -> EmailMessage:
        message = self._fetch(client, uid)
        if message is None:
            raise NotFoundError("email", uid)
        return message
