"""Helpers shared by the business tools."""

import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool, ToolException
from pydantic import BaseModel, ValidationError

from brain_agent.errors import NotFoundError
from brain_agent.hitl.models import Risk
from brain_agent.tools.idempotency import current_idempotency_key


def to_json(value: BaseModel | list[BaseModel] | dict[str, Any]) -> str:
    """Compact JSON with stable (sorted) keys, the form every business tool returns."""
    if isinstance(value, BaseModel):
        data: Any = value.model_dump(mode="json")
    elif isinstance(value, list):
        data = [item.model_dump(mode="json") for item in value]
    else:
        data = value
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def idempotency_key_or_new() -> str:
    """The ledger's key for the running call; a fresh uuid for direct calls outside the graph."""
    return current_idempotency_key() or uuid.uuid4().hex


def not_found(error: NotFoundError) -> ToolException:
    """Tool error the model can act on (e.g. by searching for the right id)."""
    return ToolException(f"{error}. Look the record up with a search or list tool and retry.")


def describe_validation_error(error: ValidationError | Any) -> str:
    """Which arguments were wrong and why, so the model can fix the call."""
    if not isinstance(error, ValidationError):
        return f"Invalid arguments: {error}"
    problems = "; ".join(
        f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in error.errors()
    )
    return f"Invalid arguments: {problems}"


def make_tool(
    name: str,
    description: str,
    args_schema: type[BaseModel],
    coroutine: Callable[..., Awaitable[str]],
    risk: Risk,
    **metadata: Any,
) -> BaseTool:
    async def guarded(**kwargs: Any) -> str:
        try:
            return await coroutine(**kwargs)
        except NotFoundError as exc:
            raise not_found(exc) from exc

    return StructuredTool.from_function(
        coroutine=guarded,
        name=name,
        description=description,
        args_schema=args_schema,
        handle_tool_error=True,
        handle_validation_error=describe_validation_error,
        metadata={"risk": risk, "retry_safe": True, **metadata},
    )
