"""The agent's brain: the user's long-term memories and the rules in force."""

import asyncio
from datetime import datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Path, Query, Request, Response
from pydantic import BaseModel, Field, StringConstraints

from brain_agent.api.auth import AdminUser, Container, CurrentUser
from brain_agent.api.errors import ApiError
from brain_agent.api.ratelimit import enforce
from brain_agent.brain.knowledge_graph import build_knowledge_graph
from brain_agent.brain.memory import MemoryKind, MemoryRecord
from brain_agent.brain.rules import (
    MAX_RULES_BYTES,
    RULE_FILENAME,
    RulesError,
    validate_candidate,
    write_rule_file,
)
from brain_agent.errors import NotFoundError

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["brain"])


class MemoryIn(BaseModel):
    kind: MemoryKind
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class MemoryOut(BaseModel):
    id: str
    kind: MemoryKind
    text: str
    source_thread_id: str | None
    created_at: datetime
    score: float | None

    @classmethod
    def of(cls, record: MemoryRecord) -> "MemoryOut":
        return cls(
            id=record.id,
            kind=record.kind,
            text=record.text,
            source_thread_id=record.source_thread_id,
            created_at=record.created_at,
            score=record.score,
        )


@router.get("/memories", response_model=list[MemoryOut])
async def list_memories(
    container: Container, user: CurrentUser, kind: MemoryKind | None = None
) -> list[MemoryOut]:
    return [MemoryOut.of(m) for m in await container.memory.list(user.id, kind)]


@router.get("/memories/search", response_model=list[MemoryOut])
async def search_memories(
    container: Container,
    user: CurrentUser,
    q: Annotated[str, Query(min_length=1, max_length=500)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[MemoryOut]:
    return [MemoryOut.of(m) for m in await container.memory.recall(user.id, q, limit=limit)]


@router.post("/memories", status_code=201, response_model=MemoryOut)
async def create_memory(body: MemoryIn, container: Container, user: CurrentUser) -> MemoryOut:
    record = await container.memory.remember(user.id, body.kind, body.text, source_thread_id=None)
    return MemoryOut.of(record)


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(memory_id: str, container: Container, user: CurrentUser) -> Response:
    if not await container.memory.forget(user.id, memory_id):
        raise NotFoundError("memory", memory_id)
    return Response(status_code=204)


class OrgKnowledgeIn(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


@router.get("/org-knowledge", response_model=list[MemoryOut])
async def list_org_knowledge(container: Container, _: CurrentUser) -> list[MemoryOut]:
    """Shared facts every user's agent can recall."""
    return [MemoryOut.of(m) for m in await container.memory.list_org_knowledge()]


@router.post("/org-knowledge", status_code=201, response_model=MemoryOut)
async def add_org_knowledge(
    body: OrgKnowledgeIn, container: Container, admin: AdminUser
) -> MemoryOut:
    record = await container.memory.add_org_knowledge(body.text, source=None)
    logger.info("org_knowledge_added", user_id=admin.id, memory_id=record.id)
    return MemoryOut.of(record)


@router.delete("/org-knowledge/{memory_id}", status_code=204)
async def delete_org_knowledge(memory_id: str, container: Container, admin: AdminUser) -> Response:
    if not await container.memory.forget_org_knowledge(memory_id):
        raise NotFoundError("org knowledge", memory_id)
    logger.info("org_knowledge_deleted", user_id=admin.id, memory_id=memory_id)
    return Response(status_code=204)


GRAPH_LIMITS = {"memories": 200, "org": 100, "contacts": 100, "deals": 100, "tasks": 50}


@router.get("/brain/graph")
async def knowledge_graph(container: Container, user: CurrentUser) -> dict[str, Any]:
    """Everything the agent knows for this user, as nodes and edges (see ``knowledge_graph``)."""
    memories, org, contacts, deals, tasks = await asyncio.gather(
        container.memory.list(user.id),
        container.memory.list_org_knowledge(),
        container.crm.search_contacts("", GRAPH_LIMITS["contacts"] + 1),
        container.crm.list_deals(None, None),
        container.tasks.list_tasks(None, None, GRAPH_LIMITS["tasks"] + 1),
    )
    sizes = {
        "memories": len(memories),
        "org": len(org),
        "contacts": len(contacts),
        "deals": len(deals),
        "tasks": len(tasks),
    }
    truncated = any(sizes[k] > limit for k, limit in GRAPH_LIMITS.items())
    return build_knowledge_graph(
        user_name=user.display_name,
        memories=memories[: GRAPH_LIMITS["memories"]],
        org_knowledge=org[: GRAPH_LIMITS["org"]],
        ruleset=container.rules.ruleset,
        contacts=contacts[: GRAPH_LIMITS["contacts"]],
        deals=deals[: GRAPH_LIMITS["deals"]],
        tasks=tasks[: GRAPH_LIMITS["tasks"]],
        truncated=truncated,
    )


class RuleFileOut(BaseModel):
    name: str
    content: str


class RulesOut(BaseModel):
    version_hash: str
    persona: str | None
    guidelines: list[dict[str, Any]]
    hard_rules: list[dict[str, Any]]
    files: list[RuleFileOut]
    """The raw YAML of each file, in load order."""


class RuleUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_RULES_BYTES)
    """The complete YAML text of the file."""


class RuleSaved(BaseModel):
    filename: str
    version_hash: str


def _read_files(container: Container) -> list[RuleFileOut]:
    directory = container.settings.rules_dir
    return [
        RuleFileOut(name=p.name, content=p.read_text(encoding="utf-8"))
        for p in sorted(directory.glob("*.yaml"))
    ]


@router.get("/rules", response_model=RulesOut)
async def get_rules(container: Container, _: CurrentUser) -> RulesOut:
    ruleset = container.rules.ruleset
    dumped = ruleset.model_dump(mode="json", by_alias=True, exclude_unset=True)
    return RulesOut(
        version_hash=ruleset.version_hash,
        persona=ruleset.persona,
        guidelines=dumped.get("guidelines", []),
        hard_rules=dumped.get("hard_rules", []),
        files=await asyncio.to_thread(_read_files, container),
    )


@router.put("/rules/{filename}", response_model=RuleSaved)
async def put_rule(
    filename: Annotated[str, Path(pattern=RULE_FILENAME, max_length=100)],
    body: RuleUpdate,
    container: Container,
    admin: AdminUser,
    request: Request,
) -> RuleSaved:
    """Replace (or add) one rule file. The whole resulting rule set is validated before
    anything is written, and the file is swapped atomically."""
    enforce(request, "rules", admin.id, container.settings.rate_limit_rules_writes_per_minute, 60)
    directory = container.settings.rules_dir
    async with container.rules_lock:
        try:
            await asyncio.to_thread(validate_candidate, directory, filename, body.content)
        except RulesError as exc:
            raise ApiError(422, "invalid_rules", str(exc)) from exc
        await asyncio.to_thread(write_rule_file, directory, filename, body.content)
        container.rules.reload(force=True)  # do not wait for the next fingerprint check
        version_hash = container.rules.ruleset.version_hash
    logger.info("rules_updated", user_id=admin.id, filename=filename, version_hash=version_hash)
    return RuleSaved(filename=filename, version_hash=version_hash)
