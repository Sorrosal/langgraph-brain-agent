"""Decides which tool calls need a human decision before they run."""

from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import ToolCall
from langchain_core.tools import BaseTool

from brain_agent.hitl.models import Risk

DEFAULT_REASON = "This tool requires human approval."


@dataclass(frozen=True, slots=True)
class PolicyVerdict:
    """A policy's decision that a call needs approval, or must not run at all."""

    risk: Risk
    reason: str
    blocked: bool = False
    """The call is refused outright: never executed and never offered for approval."""
    rule_ids: tuple[str, ...] = ()
    """Ids of the rules behind the verdict, for audit."""


RISK_ORDER: tuple[Risk, ...] = ("low", "medium", "high")


def _severity(verdict: PolicyVerdict) -> tuple[bool, int]:
    return verdict.blocked, RISK_ORDER.index(verdict.risk)


def strictest(*verdicts: PolicyVerdict | None) -> PolicyVerdict | None:
    """The most severe verdict (block > approval by risk); the earliest wins ties."""
    found: PolicyVerdict | None = None
    for verdict in verdicts:
        if verdict is not None and (found is None or _severity(verdict) > _severity(found)):
            found = verdict
    return found


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
    """Asks every policy and returns the strictest verdict (block > approval > none).

    Approvals are ranked by risk; among equally strict verdicts the earliest policy wins.
    """

    def __init__(self, *policies: ApprovalPolicy) -> None:
        self._policies = policies

    def evaluate(self, tool_call: ToolCall, tool: BaseTool | None) -> PolicyVerdict | None:
        return strictest(*(policy.evaluate(tool_call, tool) for policy in self._policies))
