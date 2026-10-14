"""structlog setup: JSON lines in production, a console renderer in development.

Standard-library logging (uvicorn, libraries) is routed through the same pipeline, and the
context bound by the request-id middleware (``request_id``, and ``thread_id``/``owner`` where
the runner binds them) is merged into every record.
"""

import logging
import re
import sys
from typing import TextIO

import structlog
from structlog.typing import Processor

from brain_agent.config import Settings

_HANDLER_MARK = "_brain_agent_handler"
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")
_TOKEN_IN_QUERY = re.compile(r"(access_token=)[^&\s\"']+")


class RedactTokens(logging.Filter):
    """Mask ``access_token`` query values (SSE streams carry the token in the URL), so access
    logs never store a usable bearer token."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(
                _TOKEN_IN_QUERY.sub(r"\1[redacted]", a) if isinstance(a, str) else a
                for a in record.args
            )
        if isinstance(record.msg, str):
            record.msg = _TOKEN_IN_QUERY.sub(r"\1[redacted]", record.msg)
        return True


def configure_logging(settings: Settings, stream: TextIO | None = None) -> None:
    """(Re)configure structlog and the root logger; safe to call more than once."""
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    json_logs = settings.effective_log_format == "json"
    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )
    handler = logging.StreamHandler(stream or sys.stderr)
    setattr(handler, _HANDLER_MARK, True)
    handler.addFilter(RedactTokens())
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                *([structlog.processors.format_exc_info] if json_logs else []),
                renderer,
            ],
        )
    )
    root = logging.getLogger()
    for existing in [h for h in root.handlers if getattr(h, _HANDLER_MARK, False)]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(settings.log_level)
    for name in _UVICORN_LOGGERS:  # let uvicorn's records flow through the root handler
        logging.getLogger(name).handlers.clear()
        logging.getLogger(name).propagate = True
