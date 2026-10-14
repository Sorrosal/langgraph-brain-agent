"""Agent tools to read the rules and add new ones from the chat (admins only, always approved).

The agent never rewrites rule files. ``add_rule`` takes the fields of one guideline or hard rule
and appends it to ``chat.yaml``, a file only this tool writes (every ``*.yaml`` in the rules
directory is merged). Existing rules therefore cannot be removed, relaxed or corrupted from the
chat; that stays on the Brain page.
"""

import asyncio
from pathlib import Path
from typing import Any, Literal, Self

import structlog
import yaml
from langchain_core.messages import ToolCall
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException, tool
from pydantic import BaseModel, Field, ValidationError, model_validator

from brain_agent.brain.rules import RulesEngine, RulesError, validate_candidate, write_rule_file
from brain_agent.hitl.policy import PolicyVerdict
from brain_agent.persistence.users import UserRepository
from brain_agent.tools.memory_tools import user_id_of

logger = structlog.get_logger(__name__)

CHAT_RULES_FILE = "chat.yaml"


class AddRuleArgs(BaseModel):
    kind: Literal["guideline", "hard_rule"] = Field(
        description="guideline: advice in the prompt; hard_rule: enforced before a tool runs."
    )
    id: str = Field(
        pattern=r"^[a-z0-9][a-z0-9-]{1,62}$",
        description="Unique kebab-case id, e.g. no-bulk-tasks.",
    )
    text: str = Field(
        min_length=3,
        max_length=500,
        description="The guideline itself, or what the hard rule enforces (its description).",
    )
    priority: int = Field(default=5, ge=0, le=10, description="Guidelines: higher comes first.")
    tool: str | None = Field(
        default=None,
        max_length=100,
        description="Hard rules: the tool it applies to (exact name or fnmatch glob).",
    )
    action: Literal["require_approval", "block"] = Field(
        default="require_approval", description="Hard rules: ask a human first, or refuse."
    )
    risk: Literal["low", "medium", "high"] = Field(default="high", description="Hard rules.")
    reason: str | None = Field(
        default=None, max_length=300, description="Hard rules: shown when the rule triggers."
    )

    @model_validator(mode="after")
    def _hard_rules_name_a_tool(self) -> Self:
        if self.kind == "hard_rule" and not self.tool:
            raise ValueError("a hard rule needs the tool it applies to")
        return self


def _with_rule(directory: Path, rule: AddRuleArgs) -> str:
    """The new text of ``chat.yaml`` with ``rule`` appended."""
    path = directory / CHAT_RULES_FILE
    data: dict[str, Any] = (
        yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else None
    ) or {"version": 1}
    if rule.kind == "guideline":
        entry: dict[str, Any] = {"id": rule.id, "text": rule.text, "priority": rule.priority}
        data.setdefault("guidelines", []).append(entry)
    else:
        entry = {
            "id": rule.id,
            "description": rule.text,
            "when": {"tool": rule.tool},
            "action": rule.action,
            "risk": rule.risk,
        }
        if rule.reason:
            entry["reason"] = rule.reason
        data.setdefault("hard_rules", []).append(entry)
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def _candidate(directory: Path, args: dict[str, Any]) -> str:
    """Validated ``chat.yaml`` text for an ``add_rule`` call.

    Raises:
        ValidationError: malformed arguments.
        RulesError: the resulting rule set is invalid (e.g. a duplicate id).
    """
    content = _with_rule(directory, AddRuleArgs.model_validate(args))
    validate_candidate(directory, CHAT_RULES_FILE, content)
    return content


class RulesEditPolicy:
    """Checks an ``add_rule`` call at the approval gate, before anyone is asked to approve it.

    An invalid rule is refused there and the agent gets the reason back to correct itself; the
    tool repeats the check when it runs (an edited decision, or rules changed meanwhile).
    """

    def __init__(self, directory: Path, engine: RulesEngine) -> None:
        self._directory = directory
        self._engine = engine

    def evaluate(self, tool_call: ToolCall, tool: BaseTool | None) -> PolicyVerdict | None:
        if tool_call["name"] != "add_rule":
            return None
        # ponytail: synchronous read of the small rule files inside the gate; move to a thread
        # if rule sets ever grow large.
        try:
            _candidate(self._directory, tool_call["args"])
        except (ValidationError, RulesError) as exc:
            return PolicyVerdict(
                risk="high",
                reason=f"Invalid rule: {exc}. Fix the arguments and retry.",
                blocked=True,
                rule_ids=("rules-validation",),
            )
        return None


def _read_all(directory: Path) -> str:
    return "\n\n".join(
        f"# --- {p.name} ---\n{p.read_text(encoding='utf-8')}"
        for p in sorted(directory.glob("*.yaml"))
    )


def build_rules_tools(
    directory: Path, engine: RulesEngine, users: UserRepository, lock: asyncio.Lock
) -> list[BaseTool]:
    """``read_rules`` and ``add_rule``; ``lock`` is the one the rules API uses."""

    @tool
    async def read_rules() -> str:
        """Return the raw YAML of every rule file (persona, guidelines and hard rules)."""
        return await asyncio.to_thread(_read_all, directory)

    @tool(args_schema=AddRuleArgs)
    async def add_rule(config: RunnableConfig, **fields: Any) -> str:
        """Add one guideline or hard rule the user asked for. Existing rules cannot be changed
        or removed from the chat. A human approves the new rule before it takes effect."""
        user = await users.get(user_id_of(config))
        if user is None or user.role != "admin":
            raise ToolException("Only admins can change the rules; ask an admin to do it.")
        async with lock:
            try:
                content = await asyncio.to_thread(_candidate, directory, fields)
            except (ValidationError, RulesError) as exc:
                raise ToolException(f"Invalid rule, nothing was saved: {exc}") from exc
            await asyncio.to_thread(write_rule_file, directory, CHAT_RULES_FILE, content)
            engine.reload(force=True)
        logger.info(
            "rules_updated",
            via="agent",
            user_id=user.id,
            rule_id=fields.get("id"),
            version_hash=engine.ruleset.version_hash,
        )
        return f"Added rule {fields.get('id')}; rules version {engine.ruleset.version_hash[:12]}."

    add_rule.handle_tool_error = True
    read_rules.metadata = {"risk": "low", "retry_safe": True, "read_only": True}
    # Approval is enforced in code, so no rule file can switch it off. Appending the same rule
    # twice fails on the duplicate id, so a replay after a crash cannot add it twice.
    add_rule.metadata = {
        "risk": "high",
        "retry_safe": True,
        "approval_reason": "A new rule changes how the agent behaves; a human checks it first.",
    }
    return [read_rules, add_rule]
