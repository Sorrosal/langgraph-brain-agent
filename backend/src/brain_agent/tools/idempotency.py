"""Exactly-once tool side effects on top of an at-least-once graph.

After a crash the ``tools`` node re-runs from the last checkpoint, so a tool that already did
its side effect (sent an email) could do it again. Every call is therefore recorded in a
:class:`ToolLedger` under the key ``thread_id:tool_call_id``:

* no record -> record ``started``, run the tool, record the result;
* ``succeeded`` -> return the stored result without running the tool (``tool_replayed``);
* ``failed`` -> run again: a failure is not a committed side effect, so it is retryable;
* a not ``retry_safe`` tool failing with ``outcome_unknown`` (e.g. a timeout after SMTP DATA)
  stays ``started`` instead of ``failed``, so it is escalated like the case below;
* ``started`` -> the previous process died mid-execution and the outcome is *unknown*. If the
  tool declares ``metadata["retry_safe"] = True`` (the provider deduplicates on the key from
  :func:`current_idempotency_key`) it runs again with the same key. Otherwise a human decides
  (:class:`UncertainExecutionInterrupt`, raised by the ``resolve_uncertain`` node, never by the
  tools node): ``confirm_done``, ``retry`` (recorded as ``retry_authorized``) or ``skip``.

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
from langgraph.types import Command, Send, interrupt

from brain_agent.errors import (
    MAX_ERROR_CHARS,
    ConfigurationError,
    UncertainExecutionError,
    safe_error,
)
from brain_agent.graph.nodes import TOOLS_NODE
from brain_agent.hitl.models import (
    ConfirmDone,
    Retry,
    UncertainAction,
    UncertainExecutionInterrupt,
    UncertainResponse,
)
from brain_agent.observability.tracing import ToolObservation, observe_tool
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
        with observe_tool(request.tool_call["name"], _retry_safe(request.tool)) as observed:
            return await recorded(request, execute, observed)

    async def recorded(
        request: ToolCallRequest, execute: Execute, observed: ToolObservation
    ) -> ToolResult:
        call = request.tool_call
        thread_id = _thread_id(request.runtime.config)
        key = idempotency_key(thread_id, str(call["id"]))
        digest = args_hash(call["args"])
        record = await ledger.begin(key, thread_id, call["name"], digest)
        if not record.is_new:
            if reason := uncertain_reason(record, request.tool, digest):
                logger.error("tool_execution_uncertain", key=key, reason=reason)
                observed.outcome = "escalated"
                raise UncertainExecutionError(call["name"], str(call["id"]), reason)
            if record.status == "succeeded":
                logger.info("tool_replayed", key=key, tool=call["name"])
                observed.outcome = "replayed"
                return _replay(record, call)
            if record.status == "failed" and record.error == SKIPPED_ERROR:
                return _skipped(call)
            # failed (retryable) or started + retry_safe: run again under the same key.
            await ledger.restart(key, digest)

        token = _current_key.set(key)
        try:
            output = await execute(request)
        except GraphBubbleUp:
            observed.outcome = "interrupted"
            await ledger.fail(key, "interrupted before completion")
            raise
        except Exception as exc:
            if getattr(exc, "outcome_unknown", False) and not _retry_safe(request.tool):
                # Leave the record 'started': the effect may have happened, a human decides.
                reason = f"The attempt failed with an unknown outcome ({type(exc).__name__})."
                logger.error("tool_execution_uncertain", key=key, reason=reason)
                observed.outcome = "escalated"
                raise UncertainExecutionError(call["name"], str(call["id"]), reason) from exc
            observed.outcome = "failed"
            await ledger.fail(key, safe_error(exc))
            raise
        finally:
            _current_key.reset(token)
        if isinstance(output, ToolMessage) and output.status == "error":
            observed.outcome = "failed"
            await ledger.fail(key, output.text[:MAX_ERROR_CHARS])
        elif isinstance(output, ToolMessage):
            await ledger.complete(key, {"content": output.content, "status": "success"})
        else:
            await ledger.complete(key, {"content": str(output), "status": "success"})
        return output

    return wrapper


async def _uncertain_calls(
    calls: Sequence[ToolCall],
    tools_by_name: dict[str, BaseTool],
    ledger: ToolLedger,
    thread_id: str,
) -> list[tuple[ToolCall, str, str]]:
    """Calls whose earlier outcome is unknown, with their ledger key and the reason."""
    found = []
    for call in calls:
        record = await ledger.get(idempotency_key(thread_id, str(call["id"])))
        digest = args_hash(call["args"])
        reason = (
            uncertain_reason(record, tools_by_name.get(call["name"]), digest) if record else None
        )
        if record and reason:
            found.append((call, record.idempotency_key, reason))
    return found


def make_resolve_uncertain_node(tools: Sequence[BaseTool], ledger: ToolLedger) -> ToolsNode:
    """Node that asks a human about calls whose earlier outcome is unknown, before ``tools``.

    It has its own task, hence its own resume values, isolated from any ``interrupt()`` a tool
    raises. It interrupts at most once, with every uncertain call; the answer is keyed by
    action id. Decisions are applied idempotently, so re-running the node after a partial
    application only handles the calls still uncertain.
    """
    tools_by_name = {tool.name: tool for tool in tools}

    async def resolve_uncertain(state: Any, config: RunnableConfig) -> Any:
        thread_id = _thread_id(config)
        uncertain = await _uncertain_calls(state, tools_by_name, ledger, thread_id)
        if uncertain:
            actions = [
                UncertainAction(
                    action_id=str(call["id"]),
                    tool_name=call["name"],
                    args=call["args"],
                    message=reason,
                )
                for call, _key, reason in uncertain
            ]
            raw = interrupt(UncertainExecutionInterrupt(actions=actions).model_dump())
            response = UncertainResponse.model_validate(raw)
            response.ensure_covers([a.action_id for a in actions], [str(c["id"]) for c in state])
            for call, key, _reason in uncertain:
                await _apply_decision(ledger, key, args_hash(call["args"]), response, call)
        return Command(goto=Send(TOOLS_NODE, state))

    return resolve_uncertain


async def _apply_decision(
    ledger: ToolLedger, key: str, digest: str, response: UncertainResponse, call: ToolCall
) -> None:
    decision = response.decisions[str(call["id"])]
    if isinstance(decision, Retry):
        await ledger.authorize_retry(key, digest)
        return
    await ledger.restart(key, digest)
    if isinstance(decision, ConfirmDone):
        content = decision.message or CONFIRMED_RESULT
        await ledger.complete(key, {"content": content, "status": "success"})
    else:
        await ledger.fail(key, SKIPPED_ERROR)


def make_tools_node(tools: Sequence[BaseTool], ledger: ToolLedger) -> ToolsNode:
    """Tool node with exactly-once execution; its input is the list of calls sent to it.

    It never asks a human itself (``interrupt()`` positions would drift once the ledger
    changes). If an unresolved uncertain call reaches it, e.g. after a crash mid-execution, it
    does nothing and the graph routes back to ``resolve_uncertain``; the execution wrapper is
    the final backstop.
    """
    tools_by_name = {tool.name: tool for tool in tools}
    tool_node = ToolNode(tools, awrap_tool_call=make_execution_wrapper(ledger))

    async def tools_node(state: Any, config: RunnableConfig) -> Any:
        if await _uncertain_calls(state, tools_by_name, ledger, _thread_id(config)):
            return {}  # nothing ran; the router sends the batch back
        try:
            return await tool_node.ainvoke(state, config)
        except UncertainExecutionError:  # the record stays 'started'; the router asks a human
            return {}

    return tools_node
