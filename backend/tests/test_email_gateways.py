"""Email gateway contract (in-memory and Postgres outbox), SMTP against a real local server,
IMAP against a fake ``imaplib.IMAP4_SSL``, and settings validation."""

import hashlib
import imaplib
import socket
from collections.abc import AsyncIterator, Iterator
from email import message_from_bytes
from typing import Any, ClassVar

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP, Envelope, Session
from pydantic import SecretStr, ValidationError

from brain_agent.config import Settings
from brain_agent.errors import ConfigurationError, IntegrationError, NotFoundError
from brain_agent.integrations.email import (
    EmailGateway,
    OutgoingEmail,
    message_id_for,
)
from brain_agent.integrations.email_factory import create_email_gateway
from brain_agent.integrations.memory import InMemoryEmailGateway
from brain_agent.integrations.postgres import OutboxEmailGateway
from brain_agent.integrations.smtp_imap import SmtpImapEmailGateway
from brain_agent.persistence.postgres import open_persistence

FROM = "agent@acme.com"
BACKENDS = ["memory", pytest.param("outbox", marks=pytest.mark.integration)]


def _mail(subject: str = "Hello", **kwargs: Any) -> OutgoingEmail:
    fields: dict[str, Any] = {"to": ["bob@acme.com"], "subject": subject, "body_text": "Body"}
    return OutgoingEmail(**{**fields, **kwargs})


@pytest.fixture(params=BACKENDS)
async def gateway(request: pytest.FixtureRequest) -> AsyncIterator[Any]:
    if request.param == "memory":
        yield InMemoryEmailGateway(FROM)
        return
    schema_url: str = request.getfixturevalue("schema_url")
    async with open_persistence(schema_url) as persistence:
        yield OutboxEmailGateway(persistence.pool, FROM)


# --- models -------------------------------------------------------------------------------


def test_addresses_are_validated_and_domains_lowercased() -> None:
    mail = _mail(to=["Bob@ACME.com", "<ann@Example.ORG>"], cc=["Cy <cy@X.io>"])

    assert mail.to == ["Bob@acme.com", "ann@example.org"]
    assert mail.cc == ["cy@x.io"]
    for bad in ("nobody", "a@b@c.com", "a b@c.com", "a@", "@c.com", ""):
        with pytest.raises(ValidationError):
            _mail(to=[bad])


def test_outgoing_email_bounds_and_header_injection() -> None:
    with pytest.raises(ValidationError):
        _mail(to=[])
    with pytest.raises(ValidationError):
        _mail(to=[f"u{i}@acme.com" for i in range(51)])
    with pytest.raises(ValidationError):
        _mail(subject="")
    with pytest.raises(ValidationError):
        _mail(subject="x" * 201)
    with pytest.raises(ValidationError):
        _mail(body_text="x" * 20001)
    with pytest.raises(ValidationError):
        _mail(subject="Hi\r\nBcc: evil@x.io")


def test_message_id_is_derived_from_the_key() -> None:
    digest = hashlib.sha256(b"thread:call").hexdigest()[:32]
    assert message_id_for("thread:call") == f"<{digest}@brain-agent.local>"


# --- contract: in-memory and Postgres outbox ----------------------------------------------


async def test_send_is_deduplicated_by_key(gateway: EmailGateway) -> None:
    first = await gateway.send(_mail(), idempotency_key="k1")
    again = await gateway.send(_mail("Other subject"), idempotency_key="k1")
    other = await gateway.send(_mail(), idempotency_key="k2")

    assert gateway.retry_safe is True
    assert (first.deduplicated, again.deduplicated, other.deduplicated) == (False, True, False)
    assert again.id == first.id and other.id != first.id
    assert first.message_id_header == message_id_for("k1") != other.message_id_header
    assert first.provider == "outbox"
    sent = await gateway.get(first.id)
    assert (sent.subject, sent.folder, sent.from_, sent.to) == (
        "Hello",
        "sent",
        FROM,
        ["bob@acme.com"],
    )
    assert sent.message_id_header == first.message_id_header and sent.sent_at is not None


async def test_search_get_and_folders(gateway: Any) -> None:
    await gateway.send(_mail("Quarterly REPORT", body_text="numbers"), idempotency_key="a")
    await gateway.send(_mail("Lunch", body_text="100% sure", cc=["cy@x.io"]), idempotency_key="b")
    inbound = await gateway.add_inbox_message(
        from_="ann@example.org", to=[FROM], subject="Report question", body_text="Any news?"
    )

    assert inbound.folder == "inbox" and inbound.received_at is not None
    assert [m.id for m in await gateway.search("report")] == [inbound.id]
    assert [m.subject for m in await gateway.search("", folder="sent")] == [
        "Lunch",
        "Quarterly REPORT",
    ]
    assert [m.subject for m in await gateway.search("NUMBERS", folder="sent")] == [
        "Quarterly REPORT"
    ]
    assert [m.subject for m in await gateway.search("100%", folder="sent")] == ["Lunch"]
    assert await gateway.search("%", folder="inbox") == []  # wildcards are literal
    assert len(await gateway.search("", folder="sent", limit=1)) == 1
    assert await gateway.get(inbound.id) == inbound


async def test_get_unknown_message_is_not_found(gateway: EmailGateway) -> None:
    with pytest.raises(NotFoundError):
        await gateway.get("missing")


# --- SMTP against a real local server -----------------------------------------------------


class Inbox:
    def __init__(self) -> None:
        self.envelopes: list[Envelope] = []

    async def handle_DATA(self, server: SMTP, session: Session, envelope: Envelope) -> str:  # noqa: N802
        self.envelopes.append(envelope)
        return "250 OK"


@pytest.fixture
def smtp_server() -> Iterator[tuple[int, Inbox]]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    inbox = Inbox()
    controller = Controller(inbox, hostname="127.0.0.1", port=port)
    controller.start()
    try:
        yield port, inbox
    finally:
        controller.stop()


def _smtp_settings(port: int, **overrides: Any) -> Settings:
    return Settings(
        _env_file=None,
        email_provider="smtp",
        smtp_host="127.0.0.1",
        smtp_port=port,
        smtp_security="none",
        **overrides,
    )


async def test_smtp_sends_with_deterministic_headers(smtp_server: tuple[int, Inbox]) -> None:
    port, inbox = smtp_server
    gateway = SmtpImapEmailGateway(_smtp_settings(port))

    result = await gateway.send(
        _mail(cc=["cy@acme.com"], reply_to_message_id="<orig@x.io>"), idempotency_key="t:c1"
    )

    assert gateway.retry_safe is False
    assert (result.provider, result.deduplicated) == ("smtp", False)
    [envelope] = inbox.envelopes
    assert envelope.rcpt_tos == ["bob@acme.com", "cy@acme.com"]
    received = message_from_bytes(envelope.original_content or b"")
    assert received["Message-ID"] == message_id_for("t:c1") == result.message_id_header
    assert received["X-Idempotency-Key"] == "t:c1"
    assert (received["From"], received["Subject"], received["In-Reply-To"]) == (
        FROM,
        "Hello",
        "<orig@x.io>",
    )
    assert "Body" in str(received.get_payload())


@pytest.mark.integration
async def test_smtp_keeps_a_copy_in_the_outbox(
    smtp_server: tuple[int, Inbox], schema_url: str
) -> None:
    port, _ = smtp_server
    async with open_persistence(schema_url) as persistence:
        outbox = OutboxEmailGateway(persistence.pool, FROM)
        gateway = SmtpImapEmailGateway(_smtp_settings(port), outbox)

        result = await gateway.send(_mail(), idempotency_key="k")

        [copy] = await gateway.search("", folder="sent")
        assert copy.message_id_header == result.message_id_header
        assert (await gateway.get(copy.id)).subject == "Hello"


async def test_smtp_failure_is_a_typed_error_without_secrets() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]
    settings = _smtp_settings(closed_port, smtp_username="u", smtp_password=SecretStr("hunter2"))

    with pytest.raises(IntegrationError) as caught:
        await SmtpImapEmailGateway(settings).send(_mail(), idempotency_key="k")

    assert "hunter2" not in str(caught.value)


# --- IMAP with a fake client --------------------------------------------------------------

RAW_PLAIN = (
    b"From: Ann <ann@Example.org>\r\nTo: agent@acme.com\r\nCc: cy@x.io\r\n"
    b"Subject: Report\r\nMessage-ID: <m1@example.org>\r\nDate: Mon, 05 Oct 2026 10:00:00 +0000\r\n"
    b"MIME-Version: 1.0\r\nContent-Type: multipart/alternative; boundary=b\r\n\r\n"
    b"--b\r\nContent-Type: text/plain\r\n\r\nplain body\r\n"
    b"--b\r\nContent-Type: text/html\r\n\r\n<p>html body</p>\r\n--b--\r\n"
)
RAW_HTML = (
    b"From: bob@x.io\r\nTo: agent@acme.com\r\nSubject: Html only\r\n"
    b"Content-Type: text/html\r\n\r\n<style>p{}</style><p>Hello&nbsp;<b>world</b></p>\r\n"
)


class FakeImap:
    """Stands in for ``imaplib.IMAP4_SSL``; class-level state is inspected by the tests."""

    messages: ClassVar[dict[bytes, bytes]] = {}
    commands: ClassVar[list[tuple[Any, ...]]] = []
    login_error: bool = False

    def __init__(self, host: str, port: int, timeout: float | None = None) -> None:
        type(self).commands.append(("connect", host, port, timeout))

    def login(self, user: str, password: str) -> tuple[str, list[bytes]]:
        if type(self).login_error:
            raise imaplib.IMAP4.error(f"LOGIN failed for {password}")
        return "OK", [b""]

    def select(self, mailbox: str, readonly: bool = False) -> tuple[str, list[bytes]]:
        return "OK", [b"1"]

    def uid(self, command: str, *args: Any) -> tuple[str, list[Any]]:
        type(self).commands.append((command, *args))
        if command == "SEARCH":
            return "OK", [b" ".join(type(self).messages)]
        uid = args[0].encode() if isinstance(args[0], str) else args[0]
        if uid not in type(self).messages:
            return "OK", [None]
        return "OK", [(b"1 (UID 1 BODY[] {1}", type(self).messages[uid]), b")"]

    def logout(self) -> tuple[str, list[bytes]]:
        return "BYE", [b""]


@pytest.fixture
def imap(monkeypatch: pytest.MonkeyPatch) -> type[FakeImap]:
    FakeImap.messages = {b"3": RAW_PLAIN, b"7": RAW_HTML}
    FakeImap.commands = []
    FakeImap.login_error = False
    monkeypatch.setattr(imaplib, "IMAP4_SSL", FakeImap)
    return FakeImap


def _imap_gateway() -> SmtpImapEmailGateway:
    settings = Settings(
        _env_file=None,
        smtp_host="127.0.0.1",
        smtp_security="none",
        imap_host="imap.acme.com",
        imap_username="agent",
        imap_password=SecretStr("pw"),
        email_timeout_seconds=7,
    )
    return SmtpImapEmailGateway(settings)


async def test_imap_search_returns_newest_first_and_parses_bodies(imap: type[FakeImap]) -> None:
    found = await _imap_gateway().search("report", limit=10)

    assert [m.id for m in found] == ["7", "3"]
    html, plain = found
    assert html.body_text == "Hello world" and html.subject == "Html only"
    assert (plain.from_, plain.to, plain.cc) == ("ann@example.org", ["agent@acme.com"], ["cy@x.io"])
    assert plain.body_text == "plain body" and plain.message_id_header == "<m1@example.org>"
    assert plain.folder == "inbox" and plain.received_at is not None
    assert ("connect", "imap.acme.com", 993, 7) in imap.commands
    assert ("SEARCH", None, "TEXT", '"report"') in imap.commands
    assert len(await _imap_gateway().search("", limit=1)) == 1


async def test_imap_query_is_sanitized(imap: type[FakeImap]) -> None:
    await _imap_gateway().search('x"\r\nA1 DELETE INBOX\r\n \\', limit=5)

    [search] = [c for c in imap.commands if c[0] == "SEARCH"]
    criterion = search[3]
    assert "\r" not in criterion and "\n" not in criterion
    assert criterion == '"x\\" A1 DELETE INBOX \\\\"'


async def test_imap_get_and_errors(imap: type[FakeImap]) -> None:
    gateway = _imap_gateway()

    assert (await gateway.get("3")).subject == "Report"
    with pytest.raises(NotFoundError):
        await gateway.get("99")
    imap.login_error = True
    with pytest.raises(IntegrationError) as caught:
        await gateway.search("x")
    assert "pw" not in str(caught.value)


async def test_imap_without_configuration_is_a_typed_error() -> None:
    gateway = SmtpImapEmailGateway(Settings(_env_file=None, smtp_host="smtp.acme.com"))

    with pytest.raises(IntegrationError):
        await gateway.search("x")


# --- settings and factory -----------------------------------------------------------------


async def test_factory_picks_the_adapter_and_validates_smtp_settings() -> None:
    memory = create_email_gateway(Settings(_env_file=None), None)
    assert isinstance(memory, InMemoryEmailGateway)

    with pytest.raises(ConfigurationError, match="smtp_host"):
        create_email_gateway(Settings(_env_file=None, email_provider="smtp"), None)
    with pytest.raises(ConfigurationError, match="smtp_security"):
        create_email_gateway(
            Settings(
                _env_file=None,
                email_provider="smtp",
                smtp_host="mail.acme.com",
                smtp_security="none",
            ),
            None,
        )
    with pytest.raises(ConfigurationError, match="smtp_password"):
        create_email_gateway(
            Settings(
                _env_file=None, email_provider="smtp", smtp_host="mail.acme.com", smtp_username="u"
            ),
            None,
        )
    local = Settings(
        _env_file=None, email_provider="smtp", smtp_host="localhost", smtp_security="none"
    )
    assert isinstance(create_email_gateway(local, None), SmtpImapEmailGateway)
    defaults = Settings(_env_file=None)
    assert (defaults.smtp_security, defaults.email_from, defaults.smtp_port) == (
        "ssl",
        "agent@acme.com",
        465,
    )
