"""PostgreSQL adapters. A create is one ``INSERT .. ON CONFLICT (idempotency_key)`` whose no-op
update makes ``RETURNING`` yield the existing row on a repeat, so retries never duplicate."""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

from psycopg import AsyncConnection
from psycopg.errors import ForeignKeyViolation
from psycopg.rows import DictRow
from psycopg_pool import AsyncConnectionPool

from brain_agent.errors import NotFoundError
from brain_agent.integrations.crm import Contact, Deal, DealStage, RecordKind
from brain_agent.integrations.email import (
    MESSAGE_ID_DOMAIN,
    EmailMessage,
    Folder,
    OutgoingEmail,
    SendResult,
    message_id_for,
)
from brain_agent.integrations.tasks import Priority, Task, TaskStatus

Pool = AsyncConnectionPool[AsyncConnection[DictRow]]

MIGRATIONS = (
    """
CREATE TABLE IF NOT EXISTS crm_contacts (
    id text PRIMARY KEY,
    name text NOT NULL,
    email text NOT NULL,
    company text NOT NULL,
    phone text,
    tags text[] NOT NULL DEFAULT '{}',
    idempotency_key text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
)
""",
    """
CREATE TABLE IF NOT EXISTS crm_deals (
    id text PRIMARY KEY,
    contact_id text NOT NULL REFERENCES crm_contacts (id) ON DELETE CASCADE,
    title text NOT NULL,
    amount numeric(14, 2) NOT NULL,
    currency text NOT NULL,
    stage text NOT NULL CHECK (stage IN ('lead', 'qualified', 'proposal', 'won', 'lost')),
    idempotency_key text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
)
""",
    "CREATE INDEX IF NOT EXISTS crm_deals_contact_idx ON crm_deals (contact_id)",
    """
CREATE TABLE IF NOT EXISTS tasks (
    id text PRIMARY KEY,
    title text NOT NULL,
    description text NOT NULL,
    due_date date,
    priority text NOT NULL CHECK (priority IN ('low', 'normal', 'high')),
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
    assignee text,
    idempotency_key text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
)
""",
    """
CREATE TABLE IF NOT EXISTS email_messages (
    id text PRIMARY KEY,
    idempotency_key text UNIQUE,
    message_id_header text NOT NULL,
    from_addr text NOT NULL,
    to_addrs text[] NOT NULL,
    cc_addrs text[] NOT NULL DEFAULT '{}',
    subject text NOT NULL,
    body_text text NOT NULL,
    folder text NOT NULL CHECK (folder IN ('inbox', 'sent')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
)
""",
    "CREATE INDEX IF NOT EXISTS email_messages_folder_idx ON email_messages (folder, created_at)",
)

_NOOP_UPDATE = (
    "ON CONFLICT (idempotency_key) DO UPDATE SET idempotency_key = excluded.idempotency_key"
)
_CONTACT_COLUMNS = "id, name, email, company, phone, tags, created_at"
_DEAL_COLUMNS = "id, contact_id, title, amount, currency, stage, updated_at"
_TASK_COLUMNS = "id, title, description, due_date, priority, status, assignee, created_at"


async def setup_integrations(pool: Pool) -> None:
    """Create the CRM, task and email tables (idempotent; callers serialise concurrent setups)."""
    async with pool.connection() as conn:
        for statement in MIGRATIONS:
            await conn.execute(statement)


async def _fetch(pool: Pool, query: str, params: dict[str, Any]) -> list[DictRow]:
    async with pool.connection() as conn:
        cursor = await conn.execute(query, params)
        return await cursor.fetchall()


async def _fetch_one(pool: Pool, query: str, params: dict[str, Any]) -> DictRow | None:
    rows = await _fetch(pool, query, params)
    return rows[0] if rows else None


class PostgresCrmRepository:
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def search_contacts(self, query: str, limit: int) -> list[Contact]:
        rows = await _fetch(
            self._pool,
            f"""SELECT {_CONTACT_COLUMNS} FROM crm_contacts
            WHERE position(lower(%(q)s) IN lower(name || E'\n' || email || E'\n' || company)) > 0
            ORDER BY name, id LIMIT %(limit)s""",
            {"q": query, "limit": limit},
        )
        return [Contact(**row) for row in rows]

    async def get_contact(self, contact_id: str) -> Contact:
        row = await _fetch_one(
            self._pool,
            f"SELECT {_CONTACT_COLUMNS} FROM crm_contacts WHERE id = %(id)s",
            {"id": contact_id},
        )
        if row is None:
            raise NotFoundError("contact", contact_id)
        return Contact(**row)

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
        row = await _fetch_one(
            self._pool,
            f"""INSERT INTO crm_contacts (id, name, email, company, phone, tags, idempotency_key)
            VALUES (%(id)s, %(name)s, %(email)s, %(company)s, %(phone)s, %(tags)s, %(key)s)
            {_NOOP_UPDATE} RETURNING {_CONTACT_COLUMNS}""",
            {
                "id": uuid4().hex,
                "name": name,
                "email": email,
                "company": company,
                "phone": phone,
                "tags": tags,
                "key": idempotency_key,
            },
        )
        assert row is not None
        return Contact(**row)

    async def list_deals(self, contact_id: str | None, stage: DealStage | None) -> list[Deal]:
        rows = await _fetch(
            self._pool,
            f"""SELECT {_DEAL_COLUMNS} FROM crm_deals
            WHERE (%(contact)s::text IS NULL OR contact_id = %(contact)s)
              AND (%(stage)s::text IS NULL OR stage = %(stage)s)
            ORDER BY created_at, id""",
            {"contact": contact_id, "stage": stage},
        )
        return [Deal(**row) for row in rows]

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
        try:
            row = await _fetch_one(
                self._pool,
                f"""INSERT INTO crm_deals
                (id, contact_id, title, amount, currency, stage, idempotency_key)
                VALUES (%(id)s, %(contact)s, %(title)s, %(amount)s, %(currency)s, %(stage)s,
                        %(key)s)
                {_NOOP_UPDATE} RETURNING {_DEAL_COLUMNS}""",
                {
                    "id": uuid4().hex,
                    "contact": contact_id,
                    "title": title,
                    "amount": amount,
                    "currency": currency,
                    "stage": stage,
                    "key": idempotency_key,
                },
            )
        except ForeignKeyViolation:
            raise NotFoundError("contact", contact_id) from None
        assert row is not None
        return Deal(**row)

    async def update_deal(
        self,
        deal_id: str,
        *,
        amount: Decimal | None = None,
        stage: DealStage | None = None,
        title: str | None = None,
    ) -> Deal:
        row = await _fetch_one(
            self._pool,
            f"""UPDATE crm_deals SET amount = COALESCE(%(amount)s, amount),
                stage = COALESCE(%(stage)s, stage), title = COALESCE(%(title)s, title),
                updated_at = clock_timestamp()
            WHERE id = %(id)s RETURNING {_DEAL_COLUMNS}""",
            {"id": deal_id, "amount": amount, "stage": stage, "title": title},
        )
        if row is None:
            raise NotFoundError("deal", deal_id)
        return Deal(**row)

    async def delete_record(self, kind: RecordKind, record_id: str) -> bool:
        table = "crm_deals" if kind == "deal" else "crm_contacts"
        row = await _fetch_one(
            self._pool, f"DELETE FROM {table} WHERE id = %(id)s RETURNING id", {"id": record_id}
        )
        return row is not None


class PostgresTaskRepository:
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

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
        row = await _fetch_one(
            self._pool,
            f"""INSERT INTO tasks
            (id, title, description, due_date, priority, assignee, idempotency_key)
            VALUES (%(id)s, %(title)s, %(description)s, %(due)s, %(priority)s, %(assignee)s,
                    %(key)s)
            {_NOOP_UPDATE} RETURNING {_TASK_COLUMNS}""",
            {
                "id": uuid4().hex,
                "title": title,
                "description": description,
                "due": due_date,
                "priority": priority,
                "assignee": assignee,
                "key": idempotency_key,
            },
        )
        assert row is not None
        return Task(**row)

    async def list_tasks(
        self, status: TaskStatus | None, assignee: str | None, limit: int
    ) -> list[Task]:
        rows = await _fetch(
            self._pool,
            f"""SELECT {_TASK_COLUMNS} FROM tasks
            WHERE (%(status)s::text IS NULL OR status = %(status)s)
              AND (%(assignee)s::text IS NULL OR assignee = %(assignee)s)
            ORDER BY created_at, id LIMIT %(limit)s""",
            {"status": status, "assignee": assignee, "limit": limit},
        )
        return [Task(**row) for row in rows]

    async def complete_task(self, task_id: str) -> Task:
        row = await _fetch_one(
            self._pool,
            f"UPDATE tasks SET status = 'done' WHERE id = %(id)s RETURNING {_TASK_COLUMNS}",
            {"id": task_id},
        )
        if row is None:
            raise NotFoundError("task", task_id)
        return Task(**row)

    async def delete_task(self, task_id: str) -> bool:
        row = await _fetch_one(
            self._pool, "DELETE FROM tasks WHERE id = %(id)s RETURNING id", {"id": task_id}
        )
        return row is not None


_EMAIL_COLUMNS = (
    "id, message_id_header, from_addr, to_addrs, cc_addrs, subject, body_text, folder, created_at"
)


def _email_from_row(row: DictRow) -> EmailMessage:
    when = {"sent_at" if row["folder"] == "sent" else "received_at": row["created_at"]}
    return EmailMessage(
        id=row["id"],
        message_id_header=row["message_id_header"],
        from_=row["from_addr"],
        to=row["to_addrs"],
        cc=row["cc_addrs"],
        subject=row["subject"],
        body_text=row["body_text"],
        folder=row["folder"],
        **when,
    )


class OutboxEmailGateway:
    """Email kept in PostgreSQL: ``send`` files the message under "sent" and nothing leaves the
    system. The unique idempotency key makes a repeated send return the original message."""

    provider = "outbox"
    retry_safe = True

    def __init__(self, pool: Pool, from_address: str = "agent@acme.com") -> None:
        self._pool = pool
        self._from = from_address

    async def send(self, email: OutgoingEmail, *, idempotency_key: str) -> SendResult:
        row = await _fetch_one(
            self._pool,
            f"""INSERT INTO email_messages (id, idempotency_key, message_id_header, from_addr,
                to_addrs, cc_addrs, subject, body_text, folder)
            VALUES (%(id)s, %(key)s, %(header)s, %(from)s, %(to)s, %(cc)s, %(subject)s, %(body)s,
                'sent')
            {_NOOP_UPDATE} RETURNING id, message_id_header, (xmax = 0) AS inserted""",
            {
                "id": uuid4().hex,
                "key": idempotency_key,
                "header": message_id_for(idempotency_key),
                "from": self._from,
                "to": email.to,
                "cc": email.cc,
                "subject": email.subject,
                "body": email.body_text,
            },
        )
        assert row is not None
        return SendResult(
            id=row["id"],
            message_id_header=row["message_id_header"],
            provider=self.provider,
            deduplicated=not row["inserted"],
        )

    async def add_inbox_message(
        self,
        *,
        from_: str,
        to: list[str],
        subject: str,
        body_text: str,
        cc: list[str] | None = None,
    ) -> EmailMessage:
        """Deliver a message into the inbox (demos and tests)."""
        row = await _fetch_one(
            self._pool,
            f"""INSERT INTO email_messages (id, message_id_header, from_addr, to_addrs, cc_addrs,
                subject, body_text, folder)
            VALUES (%(id)s, %(header)s, %(from)s, %(to)s, %(cc)s, %(subject)s, %(body)s, 'inbox')
            RETURNING {_EMAIL_COLUMNS}""",
            {
                "id": (new_id := uuid4().hex),
                "header": f"<{new_id}@{MESSAGE_ID_DOMAIN}>",
                "from": from_,
                "to": to,
                "cc": cc or [],
                "subject": subject,
                "body": body_text,
            },
        )
        assert row is not None
        return _email_from_row(row)

    async def search(
        self, query: str, *, folder: Folder = "inbox", limit: int = 10
    ) -> list[EmailMessage]:
        rows = await _fetch(
            self._pool,
            f"""SELECT {_EMAIL_COLUMNS} FROM email_messages
            WHERE folder = %(folder)s AND position(lower(%(q)s) IN lower(
                from_addr || E'\n' || array_to_string(to_addrs || cc_addrs, E'\n')
                || E'\n' || subject || E'\n' || body_text)) > 0
            ORDER BY created_at DESC, id LIMIT %(limit)s""",
            {"folder": folder, "q": query, "limit": limit},
        )
        return [_email_from_row(row) for row in rows]

    async def get(self, message_id: str) -> EmailMessage:
        row = await _fetch_one(
            self._pool,
            f"SELECT {_EMAIL_COLUMNS} FROM email_messages WHERE id = %(id)s",
            {"id": message_id},
        )
        if row is None:
            raise NotFoundError("email", message_id)
        return _email_from_row(row)
