"""Approval policy backed by the declarative hard rules."""

from langchain_core.messages import ToolCall
from langchain_core.tools import BaseTool

from brain_agent.brain.rules import RuleMatch, RulesEngine
from brain_agent.hitl.policy import RISK_ORDER, PolicyVerdict


class RulesApprovalPolicy:
    """Blocks or requires approval for calls matching a hard rule; ``block`` beats approval."""

    def __init__(self, engine: RulesEngine) -> None:
        self._engine = engine

    def evaluate(self, tool_call: ToolCall, tool: BaseTool | None) -> PolicyVerdict | None:
        matches = self._engine.evaluate(tool_call["name"], tool_call["args"])
        blocking = [m for m in matches if m.action == "block"]
        deciding = blocking or matches
        if not deciding:
            return None
        return PolicyVerdict(
            risk=max((m.risk for m in deciding), key=RISK_ORDER.index),
            reason=_reason(deciding),
            blocked=bool(blocking),
            rule_ids=tuple(m.rule_id for m in deciding),
        )


def _reason(matches: list[RuleMatch]) -> str:
    return " ".join(dict.fromkeys(m.reason for m in matches))
