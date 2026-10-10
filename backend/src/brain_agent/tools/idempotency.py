"""Exactly-once tool side effects on top of an at-least-once graph.

After a crash the ``tools`` node re-runs from the last checkpoint, so a tool that already did
its side effect (sent an email) could do it again. Every call is therefore recorded in a
:class:`ToolLedger` under the key ``thread_id:tool_call_id``:

* no record -> record ``started``, run the tool, record the result;
* ``succeeded`` -> return the stored result without running the tool (``tool_replayed``);
* ``failed`` -> run again: a failure is not a committed side effect, so it is retryable;
* ``started`` -> the previous process died mid-execution and the outcome is *unknown*. If the
  tool declares ``metadata["retry_safe"] = True`` (the provider deduplicates on the key from
  :func:`current_idempotency_key`) it runs again with the same key. Otherwise a human decides
  (:class:`UncertainExecutionInterrupt`): ``confirm_done``, ``retry`` or ``skip``.

The same applies when a stored record's args hash differs from the call's: the key is per
tool call id, so that indicates a bug and is escalated instead of trusted.

Only :class:`ToolMessage` results are stored and replayed (``artifact`` is not kept).
"""

import hashlib
import json
from collections.abc import Awaitable, Callable, Sequence
from contextvars import ContextVar
from typing import Any, Protocol

import structlog
from langchain_core.messages import ToolCall, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.errors import GraphBubbleUp
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command, interrupt

from brain_agent.errors import ConfigurationError, UncertainExecutionError
from brain_agent.hitl.models import (
    UNCERTAIN_DECISION,
    ConfirmDone,
    Retry,
    UncertainExecutionInterrupt,
)
from brain_agent.persistence.tool_ledger import ExecutionRecord, ToolLedger

logger = structlog.get_logger(__name__)

CONFIRMED_RESULT = "Confirmed done by human"
SKIPPED_ERROR = "Skipped by human"

_current_key: ContextVar[str | None] = ContextVar("idempotency_key", default=None)

ToolResult = ToolMessage | Command[Any]
Execute = Callable[[ToolCallRequest], Awaitable[ToolResult]]


class ToolsNode(Protocol):
    """Async node signature LangGraph recognises as accepting the run config."""

    def __call__(self, state: Any, config: RunnableConfig) -> Awaitable[Any]: ...


def current_idempotency_key() -> str | None:
    """Idempotency key of the tool call being executed, for adapters to send to providers."""
    return _current_key.get()


def idempotency_key(thread_id: str, call_id: str) -> str:
    return f"{thread_id}:{call_id}"


def args_hash(args: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON form of ``args``."""
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _thread_id(config: RunnableConfig) -> str:
    thread_id = (config.get("configurable") or {}).get("thread_id")
    if not thread_id:
        raise ConfigurationError("Exactly-once tool execution requires a thread_id in the config")
    return str(thread_id)


def _retry_safe(tool: BaseTool | None) -> bool:
    return bool(tool and tool.metadata and tool.metadata.get("retry_safe") is True)


def uncertain_reason(record: ExecutionRecord, tool: BaseTool | None, digest: str) -> str | None:
    """Why a previous execution of this call cannot be trusted, or ``None`` if it can."""
    if record.args_hash != digest:
        return "The recorded arguments differ from the call's; the earlier execution is suspect."
    if record.status == "started" and not _retry_safe(tool):
        return "A previous attempt started but never recorded an outcome; it may have run."
    return None


def _replay(record: ExecutionRecord, call: ToolCall) -> ToolMessage:
    stored = record.result or {}
    return ToolMessage(
        content=stored.get("content", ""),
        name=call["name"],
        tool_call_id=str(call["id"]),
        status=stored.get("status", "success"),
    )


def _skipped(call: ToolCall) -> ToolMessage:
    return ToolMessage(
        content=SKIPPED_ERROR, name=call["name"], tool_call_id=str(call["id"]), status="error"
    )


def make_execution_wrapper(
    ledger: ToolLedger,
) -> Callable[[ToolCallRequest, Execute], Awaitable[ToolResult]]:
    """``awrap_tool_call`` hook that records each call in ``ledger`` and replays stored results."""

    async def wrapper(request: ToolCallRequest, execute: Execute) -> ToolResult:
        call = request.tool_call
        thread_id = _thread_id(request.runtime.config)
        key = idempotency_key(thread_id, str(call["id"]))
        digest = args_hash(call["args"])
        record = await ledger.begin(key, thread_id, call["name"], digest)
        if not record.is_new:
            if reason := uncertain_reason(record, request.tool, digest):
                logger.error("tool_execution_uncertain", key=key, reason=reason)
                raise UncertainExecutionError(call["name"], str(call["id"]), reason)
            if record.status == "succeeded":
                logger.info("tool_replayed", key=key, tool=call["name"])
                return _replay(record, call)
            if record.status == "failed" and record.error == SKIPPED_ERROR:
                return _skipped(call)
            # failed (retryable) or started + retry_safe: run again under the same key.
            await ledger.restart(key, digest)

        token = _current_key.set(key)
        try:
            output = await execute(request)
        except GraphBubbleUp:
            await ledger.fail(key, "interrupted before completion")
            raise
        except Exception as exc:
            await ledger.fail(key, f"{type(exc).__name__}: {exc}")
            raise
        finally:
            _current_key.reset(token)
        if isinstance(output, ToolMessage) and output.status == "error":
            await ledger.fail(key, output.text)
        elif isinstance(output, ToolMessage):
            await ledger.complete(key, {"content": output.content, "status": "success"})
        else:
            await ledger.complete(key, {"content": str(output), "status": "success"})
        return output

    return wrapper


def make_tools_node(tools: Sequence[BaseTool], ledger: ToolLedger) -> ToolsNode:
    """Tool node with exactly-once execution; its input is the list of calls sent to it.

    Before running anything it asks a human about every call whose earlier outcome is unknown
    (one interrupt each, in call order). Nothing in the ledger changes until every question is
    answered, so re-running the node on resume asks the same questions in the same order.
    """
    tools_by_name = {tool.name: tool for tool in tools}
    tool_node = ToolNode(tools, awrap_tool_call=make_execution_wrapper(ledger))

    async def tools_node(state: Any, config: RunnableConfig) -> Any:
        thread_id = _thread_id(config)
        decided: list[tuple[str, str, str, Any]] = []
        for call in state:
            key = idempotency_key(thread_id, str(call["id"]))
            digest = args_hash(call["args"])
            record = await ledger.get(key)
            if record is None:
                continue
            reason = uncertain_reason(record, tools_by_name.get(call["name"]), digest)
            if reason is None:
                continue
            payload = UncertainExecutionInterrupt(
                action_id=str(call["id"]), tool_name=call["name"], args=call["args"], message=reason
            )
            decision = UNCERTAIN_DECISION.validate_python(interrupt(payload.model_dump()))
            decided.append((key, call["name"], digest, decision))
        for key, _name, digest, decision in decided:
            await ledger.restart(key, digest)
            if isinstance(decision, ConfirmDone):
                content = decision.message or CONFIRMED_RESULT
                await ledger.complete(key, {"content": content, "status": "success"})
            elif isinstance(decision, Retry):
                await ledger.fail(key, "Retry requested by human")
            else:
                await ledger.fail(key, SKIPPED_ERROR)
        return await tool_node.ainvoke(state, config)

    return tools_node
