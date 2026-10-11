"""Repository contract tests, run against the in-memory and the PostgreSQL adapters."""

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest

from brain_agent.errors import NotFoundError
from brain_agent.integrations.crm import CrmRepository
from brain_agent.integrations.memory import InMemoryCrmRepository, InMemoryTaskRepository
from brain_agent.integrations.tasks import TaskRepository
from brain_agent.persistence.postgres import open_persistence

BACKENDS = ["memory", pytest.param("postgres", marks=pytest.mark.integration)]


@pytest.fixture(params=BACKENDS)
async def repos(
    request: pytest.FixtureRequest,
) -> AsyncIterator[tuple[CrmRepository, TaskRepository]]:
    if request.param == "memory":
        yield InMemoryCrmRepository(), InMemoryTaskRepository()
        return
    schema_url: str = request.getfixturevalue("schema_url")
    async with open_persistence(schema_url) as persistence:
        yield persistence.crm, persistence.tasks


# --- CRM ----------------------------------------------------------------------------------


async def _ada(crm: CrmRepository, key: str = "k-ada") -> str:
    contact = await crm.create_contact(
        name="Ada Lovelace",
        email="ada@Analytical.io",
        company="Analytical Engines",
        phone=None,
        tags=["vip"],
        idempotency_key=key,
    )
    return contact.id


async def test_contact_roundtrip_and_idempotent_create(
    repos: tuple[CrmRepository, TaskRepository],
) -> None:
    crm, _ = repos
    first = await crm.create_contact(
        name="Ada", email="a@x.io", company="X", phone="+1", tags=["a"], idempotency_key="k1"
    )
    again = await crm.create_contact(
        name="Other", email="o@x.io", company="Y", phone=None, tags=[], idempotency_key="k1"
    )

    assert again == first
    assert (first.phone, first.tags) == ("+1", ["a"])
    assert await crm.get_contact(first.id) == first
    assert len(await crm.search_contacts("", 10)) == 1
    with pytest.raises(NotFoundError):
        await crm.get_contact("missing")


async def test_search_is_case_insensitive_over_name_email_and_company(
    repos: tuple[CrmRepository, TaskRepository],
) -> None:
    crm, _ = repos
    ada = await _ada(crm)
    await crm.create_contact(
        name="Bob", email="bob@b.io", company="Builders", phone=None, tags=[], idempotency_key="k2"
    )

    for query in ("lovelace", "ANALYTICAL.IO", "engines"):
        assert [c.id for c in await crm.search_contacts(query, 10)] == [ada]
    assert [c.name for c in await crm.search_contacts("", 10)] == ["Ada Lovelace", "Bob"]
    assert len(await crm.search_contacts("", 1)) == 1
    assert await crm.search_contacts("100%", 10) == []  # wildcards are literal


async def test_deals_create_filter_and_partial_update(
    repos: tuple[CrmRepository, TaskRepository],
) -> None:
    crm, _ = repos
    ada = await _ada(crm)
    deal = await crm.create_deal(
        contact_id=ada,
        title="Engine",
        amount=Decimal("1500.5"),
        currency="EUR",
        stage="lead",
        idempotency_key="d1",
    )
    same = await crm.create_deal(
        contact_id=ada,
        title="Dup",
        amount=Decimal(1),
        currency="USD",
        stage="won",
        idempotency_key="d1",
    )

    assert same == deal and deal.amount == Decimal("1500.50")
    updated = await crm.update_deal(deal.id, stage="won")
    assert (updated.stage, updated.amount, updated.title) == ("won", Decimal("1500.50"), "Engine")
    assert updated.updated_at >= deal.updated_at
    renamed = await crm.update_deal(deal.id, amount=Decimal("20000"), title="Big engine")
    assert (renamed.amount, renamed.title, renamed.stage) == (
        Decimal("20000.00"),
        "Big engine",
        "won",
    )
    assert [d.id for d in await crm.list_deals(ada, "won")] == [deal.id]
    assert await crm.list_deals(None, "lead") == []
    assert len(await crm.list_deals(None, None)) == 1
    with pytest.raises(NotFoundError):
        await crm.update_deal("missing", stage="lost")
    with pytest.raises(NotFoundError):
        await crm.create_deal(
            contact_id="missing",
            title="x",
            amount=Decimal(1),
            currency="USD",
            stage="lead",
            idempotency_key="d2",
        )


async def test_delete_is_idempotent_and_contact_delete_removes_its_deals(
    repos: tuple[CrmRepository, TaskRepository],
) -> None:
    crm, _ = repos
    ada = await _ada(crm)
    deal = await crm.create_deal(
        contact_id=ada,
        title="t",
        amount=Decimal(5),
        currency="USD",
        stage="lead",
        idempotency_key="d1",
    )

    assert await crm.delete_record("contact", ada) is True
    assert await crm.delete_record("contact", ada) is False
    assert await crm.delete_record("deal", deal.id) is False  # removed with its contact
    assert await crm.list_deals(None, None) == []


# --- tasks --------------------------------------------------------------------------------


async def test_task_idempotent_create_list_complete_delete(
    repos: tuple[CrmRepository, TaskRepository],
) -> None:
    _, tasks = repos
    first = await tasks.create_task(
        title="Call Ada",
        description="about the deal",
        due_date=date(2026, 12, 1),
        priority="high",
        assignee="sam",
        idempotency_key="t1",
    )
    again = await tasks.create_task(
        title="Different",
        description="",
        due_date=None,
        priority="low",
        assignee=None,
        idempotency_key="t1",
    )
    other = await tasks.create_task(
        title="File taxes",
        description="",
        due_date=None,
        priority="normal",
        assignee=None,
        idempotency_key="t2",
    )

    assert again == first
    assert (first.status, first.due_date, first.priority) == ("open", date(2026, 12, 1), "high")
    assert [t.id for t in await tasks.list_tasks(None, None, 10)] == [first.id, other.id]
    assert [t.id for t in await tasks.list_tasks(None, "sam", 10)] == [first.id]
    assert len(await tasks.list_tasks(None, None, 1)) == 1

    done = await tasks.complete_task(first.id)
    assert done.status == "done"
    assert (await tasks.complete_task(first.id)).status == "done"
    assert [t.id for t in await tasks.list_tasks("open", None, 10)] == [other.id]

    assert await tasks.delete_task(other.id) is True
    assert await tasks.delete_task(other.id) is False
    with pytest.raises(NotFoundError):
        await tasks.complete_task(other.id)


@pytest.mark.parametrize(
    ("amount", "stored"),
    [
        ("0.005", "0.01"),
        ("0.015", "0.02"),
        ("0.025", "0.03"),  # half-even would give 0.02
        ("2.675", "2.68"),
        ("0.004", "0.00"),
        ("-0.005", "-0.01"),
    ],
)
async def test_amounts_round_half_away_from_zero_in_both_adapters(
    repos: tuple[CrmRepository, TaskRepository], amount: str, stored: str
) -> None:
    crm, _ = repos
    ada = await _ada(crm)

    deal = await crm.create_deal(
        contact_id=ada,
        title="t",
        amount=Decimal(amount),
        currency="USD",
        stage="lead",
        idempotency_key="d1",
    )
    updated = await crm.update_deal(deal.id, amount=Decimal(amount))

    assert (deal.amount, updated.amount) == (Decimal(stored), Decimal(stored))
