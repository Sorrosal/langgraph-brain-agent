"""Payloads exchanged with the human reviewer.

The interrupt payload is persisted in the checkpoint and the node that raises it re-runs on
resume, so it must be a pure function of the graph state: no timestamps, no randomness.
"""

from collections.abc import Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from brain_agent.errors import InvalidApprovalError

Risk = Literal["low", "medium", "high"]


class ActionRequest(BaseModel):
    """A tool call waiting for a human decision."""

    action_id: str
    """The tool call id; decisions are keyed by it."""
    tool_name: str
    args: dict[str, Any]
    risk: Risk
    reason: str
    """Why this call needs approval."""


class ApprovalInterrupt(BaseModel):
    """Interrupt payload: the actions in the current tool-call batch that need approval."""

    kind: Literal["approval_required"] = "approval_required"
    actions: list[ActionRequest]


class Approve(BaseModel):
    type: Literal["approve"] = "approve"


class Edit(BaseModel):
    type: Literal["edit"] = "edit"
    args: dict[str, Any]
    """Replacement arguments for the tool call."""


class Reject(BaseModel):
    type: Literal["reject"] = "reject"
    reason: str | None = None


class Respond(BaseModel):
    type: Literal["respond"] = "respond"
    message: str
    """Answer returned to the model in place of running the tool."""


Decision = Annotated[Approve | Edit | Reject | Respond, Field(discriminator="type")]


class ApprovalResponse(BaseModel):
    """Human decisions keyed by action id."""

    decisions: dict[str, Decision]

    def ensure_covers(self, actions: Sequence[ActionRequest]) -> None:
        """Require exactly one decision per pending action.

        Raises:
            InvalidApprovalError: a pending action has no decision, or an id is unknown.
        """
        pending = {action.action_id for action in actions}
        missing = sorted(pending - self.decisions.keys())
        unknown = sorted(self.decisions.keys() - pending)
        if missing:
            raise InvalidApprovalError(f"Decision missing for actions: {', '.join(missing)}")
        if unknown:
            raise InvalidApprovalError(f"Decision for unknown actions: {', '.join(unknown)}")
