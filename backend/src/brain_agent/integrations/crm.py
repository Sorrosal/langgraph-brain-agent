"""CRM domain models and the repository port."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Protocol

from pydantic import BaseModel, Field

DealStage = Literal["lead", "qualified", "proposal", "won", "lost"]
RecordKind = Literal["contact", "deal"]


class Contact(BaseModel):
    id: str
    name: str
    email: str
    company: str
    phone: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime


class Deal(BaseModel):
    id: str
    contact_id: str
    title: str
    amount: Decimal
    currency: str
    stage: DealStage
    updated_at: datetime


class CrmRepository(Protocol):
    """Contacts and deals. ``create_*`` are idempotent on ``idempotency_key``: repeating a key
    returns the originally created record. Unknown ids raise :class:`NotFoundError`."""

    async def search_contacts(self, query: str, limit: int) -> list[Contact]:
        """Contacts whose name, email or company contains ``query`` (case-insensitive)."""
        ...

    async def get_contact(self, contact_id: str) -> Contact: ...

    async def create_contact(
        self,
        *,
        name: str,
        email: str,
        company: str,
        phone: str | None,
        tags: list[str],
        idempotency_key: str,
    ) -> Contact: ...

    async def list_deals(self, contact_id: str | None, stage: DealStage | None) -> list[Deal]: ...

    async def create_deal(
        self,
        *,
        contact_id: str,
        title: str,
        amount: Decimal,
        currency: str,
        stage: DealStage,
        idempotency_key: str,
    ) -> Deal: ...

    async def update_deal(
        self,
        deal_id: str,
        *,
        amount: Decimal | None = None,
        stage: DealStage | None = None,
        title: str | None = None,
    ) -> Deal:
        """Set the given fields to absolute values (so repeating the call is harmless)."""
        ...

    async def delete_record(self, kind: RecordKind, record_id: str) -> bool:
        """Delete a record (a contact takes its deals along); ``False`` if already gone."""
        ...
