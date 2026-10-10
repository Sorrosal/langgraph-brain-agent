"""Decides which tool calls need a human decision before they run."""

from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import ToolCall
from langchain_core.tools import BaseTool

from brain_agent.hitl.models import Risk

DEFAULT_REASON = "This tool requires human approval."


@dataclass(frozen=True, slots=True)
class PolicyVerdict:
    """A policy's decision that a call needs approval."""

    risk: Risk
    reason: str


class ApprovalPolicy(Protocol):
    """Evaluates one tool call; ``None`` means it can run without approval.

    ``tool`` is ``None`` when the model asked for a tool that is not registered.
    """

    def evaluate(self, tool_call: ToolCall, tool: BaseTool | None) -> PolicyVerdict | None: ...


class MetadataApprovalPolicy:
    """Requires approval for tools flagged in their metadata.

    A tool needs approval when ``metadata["requires_approval"]`` is true or
    ``metadata["risk"] == "high"``; ``metadata["approval_reason"]`` explains why.
    """

    def evaluate(self, tool_call: ToolCall, tool: BaseTool | None) -> PolicyVerdict | None:
        metadata = (tool.metadata if tool is not None else None) or {}
        high = metadata.get("risk") == "high"
        if not (high or metadata.get("requires_approval") is True):
            return None
        return PolicyVerdict(
            risk="high" if high else "medium",
            reason=str(metadata.get("approval_reason", DEFAULT_REASON)),
        )


class CompositeApprovalPolicy:
    """Asks several policies in order; the first verdict wins."""

    def __init__(self, *policies: ApprovalPolicy) -> None:
        self._policies = policies

    def evaluate(self, tool_call: ToolCall, tool: BaseTool | None) -> PolicyVerdict | None:
        for policy in self._policies:
            verdict = policy.evaluate(tool_call, tool)
            if verdict is not None:
                return verdict
        return None
