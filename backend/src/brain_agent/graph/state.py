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
    context: NotRequired[str]
    """Recalled memories for the current turn, set by ``load_context``."""
    step_count: NotRequired[int]
    """Reasoning steps taken in the current run, used by the step guard."""
    approvals: NotRequired[Annotated[list[dict[str, Any]], operator.add]]
    """Audit trail of human decisions: action id, tool name and decision type."""
    pending_review: NotRequired[dict[str, Any] | None]
    """Verdicts the approval gate persisted for ``await_approval`` (AI message id, verdicts)."""
    session: NotRequired[dict[str, str]]
    """Who is talking and from where (user_name, role, language, timezone), set per message."""
    summary_tainted: NotRequired[bool]
    """The summary folded in outside content (an email): writes keep needing approval."""
    context_report: NotRequired[dict[str, Any]]
    """What the last model call was given: sections, approximate tokens, cleared results."""
