"""Email domain models and the gateway port."""

import hashlib
import re
from datetime import datetime
from email.utils import parseaddr
from typing import Annotated, Literal, Protocol

from pydantic import AfterValidator, BaseModel, Field

MESSAGE_ID_DOMAIN = "brain-agent.local"
_ADDRESS = re.compile(r"[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+")
_NO_NEWLINES = r"\A[^\r\n]*\z"

Folder = Literal["inbox", "sent"]


def message_id_for(idempotency_key: str) -> str:
    """Deterministic ``Message-ID`` so a retried send carries the same header."""
    digest = hashlib.sha256(idempotency_key.encode()).hexdigest()[:32]
    return f"<{digest}@{MESSAGE_ID_DOMAIN}>"


def normalize_address(value: str) -> str:
    address = parseaddr(value)[1]
    if _ADDRESS.fullmatch(address) is None:
        raise ValueError(f"{value!r} is not a valid email address")
    local, _, domain = address.partition("@")
    return f"{local}@{domain.lower()}"


EmailAddress = Annotated[str, AfterValidator(normalize_address)]
"""A bare address (``Name <a@b.c>`` is reduced to ``a@b.c``) with a lowercase domain."""
SingleLine = Annotated[str, Field(pattern=_NO_NEWLINES)]


class OutgoingEmail(BaseModel):
    to: list[EmailAddress] = Field(min_length=1, max_length=50)
    cc: list[EmailAddress] = Field(default_factory=list, max_length=50)
    subject: SingleLine = Field(min_length=1, max_length=200)
    body_text: str = Field(min_length=1, max_length=20000)
    reply_to_message_id: SingleLine | None = None
    """``Message-ID`` header of the email being answered."""


class EmailMessage(BaseModel):
    id: str
    message_id_header: str
    from_: str
    to: list[str]
    cc: list[str] = Field(default_factory=list)
    subject: str
    body_text: str
    received_at: datetime | None = None
    sent_at: datetime | None = None
    folder: Folder


class SendResult(BaseModel):
    id: str
    message_id_header: str
    provider: str
    deduplicated: bool


class EmailGateway(Protocol):
    """Sending and reading email. ``search`` returns the newest matches first; ``get`` raises
    :class:`NotFoundError` for an unknown id and adapters raise :class:`IntegrationError` when
    the provider fails."""

    @property
    def retry_safe(self) -> bool:
        """Whether repeating ``send`` with the same key never sends twice."""
        ...

    async def send(self, email: OutgoingEmail, *, idempotency_key: str) -> SendResult: ...

    async def search(
        self, query: str, *, folder: Folder = "inbox", limit: int = 10
    ) -> list[EmailMessage]:
        """Messages whose sender, recipients, subject or body contain ``query``."""
        ...

    async def get(self, message_id: str) -> EmailMessage: ...
