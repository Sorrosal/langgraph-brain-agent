"""Graph state schema."""

import operator
from typing import Annotated, Any, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """State shared by every node of the agent graph."""

    messages: Annotated[list[AnyMessage], add_messages]
    """Conversation history; node updates are merged by ``add_messages``."""
    summary: NotRequired[str]
    """Rolling summary of older conversation turns."""
    step_count: NotRequired[int]
    """Reasoning steps taken in the current run, used by the step guard."""
    approvals: NotRequired[Annotated[list[dict[str, Any]], operator.add]]
    """Audit trail of human decisions: action id, tool name and decision type."""
    pending_review: NotRequired[dict[str, Any] | None]
    """Verdicts the approval gate persisted for ``await_approval`` (AI message id, verdicts)."""
