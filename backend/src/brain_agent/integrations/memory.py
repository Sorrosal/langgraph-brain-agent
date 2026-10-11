"""In-memory adapters with the same semantics as the PostgreSQL ones (tests and demo mode)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from brain_agent.errors import NotFoundError
from brain_agent.integrations.crm import Contact, Deal, DealStage, RecordKind
from brain_agent.integrations.tasks import Priority, Task, TaskStatus

CENT = Decimal("0.01")


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class InMemoryCrmRepository:
    def __init__(self) -> None:
        self._contacts: dict[str, Contact] = {}
        self._deals: dict[str, Deal] = {}
        self._keys: dict[str, str] = {}  # idempotency key -> record id

    async def search_contacts(self, query: str, limit: int) -> list[Contact]:
        needle = query.casefold()
        found = [
            c
            for c in self._contacts.values()
            if needle in f"{c.name}\n{c.email}\n{c.company}".casefold()
        ]
        return sorted(found, key=lambda c: (c.name, c.id))[:limit]

    async def get_contact(self, contact_id: str) -> Contact:
        if contact_id not in self._contacts:
            raise NotFoundError("contact", contact_id)
        return self._contacts[contact_id]

    async def create_contact(
        self,
        *,
        name: str,
        email: str,
        company: str,
        phone: str | None,
        tags: list[str],
        idempotency_key: str,
    ) -> Contact:
        if (existing := self._keys.get(f"contact:{idempotency_key}")) in self._contacts:
            return self._contacts[str(existing)]
        contact = Contact(
            id=_new_id(),
            name=name,
            email=email,
            company=company,
            phone=phone,
            tags=list(tags),
            created_at=_now(),
        )
        self._contacts[contact.id] = contact
        self._keys[f"contact:{idempotency_key}"] = contact.id
        return contact

    async def list_deals(self, contact_id: str | None, stage: DealStage | None) -> list[Deal]:
        return [
            d
            for d in self._deals.values()
            if contact_id in (None, d.contact_id) and stage in (None, d.stage)
        ]

    async def create_deal(
        self,
        *,
        contact_id: str,
        title: str,
        amount: Decimal,
        currency: str,
        stage: DealStage,
        idempotency_key: str,
    ) -> Deal:
        if (existing := self._keys.get(f"deal:{idempotency_key}")) in self._deals:
            return self._deals[str(existing)]
        await self.get_contact(contact_id)
        deal = Deal(
            id=_new_id(),
            contact_id=contact_id,
            title=title,
            amount=amount.quantize(CENT),
            currency=currency,
            stage=stage,
            updated_at=_now(),
        )
        self._deals[deal.id] = deal
        self._keys[f"deal:{idempotency_key}"] = deal.id
        return deal

    async def update_deal(
        self,
        deal_id: str,
        *,
        amount: Decimal | None = None,
        stage: DealStage | None = None,
        title: str | None = None,
    ) -> Deal:
        if deal_id not in self._deals:
            raise NotFoundError("deal", deal_id)
        changes: dict[str, object] = {"updated_at": _now()}
        if amount is not None:
            changes["amount"] = amount.quantize(CENT)
        if stage is not None:
            changes["stage"] = stage
        if title is not None:
            changes["title"] = title
        deal = self._deals[deal_id].model_copy(update=changes)
        self._deals[deal_id] = deal
        return deal

    async def delete_record(self, kind: RecordKind, record_id: str) -> bool:
        if kind == "deal":
            return self._deals.pop(record_id, None) is not None
        if self._contacts.pop(record_id, None) is None:
            return False
        self._deals = {k: d for k, d in self._deals.items() if d.contact_id != record_id}
        return True


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._keys: dict[str, str] = {}

    async def create_task(
        self,
        title: str,
        description: str,
        due_date: date | None,
        priority: Priority,
        assignee: str | None,
        *,
        idempotency_key: str,
    ) -> Task:
        if (existing := self._keys.get(idempotency_key)) in self._tasks:
            return self._tasks[str(existing)]
        task = Task(
            id=_new_id(),
            title=title,
            description=description,
            due_date=due_date,
            priority=priority,
            status="open",
            assignee=assignee,
            created_at=_now(),
        )
        self._tasks[task.id] = task
        self._keys[idempotency_key] = task.id
        return task

    async def list_tasks(
        self, status: TaskStatus | None, assignee: str | None, limit: int
    ) -> list[Task]:
        found = [
            t
            for t in self._tasks.values()  # insertion order == creation order
            if status in (None, t.status) and assignee in (None, t.assignee)
        ]
        return found[:limit]

    async def complete_task(self, task_id: str) -> Task:
        if task_id not in self._tasks:
            raise NotFoundError("task", task_id)
        task = self._tasks[task_id].model_copy(update={"status": "done"})
        self._tasks[task_id] = task
        return task

    async def delete_task(self, task_id: str) -> bool:
        return self._tasks.pop(task_id, None) is not None
