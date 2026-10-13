"""Email tools over an :class:`EmailGateway`."""

import re
from typing import Any

from langchain_core.tools import BaseTool, ToolException
from pydantic import BaseModel, Field, ValidationError, field_validator

from brain_agent.brain.prompt import UNTRUSTED_TAG
from brain_agent.errors import IntegrationError
from brain_agent.integrations.email import EmailGateway, EmailMessage, OutgoingEmail
from brain_agent.tools.support import idempotency_key_or_new, make_tool, to_json

BODY_LIMIT = 4000
SEARCH_LIMIT_MAX = 50
_SEPARATORS = re.compile(r"[,;]")


def _untrusted(payload: str) -> str:
    """Spotlight email content as outside data. JSON may escape ``/`` as ``\\/``, so a body
    cannot close the tag early."""
    escaped = payload.replace(f"</{UNTRUSTED_TAG}", f"<\\/{UNTRUSTED_TAG}")
    return f'<{UNTRUSTED_TAG} source="email">\n{escaped}\n</{UNTRUSTED_TAG}>'


def _split_recipients(value: Any) -> Any:
    """Accept one string holding several addresses (``"a@x.io, b@y.io"``) as well as a list."""
    if isinstance(value, str):
        return [part.strip() for part in _SEPARATORS.split(value) if part.strip()]
    return value


class SendEmailArgs(BaseModel):
    to: list[str] = Field(description="Recipient addresses (1 to 50).")
    subject: str = Field(description="Subject line, up to 200 characters.")
    body: str = Field(description="Plain-text body, up to 20000 characters.")
    cc: list[str] = Field(default_factory=list, description="Addresses to copy.")

    _split = field_validator("to", "cc", mode="before")(_split_recipients)


class SearchInboxArgs(BaseModel):
    query: str = Field(description="Text to look for in sender, subject or body; '' lists latest.")
    limit: int = Field(default=10, ge=1, le=SEARCH_LIMIT_MAX, description="Maximum results.")


class ReadEmailArgs(BaseModel):
    message_id: str = Field(description="Id of the email, as returned by search_inbox.")


def _truncated(message: EmailMessage) -> EmailMessage:
    body = message.body_text
    if len(body) <= BODY_LIMIT:
        return message
    marker = f"\n[truncated: {len(body) - BODY_LIMIT} more characters]"
    return message.model_copy(update={"body_text": body[:BODY_LIMIT] + marker})


def build_email_tools(gateway: EmailGateway) -> list[BaseTool]:
    """``send_email`` (repeat-safe only if the gateway is) and the read-only inbox tools."""

    async def send_email(
        to: list[str], subject: str, body: str, cc: list[str] | None = None
    ) -> str:
        try:
            email = OutgoingEmail(to=to, cc=cc or [], subject=subject, body_text=body)
        except ValidationError as exc:
            raise ToolException(f"Invalid email: {exc.errors()[0]['msg']}") from exc
        try:
            result = await gateway.send(email, idempotency_key=idempotency_key_or_new())
        except IntegrationError as exc:
            if exc.outcome_unknown:  # may have been sent: the ledger asks a human
                raise
            raise ToolException(str(exc)) from exc
        return to_json(
            {
                "id": result.id,
                "message_id": result.message_id_header,
                "deduplicated": result.deduplicated,
            }
        )

    async def search_inbox(query: str, limit: int = 10) -> str:
        try:
            found = await gateway.search(query, folder="inbox", limit=limit)
        except IntegrationError as exc:
            raise ToolException(str(exc)) from exc
        return _untrusted(to_json([_truncated(m) for m in found]))

    async def read_email(message_id: str) -> str:
        try:
            return _untrusted(to_json(_truncated(await gateway.get(message_id))))
        except IntegrationError as exc:
            raise ToolException(str(exc)) from exc

    return [
        make_tool(
            "send_email",
            "Send a plain-text email. Recipients outside the company, or more than 5, need "
            "human approval first. Returns {id, message_id, deduplicated} as JSON.",
            SendEmailArgs,
            send_email,
            "medium",
            retry_safe=gateway.retry_safe,
            approval_reason="Sending email cannot be undone.",
        ),
        make_tool(
            "search_inbox",
            "Search received emails by text in sender, recipients, subject or body, newest "
            "first. Long bodies are truncated; use read_email for one message.",
            SearchInboxArgs,
            search_inbox,
            "low",
            read_only=True,
            untrusted_output=True,
        ),
        make_tool(
            "read_email",
            "Read one received or sent email by id. Long bodies are truncated.",
            ReadEmailArgs,
            read_email,
            "low",
            read_only=True,
            untrusted_output=True,
        ),
    ]
