"""CRM tools over a :class:`CrmRepository`."""

from decimal import Decimal
from typing import Annotated, Self

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, model_validator

from brain_agent.integrations.crm import CrmRepository, DealStage
from brain_agent.tools.support import idempotency_key_or_new, make_tool, to_json

SEARCH_LIMIT_MAX = 50
AMOUNT_MAX = Decimal("999999999999.99")  # what numeric(14, 2) can hold
DealAmount = Annotated[Decimal, Field(ge=0, le=AMOUNT_MAX, decimal_places=2)]


class SearchContactsArgs(BaseModel):
    query: str = Field(description="Text to look for in name, email or company; '' lists all.")
    limit: int = Field(default=10, ge=1, le=SEARCH_LIMIT_MAX, description="Maximum results.")


class GetContactArgs(BaseModel):
    contact_id: str = Field(description="Id of the contact, as returned by crm_search_contacts.")


class CreateContactArgs(BaseModel):
    name: str = Field(min_length=1, description="Full name.")
    email: str = Field(min_length=3, description="Email address.")
    company: str = Field(default="", description="Company name.")
    phone: str | None = Field(default=None, description="Phone number.")
    tags: list[str] = Field(default_factory=list, description="Free-form labels.")


class ListDealsArgs(BaseModel):
    contact_id: str | None = Field(default=None, description="Only deals of this contact.")
    stage: DealStage | None = Field(default=None, description="Only deals in this stage.")


class CreateDealArgs(BaseModel):
    contact_id: str = Field(description="Id of the contact the deal belongs to.")
    title: str = Field(min_length=1, description="Short deal title.")
    amount: DealAmount = Field(description="Deal value in the given currency.")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="ISO 4217 code.")
    stage: DealStage = Field(default="lead", description="Pipeline stage.")


class UpdateDealArgs(BaseModel):
    deal_id: str = Field(description="Id of the deal, as returned by crm_list_deals.")
    amount: DealAmount | None = Field(default=None, description="New deal value.")
    stage: DealStage | None = Field(default=None, description="New pipeline stage.")
    title: str | None = Field(default=None, min_length=1, description="New title.")

    @model_validator(mode="after")
    def _something_to_change(self) -> Self:
        if self.amount is None and self.stage is None and self.title is None:
            raise ValueError("give at least one of amount, stage or title to update")
        return self


def build_crm_tools(repo: CrmRepository) -> list[BaseTool]:
    """The CRM tools, all safe to repeat after a crash (reads, keyed creates, absolute updates)."""

    async def search_contacts(query: str, limit: int = 10) -> str:
        return to_json(list(await repo.search_contacts(query, limit)))

    async def get_contact(contact_id: str) -> str:
        return to_json(await repo.get_contact(contact_id))

    async def create_contact(
        name: str,
        email: str,
        company: str = "",
        phone: str | None = None,
        tags: list[str] | None = None,
    ) -> str:
        contact = await repo.create_contact(
            name=name,
            email=email,
            company=company,
            phone=phone,
            tags=tags or [],
            idempotency_key=idempotency_key_or_new(),
        )
        return to_json(contact)

    async def list_deals(contact_id: str | None = None, stage: DealStage | None = None) -> str:
        return to_json(list(await repo.list_deals(contact_id, stage)))

    async def create_deal(
        contact_id: str,
        title: str,
        amount: Decimal,
        currency: str = "USD",
        stage: DealStage = "lead",
    ) -> str:
        deal = await repo.create_deal(
            contact_id=contact_id,
            title=title,
            amount=amount,
            currency=currency.upper(),
            stage=stage,
            idempotency_key=idempotency_key_or_new(),
        )
        return to_json(deal)

    async def update_deal(
        deal_id: str,
        amount: Decimal | None = None,
        stage: DealStage | None = None,
        title: str | None = None,
    ) -> str:
        return to_json(await repo.update_deal(deal_id, amount=amount, stage=stage, title=title))

    return [
        make_tool(
            "crm_search_contacts",
            "Search CRM contacts by text in name, email or company (case-insensitive). "
            "Returns a JSON list of contacts with their ids.",
            SearchContactsArgs,
            search_contacts,
            "low",
            read_only=True,
        ),
        make_tool(
            "crm_get_contact",
            "Get one CRM contact by id. Returns the contact as JSON.",
            GetContactArgs,
            get_contact,
            "low",
            read_only=True,
        ),
        make_tool(
            "crm_create_contact",
            "Create a CRM contact. Returns the created contact as JSON, including its id.",
            CreateContactArgs,
            create_contact,
            "medium",
        ),
        make_tool(
            "crm_list_deals",
            "List CRM deals, optionally only those of one contact and/or in one stage. "
            "Returns a JSON list of deals with their ids.",
            ListDealsArgs,
            list_deals,
            "low",
            read_only=True,
        ),
        make_tool(
            "crm_create_deal",
            "Create a deal for an existing contact. Amounts are decimal numbers. "
            "Returns the created deal as JSON.",
            CreateDealArgs,
            create_deal,
            "medium",
        ),
        make_tool(
            "crm_update_deal",
            "Update a deal's amount, stage and/or title (only the given fields change). "
            "Large amounts may need human approval. Returns the updated deal as JSON.",
            UpdateDealArgs,
            update_deal,
            "medium",
        ),
    ]
