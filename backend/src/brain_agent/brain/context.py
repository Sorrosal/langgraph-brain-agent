"""Conversation compaction: summarise old messages so the history stays within a token budget."""

from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.utils import count_tokens_approximately

SUMMARY_INSTRUCTIONS = (
    "You maintain the running summary of a conversation between a user and an assistant. "
    "Merge the existing summary with the new messages into one concise summary. Keep decisions, "
    "names, ids, amounts, open tasks and tool outcomes; drop pleasantries. Reply with the "
    "summary only."
)


@dataclass(frozen=True, slots=True)
class ContextBudget:
    """Token budget of the message history and how many recent messages always stay verbatim."""

    max_tokens: int
    keep_last_messages: int


def over_budget(messages: Sequence[AnyMessage], budget: ContextBudget) -> bool:
    """Whether the history exceeds the budget (approximate token count)."""
    return count_tokens_approximately(messages) > budget.max_tokens


def _cut_index(messages: Sequence[AnyMessage], keep_last: int) -> int:
    """Index of the first kept message; never a ``ToolMessage``, so a tool call stays with
    its results (the cut moves back to the AI message that requested them)."""
    cut = len(messages) - max(keep_last, 0)
    while 0 < cut < len(messages) and isinstance(messages[cut], ToolMessage):
        cut -= 1
    return cut


def _render(messages: Sequence[AnyMessage]) -> str:
    lines = []
    for message in messages:
        if isinstance(message, AIMessage) and message.tool_calls:
            calls = ", ".join(f"{c['name']}({c['args']})" for c in message.tool_calls)
            lines.append(f"assistant: {message.text} [tool calls: {calls}]".strip())
        elif isinstance(message, ToolMessage) and message.text.lstrip().startswith("<untrusted"):
            # Outside content (an email) never reaches the summary verbatim.
            lines.append("tool: [outside content omitted]")
        else:
            lines.append(f"{message.type}: {message.text}")
    return "\n".join(lines)


async def compact_messages(
    messages: Sequence[AnyMessage], summary: str, model: BaseChatModel, budget: ContextBudget
) -> tuple[str, list[RemoveMessage]] | None:
    """Summarise the oldest messages when the history is over budget.

    Returns the merged summary and a ``RemoveMessage`` per summarised message, or ``None`` when
    the history fits, or nothing is old enough to be summarised (the last
    ``keep_last_messages`` always stay).
    """
    if not over_budget(messages, budget):
        return None
    cut = _cut_index(messages, budget.keep_last_messages)
    old = [m for m in messages[:cut] if m.id is not None]
    if not old:
        return None
    existing = f"Existing summary:\n{summary}\n\n" if summary else ""
    response = await model.ainvoke(
        [
            SystemMessage(content=SUMMARY_INSTRUCTIONS),
            HumanMessage(content=f"{existing}New messages:\n{_render(old)}"),
        ]
    )
    new_summary = response.text.strip()
    if not new_summary:
        return None
    return new_summary, [RemoveMessage(id=str(m.id)) for m in old]
