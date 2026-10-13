"""System prompt assembled from the rule set."""

from datetime import datetime

from brain_agent.brain.rules import RuleSet

DEFAULT_PERSONA = (
    "You are Brain Agent, a careful business operations assistant. "
    "Use the available tools when they help, and answer concisely."
)


def build_system_prompt(
    ruleset: RuleSet, *, now: datetime | None = None, extra_context: str | None = None
) -> str:
    """Persona, guidelines (priority desc, then id), hard-rule summary and optional context.

    The output depends only on the arguments: pass ``now`` explicitly to include the date.
    """
    sections = [(ruleset.persona or DEFAULT_PERSONA).strip()]
    if ruleset.guidelines:
        ordered = sorted(ruleset.guidelines, key=lambda g: (-g.priority, g.id))
        lines = "\n".join(f"- {g.text.strip()}" for g in ordered)
        sections.append(f"Guidelines:\n{lines}")
    if ruleset.hard_rules:
        lines = "\n".join(f"- {r.description.strip()}" for r in ruleset.hard_rules)
        sections.append(
            "Hard rules (enforced by the system):\n"
            "The system checks these automatically before any tool runs: calls that break them "
            "are blocked or held for human approval. You request approval by calling the tool: "
            "the call itself pauses the run and shows the user an approval card. There is no "
            "other way to request approval, so when the user asks for an action, call the tool "
            "right away (look up any ids you need first) and never ask for permission or "
            "confirmation in the chat.\n" + lines
        )
    if now is not None:
        sections.append(f"Current date and time: {now:%A} {now.isoformat()}")
    if extra_context and extra_context.strip():
        sections.append(extra_context.strip())
    return "\n\n".join(sections) + "\n"
