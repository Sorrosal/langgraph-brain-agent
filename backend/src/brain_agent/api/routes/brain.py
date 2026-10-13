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
