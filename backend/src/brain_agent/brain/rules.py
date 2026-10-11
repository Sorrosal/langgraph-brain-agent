"""Declarative rules: models, YAML loading, matching and hot reloading.

Hard rules are enforced in code before any tool runs; guidelines and the persona only shape the
system prompt. See ``rules/README.md`` for the file format.
"""

import hashlib
import json
import os
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Literal, Protocol, Self

import structlog
import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from brain_agent.errors import BrainAgentError
from brain_agent.hitl.models import Risk

logger = structlog.get_logger(__name__)

RuleAction = Literal["require_approval", "block"]
_MISSING = object()


class RulesError(BrainAgentError):
    """Raised when the rule files cannot be loaded."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ArgCondition(_Model):
    """Operators applied to one argument; every operator given must hold."""

    equals: Any = _MISSING
    not_equals: Any = _MISSING
    in_: list[Any] | None = Field(default=None, alias="in")
    not_in: list[Any] | None = None
    matches: str | None = None
    not_matches: str | None = None
    any_not_matches: str | None = None
    gt: float | None = None
    gte: float | None = None
    lt: float | None = None
    lte: float | None = None
    exists: bool | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        given = self.model_fields_set
        if not given:
            raise ValueError("a condition needs at least one operator")
        for name in ("matches", "not_matches", "any_not_matches"):
            pattern = getattr(self, name)
            if pattern is not None:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    raise ValueError(f"invalid regex in {name!r}: {exc}") from exc
        return self

    def holds(self, value: Any) -> bool:
        """Whether ``value`` (``_MISSING`` when absent) satisfies every operator."""
        if self.exists is not None and self.exists != (value is not _MISSING):
            return False
        if value is _MISSING:
            return self._holds_for_missing()
        if self.any_not_matches is not None and not _any_token_fails(self.any_not_matches, value):
            return False
        # A list satisfies a condition when any element does; ``exists`` concerns the list.
        candidates = value if isinstance(value, list) else [value]
        return any(self._holds_for(item) for item in candidates)

    def _holds_for_missing(self) -> bool:
        return self.equals is _MISSING and all(
            getattr(self, op) is None for op in ("in_", "matches", "gt", "gte", "lt", "lte")
        )

    def _holds_for(self, item: Any) -> bool:
        if self.equals is not _MISSING and item != self.equals:
            return False
        if self.not_equals is not _MISSING and item == self.not_equals:
            return False
        if self.in_ is not None and item not in self.in_:
            return False
        if self.not_in is not None and item in self.not_in:
            return False
        text = item if isinstance(item, str | int | float) else None
        if self.matches is not None and (text is None or not re.search(self.matches, str(text))):
            return False
        if (
            self.not_matches is not None
            and text is not None
            and re.search(self.not_matches, str(text))
        ):
            return False
        return self._compare(item)

    def _compare(self, item: Any) -> bool:
        bounds = (self.gt, self.gte, self.lt, self.lte)
        if all(bound is None for bound in bounds):
            return True
        number = _as_number(item)
        if number is None:
            return False
        gt, gte, lt, lte = bounds
        return (
            (gt is None or number > gt)
            and (gte is None or number >= gte)
            and (lt is None or number < lt)
            and (lte is None or number <= lte)
        )


_TOKEN_SPLIT = re.compile(r"[,;\s]+")


def _any_token_fails(pattern: str, value: Any) -> bool:
    """Whether some recipient-like token of ``value`` does not match ``pattern``.

    Strings are split on commas, semicolons and whitespace (lists: per element), so one string
    holding several addresses is judged address by address. No tokens (an empty or blank
    value) counts as failing, to fail closed.
    """
    items = value if isinstance(value, list) else [value]
    tokens = [t for item in items for t in _TOKEN_SPLIT.split(str(item)) if t]
    return not tokens or any(re.search(pattern, token) is None for token in tokens)


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float | Decimal):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _lookup(args: Mapping[str, Any], path: str) -> Any:
    """Resolve a dotted path through dicts and list indexes; ``_MISSING`` when absent."""
    current: Any = args
    for part in path.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdecimal() and int(part) < len(current):
            current = current[int(part)]
        else:
            return _MISSING
    return current


class RuleCondition(_Model):
    tool: str
    """Exact tool name or ``fnmatch`` glob."""
    args: dict[str, ArgCondition] = Field(default_factory=dict)


class Guideline(_Model):
    id: str
    text: str
    priority: int = 0


class HardRule(_Model):
    id: str
    description: str
    when: RuleCondition
    action: RuleAction
    risk: Risk = "high"
    reason: str | None = None
    """Shown to the user and reviewer; defaults to the description."""

    @property
    def message(self) -> str:
        return self.reason or self.description

    def matches(self, tool_name: str, args: Mapping[str, Any]) -> bool:
        if not fnmatchcase(tool_name, self.when.tool):
            return False
        return all(cond.holds(_lookup(args, path)) for path, cond in self.when.args.items())


class RuleSet(_Model):
    """All rules in force, merged from every file."""

    persona: str | None = None
    guidelines: tuple[Guideline, ...] = ()
    hard_rules: tuple[HardRule, ...] = ()
    version_hash: str = ""
    """SHA-256 of the canonical content; changes whenever any rule changes."""


class _RuleFile(_Model):
    version: Literal[1]
    persona: str | None = None
    guidelines: list[Guideline] = Field(default_factory=list)
    hard_rules: list[HardRule] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RuleMatch:
    """A hard rule that applies to a tool call."""

    rule_id: str
    action: RuleAction
    risk: Risk
    reason: str


def _parse_file(path: Path, text: str | None = None) -> _RuleFile:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8") if text is None else text) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise RulesError(f"{path.name}: cannot read rules: {exc}") from exc
    try:
        return _RuleFile.model_validate(raw)
    except ValidationError as exc:
        details = "; ".join(f"{_describe(raw, e['loc'])}: {e['msg']}" for e in exc.errors())
        raise RulesError(f"{path.name}: invalid rules: {details}") from exc


def _describe(raw: Any, loc: tuple[int | str, ...]) -> str:
    """Error location, naming the rule by id (``hard_rules[my-rule].when...``) when possible."""
    parts = [str(part) for part in loc]
    if len(loc) >= 2 and isinstance(raw, dict) and isinstance(loc[1], int):
        items = raw.get(loc[0])
        if isinstance(items, list) and loc[1] < len(items) and isinstance(items[loc[1]], dict):
            parts[1] = f"[{items[loc[1]].get('id', loc[1])}]"
            return parts[0] + ".".join([parts[1], *parts[2:]]).rstrip(".")
    return ".".join(parts)


def _rule_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.yaml"), key=lambda p: p.name)


def load_rules(directory: Path, *, replacing: Mapping[str, str] | None = None) -> RuleSet:
    """Merge every ``*.yaml`` file of ``directory`` (sorted by filename) into one rule set.

    ``replacing`` maps file names to YAML text used instead of (or in addition to) what is on
    disk, to check a change before writing it.

    Raises:
        RulesError: unreadable or invalid file, duplicate ids, or several personas.
    """
    replacing = replacing or {}
    persona: str | None = None
    persona_file = ""
    guidelines: list[Guideline] = []
    hard_rules: list[HardRule] = []
    seen: dict[str, str] = {}
    paths = {p.name: p for p in _rule_files(directory)}
    paths |= {name: directory / name for name in replacing}
    for name in sorted(paths):
        path = paths[name]
        parsed = _parse_file(path, replacing.get(name))
        if parsed.persona is not None:
            if persona is not None:
                raise RulesError(f"{path.name}: persona already defined in {persona_file}")
            persona, persona_file = parsed.persona, path.name
        ids = [*(g.id for g in parsed.guidelines), *(r.id for r in parsed.hard_rules)]
        for rule_id in ids:
            if rule_id in seen:
                raise RulesError(
                    f"{path.name}: Duplicate rule id {rule_id!r} (also in {seen[rule_id]})"
                )
            seen[rule_id] = path.name
        guidelines.extend(parsed.guidelines)
        hard_rules.extend(parsed.hard_rules)
    ruleset = RuleSet(persona=persona, guidelines=tuple(guidelines), hard_rules=tuple(hard_rules))
    dumped = ruleset.model_dump(mode="json", by_alias=True, exclude_unset=True)
    canonical = json.dumps(dumped, sort_keys=True)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return ruleset.model_copy(update={"version_hash": digest})


def validate_candidate(directory: Path, filename: str, content: str) -> RuleSet:
    """The rule set that results from writing ``content`` to ``filename``, fully validated.

    Raises:
        RulesError: the result is invalid or defines no hard rules.
    """
    return _require_hard_rules(load_rules(directory, replacing={filename: content}))


def write_rule_file(directory: Path, filename: str, content: str) -> None:
    """Replace ``filename`` atomically: readers see the old or the new file, never half of one."""
    temporary = directory / f".{filename}.{uuid.uuid4().hex}.tmp"
    try:
        temporary.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temporary, directory / filename)
    finally:
        temporary.unlink(missing_ok=True)


class RuleSource(Protocol):
    """Where rules come from; phase 5 adds a database-backed implementation."""

    def load(self) -> RuleSet: ...

    def fingerprint(self) -> str:
        """Cheap token that changes whenever :meth:`load` would return something new."""
        ...


class YamlRuleSource:
    """Rules from a directory of YAML files, fingerprinted by file name, mtime and size."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def load(self) -> RuleSet:
        return load_rules(self._directory)

    def fingerprint(self) -> str:
        parts = []
        for path in _rule_files(self._directory):
            stat = path.stat()
            parts.append(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}")
        return "|".join(parts)


_UNREADABLE = "<unreadable>"


def _require_hard_rules(ruleset: RuleSet) -> RuleSet:
    if not ruleset.hard_rules:
        raise RulesError("the rules define no hard rules; refusing to run unconstrained")
    return ruleset


class RulesEngine:
    """Evaluates hard rules against tool calls, reloading from its source when it changes."""

    def __init__(self, ruleset: RuleSet, source: RuleSource | None = None) -> None:
        self._ruleset = ruleset
        self._source = source
        self._fingerprint = source.fingerprint() if source else ""

    @classmethod
    def from_source(cls, source: RuleSource) -> Self:
        """Engine over ``source``'s current rules.

        Fails closed: raises :class:`RulesError` if the rules are invalid or define no hard
        rules, instead of starting an agent that nothing constrains.
        """
        fingerprint = source.fingerprint()
        engine = cls(_require_hard_rules(source.load()), source)
        engine._fingerprint = fingerprint
        return engine

    @property
    def ruleset(self) -> RuleSet:
        """Current rules; picks up source changes, keeping the last good set if they are invalid."""
        try:
            self.reload()
        except RulesError as exc:
            logger.error("rules_reload_failed", error=str(exc))
        return self._ruleset

    def reload(self, *, force: bool = False) -> bool:
        """Reload when the source changed (or ``force``); returns whether rules were replaced.

        Raises:
            RulesError: the new rules are invalid; the previous set stays active and the broken
                state is not retried until the source changes again.
        """
        if self._source is None:
            return False
        try:
            fingerprint = self._source.fingerprint()
        except OSError:  # e.g. a file deleted mid-scan: treat as changed and try to reload
            fingerprint = _UNREADABLE
        if fingerprint == self._fingerprint and not force:
            return False
        self._fingerprint = fingerprint
        self._ruleset = _require_hard_rules(self._source.load())
        return True

    def evaluate(self, tool_name: str, args: Mapping[str, Any]) -> list[RuleMatch]:
        """Hard rules matching the call, in definition order."""
        return [
            RuleMatch(rule.id, rule.action, rule.risk, rule.message)
            for rule in self.ruleset.hard_rules
            if rule.matches(tool_name, args)
        ]
