"""Deterministic test doubles for the agent graph."""

from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr, SkipValidation


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
