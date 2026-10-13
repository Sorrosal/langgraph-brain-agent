"""Long-term memory on a LangGraph store.

User memories live under ``("memories", user_id, kind)``; organisation knowledge, readable by
every user but written only through :meth:`MemoryService.add_org_knowledge`, under
``("org", "knowledge")``. Items are keyed by a hash of ``kind`` and the normalised text, so
saving the same fact twice is a no-op (this also makes memory writes safe to replay).

Semantic recall needs a store created with an embeddings index on ``text`` (see
``open_persistence(..., embeddings=...)``). Without an index recall degrades to the most
recent memories first, with no scores.
"""

import builtins
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, get_args

from langgraph.store.base import BaseStore, Item, SearchItem

MemoryKind = Literal["fact", "preference", "episode"]
MEMORY_KINDS: tuple[MemoryKind, ...] = get_args(MemoryKind)

_ORG_NAMESPACE = ("org", "knowledge")
_LIST_LIMIT = 1000


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """One stored memory; ``score`` is the similarity to the query when recalled semantically."""

    id: str
    kind: MemoryKind
    text: str
    source_thread_id: str | None
    created_at: datetime
    score: float | None = None


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _key(kind: str, text: str) -> str:
    return hashlib.sha256(f"{kind}\0{_normalize(text)}".encode()).hexdigest()[:32]


def _label(user_id: str) -> str:
    """Namespace labels may not be empty or contain periods; escape them reversibly."""
    return user_id.replace("%", "%25").replace(".", "%2E") or "%00"


def _record(item: Item | SearchItem) -> MemoryRecord:
    value = item.value
    return MemoryRecord(
        id=item.key,
        kind=value["kind"],
        text=value["text"],
        source_thread_id=value.get("source_thread_id"),
        created_at=item.created_at,
        score=getattr(item, "score", None),
    )


def _rank(records: Sequence[MemoryRecord], limit: int) -> builtins.list[MemoryRecord]:
    """Best first: by score when the store produced scores, otherwise newest first."""
    if any(r.score is not None for r in records):
        ordered = sorted(
            records, key=lambda r: r.score if r.score is not None else -1, reverse=True
        )
    else:
        ordered = sorted(records, key=lambda r: r.created_at, reverse=True)
    return ordered[:limit]


class MemoryService:
    """Remember, recall, list and forget memories of a user, plus shared organisation knowledge."""

    def __init__(self, store: BaseStore) -> None:
        self._store = store

    def _namespace(self, user_id: str, kind: str) -> tuple[str, str, str]:
        return ("memories", _label(user_id), kind)

    async def _put(
        self, namespace: tuple[str, ...], kind: MemoryKind, text: str, source: str | None
    ) -> MemoryRecord:
        key = _key(kind, text)
        existing = await self._store.aget(namespace, key)
        if existing is None:
            value = {"kind": kind, "text": text.strip(), "source_thread_id": source}
            await self._store.aput(namespace, key, value, index=["text"])
            existing = await self._store.aget(namespace, key)
        assert existing is not None
        return _record(existing)

    async def remember(
        self, user_id: str, kind: MemoryKind, text: str, *, source_thread_id: str | None
    ) -> MemoryRecord:
        """Store ``text``; an existing memory with the same normalised text is returned as is."""
        if kind not in MEMORY_KINDS:
            raise ValueError(f"unknown memory kind {kind!r}")
        if not text.strip():
            raise ValueError("memory text must not be empty")
        return await self._put(self._namespace(user_id, kind), kind, text, source_thread_id)

    async def replace(
        self,
        user_id: str,
        memory_id: str,
        kind: MemoryKind,
        text: str,
        *,
        source_thread_id: str | None,
    ) -> MemoryRecord:
        """Replace one of the user's memories with a corrected or refined version."""
        await self.forget(user_id, memory_id)
        return await self.remember(user_id, kind, text, source_thread_id=source_thread_id)

    async def add_org_knowledge(self, text: str, *, source: str | None = None) -> MemoryRecord:
        """Add a shared fact visible to every user (no agent tool does this)."""
        return await self._put(_ORG_NAMESPACE, "fact", text, source)

    async def _search(
        self, namespace: tuple[str, ...], query: str | None, limit: int
    ) -> builtins.list[MemoryRecord]:
        items = await self._store.asearch(namespace, query=query, limit=limit)
        records = [_record(item) for item in items]
        if query is not None and records and records[0].score is None:
            # No embeddings index: the store ignored the query and its order is not guaranteed
            # to be recency, so list everything and let _rank pick the newest.
            records = await self._search(namespace, None, _LIST_LIMIT)
        return records

    async def recall(
        self,
        user_id: str,
        query: str,
        *,
        limit: int = 5,
        kinds: Sequence[MemoryKind] | None = None,
        include_org: bool = False,
    ) -> builtins.list[MemoryRecord]:
        """Memories most relevant to ``query``, best first (org knowledge only if requested)."""
        found: builtins.list[MemoryRecord] = []
        for kind in kinds if kinds is not None else MEMORY_KINDS:
            found += await self._search(self._namespace(user_id, kind), query, limit)
        if include_org:
            found += await self._search(_ORG_NAMESPACE, query, limit)
        return _rank(found, limit)

    async def forget(self, user_id: str, memory_id: str) -> bool:
        """Delete one of the user's memories; ``False`` if there was none with that id."""
        deleted = False
        for kind in MEMORY_KINDS:
            namespace = self._namespace(user_id, kind)
            if await self._store.aget(namespace, memory_id) is not None:
                await self._store.adelete(namespace, memory_id)
                deleted = True
        return deleted

    async def list(
        self, user_id: str, kind: MemoryKind | None = None
    ) -> builtins.list[MemoryRecord]:
        """The user's memories, newest first."""
        found: builtins.list[MemoryRecord] = []
        for k in (kind,) if kind else MEMORY_KINDS:
            found += await self._search(self._namespace(user_id, k), None, _LIST_LIMIT)
        return _rank(found, _LIST_LIMIT)


def format_memories(memories: Sequence[MemoryRecord]) -> str:
    """Prompt block for recalled memories, or an empty string when there are none."""
    if not memories:
        return ""
    lines = "\n".join(f"- ({m.kind}) {m.text}" for m in memories)
    return f"Relevant long-term memory (may be outdated; verify before acting):\n{lines}"
