"""Deterministic test doubles for the agent graph."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr, SkipValidation

from brain_agent.errors import ThreadBusyError


class ScriptedChatModel(BaseChatModel):
    """Chat model that replays a scripted list of responses, one per call.

    Each script entry is either an :class:`AIMessage` (returned) or an exception (raised),
    which makes tool calls, transient failures and step limits fully deterministic.
    ``bind_tools`` returns a binding over the same instance, so call accounting is shared.
    """

    # Unvalidated: pydantic would run AIMessage validators against scripted exceptions.
    script: SkipValidation[list[AIMessage | Exception]]

    _calls: int = PrivateAttr(default=0)
    _inputs: list[list[BaseMessage]] = PrivateAttr(default_factory=list)
    _bound_tool_names: list[str] = PrivateAttr(default_factory=list)

    @property
    def calls(self) -> int:
        """Number of times the model has been invoked (including failed attempts)."""
        return self._calls

    @property
    def inputs(self) -> list[list[BaseMessage]]:
        """Messages received on every invocation, in call order."""
        return self._inputs

    @property
    def bound_tool_names(self) -> list[str]:
        """Names of the tools passed to the last ``bind_tools`` call."""
        return self._bound_tool_names

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        self._bound_tool_names = [tool.name for tool in tools if isinstance(tool, BaseTool)]
        return self.bind(tools=[tool.name for tool in tools if isinstance(tool, BaseTool)])

    def _next(self, messages: list[BaseMessage]) -> ChatResult:
        self._inputs.append(list(messages))
        index = self._calls
        self._calls += 1
        if index >= len(self.script):
            raise AssertionError(f"ScriptedChatModel exhausted after {len(self.script)} calls")
        step = self.script[index]
        if isinstance(step, Exception):
            raise step
        return ChatResult(generations=[ChatGeneration(message=step)])

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._next(messages)

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._next(messages)


def tool_call(name: str, args: dict[str, Any], call_id: str) -> AIMessage:
    """Build an AI message requesting a single tool call."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


@dataclass(slots=True)
class FakeRunRecord:
    """Row of the in-memory run ledger."""

    thread_id: str
    status: str
    owner: str | None = None
    attempts: int = 0
    last_error: str | None = None
    expired: bool = False
    fencing_token: int = 0


class FakeRunLedger:
    """In-memory :class:`brain_agent.persistence.runs.RunLedger` for tests without Postgres.

    Mirrors :class:`~brain_agent.persistence.runs.RunRegistry` (fencing tokens, busy leases).
    Leases are not timed: a test marks a run as orphaned with :meth:`expire`.
    """

    def __init__(self) -> None:
        self.records: dict[str, FakeRunRecord] = {}
        self.heartbeats = 0
        self.events: list[str] = []

    def expire(self, thread_id: str) -> None:
        self.records[thread_id].expired = True

    def _holds(self, thread_id: str, owner: str, token: int) -> FakeRunRecord | None:
        record = self.records.get(thread_id)
        held = record is not None and record.owner == owner and record.fencing_token == token
        return record if held else None

    async def mark_running(
        self, thread_id: str, owner: str, lease_seconds: float, *, reset_attempts: bool = True
    ) -> int:
        record = self.records.get(thread_id)
        if record is None:
            record = self.records[thread_id] = FakeRunRecord(thread_id, "running", owner)
        elif (
            record.status == "running"
            and record.owner is not None
            and not record.expired
            and record.owner != owner
        ):
            raise ThreadBusyError(thread_id)
        self.events.append(f"running:{thread_id}")
        record.status, record.owner, record.expired = "running", owner, False
        record.fencing_token += 1
        if reset_attempts:
            record.attempts, record.last_error = 0, None
        return record.fencing_token

    async def heartbeat(self, thread_id: str, owner: str, token: int, lease_seconds: float) -> bool:
        record = self._holds(thread_id, owner, token)
        if record is None or record.status != "running":
            return False
        self.heartbeats += 1
        return True

    async def mark_finished(
        self, thread_id: str, owner: str, token: int, status: str, error: str | None = None
    ) -> bool:
        record = self._holds(thread_id, owner, token)
        if record is None:
            return False
        self.events.append(f"{status}:{thread_id}")
        record.status, record.owner, record.expired = status, None, False
        record.last_error = error if error is not None else record.last_error
        return True

    async def record_error(self, thread_id: str, owner: str, token: int, error: str) -> bool:
        record = self._holds(thread_id, owner, token)
        if record is None:
            return False
        record.last_error = error
        return True

    async def claim_orphans(
        self, owner: str, lease_seconds: float, limit: int, *, max_attempts: int = 3
    ) -> list[str]:
        claimed: list[str] = []
        for record in list(self.records.values()):
            if len(claimed) >= limit:
                break
            if record.status != "running" or not record.expired:
                continue
            if record.attempts >= max_attempts:
                record.status, record.owner, record.expired = "failed", None, False
                continue
            record.attempts += 1
            record.fencing_token += 1
            record.owner, record.expired = owner, False
            claimed.append(record.thread_id)
        return claimed

    async def get(self, thread_id: str) -> FakeRunRecord | None:
        return self.records.get(thread_id)
