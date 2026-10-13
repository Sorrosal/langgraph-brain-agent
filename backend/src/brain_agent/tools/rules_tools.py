"""Agent tools to read and change the rule files from the chat (admins only, always approved)."""

import asyncio
from pathlib import Path

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, ToolException, tool
from pydantic import BaseModel, Field

from brain_agent.brain.rules import (
    MAX_RULES_BYTES,
    RULE_FILENAME,
    RulesEngine,
    RulesError,
    validate_candidate,
    write_rule_file,
)
from brain_agent.persistence.users import UserRepository
from brain_agent.tools.memory_tools import user_id_of


class UpdateRulesFileArgs(BaseModel):
    filename: str = Field(
        pattern=RULE_FILENAME, max_length=100, description="Rule file, e.g. default.yaml."
    )
    content: str = Field(
        min_length=1,
        max_length=MAX_RULES_BYTES,
        description="The complete new YAML text of the file (not a diff). Read it first.",
    )


def _read_all(directory: Path) -> str:
    return "\n\n".join(
        f"# --- {p.name} ---\n{p.read_text(encoding='utf-8')}"
        for p in sorted(directory.glob("*.yaml"))
    )


def build_rules_tools(
    directory: Path, engine: RulesEngine, users: UserRepository, lock: asyncio.Lock
) -> list[BaseTool]:
    """``read_rules`` and ``update_rules_file``; ``lock`` is the one the rules API uses."""

    @tool
    async def read_rules() -> str:
        """Return the raw YAML of every rule file (persona, guidelines and hard rules)."""
        return await asyncio.to_thread(_read_all, directory)

    @tool(args_schema=UpdateRulesFileArgs)
    async def update_rules_file(filename: str, content: str, config: RunnableConfig) -> str:
        """Replace one rule file with new YAML, e.g. to add a guideline or hard rule the user
        asked for. Call read_rules first and send the whole file. A human approves the change."""
        user = await users.get(user_id_of(config))
        if user is None or user.role != "admin":
            raise ToolException("Only admins can change the rules; ask an admin to do it.")
        async with lock:
            try:
                await asyncio.to_thread(validate_candidate, directory, filename, content)
            except RulesError as exc:
                raise ToolException(f"Invalid rules, nothing was saved: {exc}") from exc
            await asyncio.to_thread(write_rule_file, directory, filename, content)
            engine.reload(force=True)
        return f"Saved {filename}; rules version {engine.ruleset.version_hash[:12]} is in force."

    update_rules_file.handle_tool_error = True
    read_rules.metadata = {"risk": "low", "retry_safe": True, "read_only": True}
    # Approval is enforced in code, so no rule file can switch it off. Rewriting the same text
    # is harmless, so a replay after a crash is safe.
    update_rules_file.metadata = {
        "risk": "high",
        "retry_safe": True,
        "approval_reason": "Changing the agent's rules needs a human check.",
    }
    return [read_rules, update_rules_file]
