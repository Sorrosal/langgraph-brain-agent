"""One JSON error body for every failure: ``{"error": {"code", "message"}}``."""

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from brain_agent.api.request_id import HEADER, request_id_of
from brain_agent.errors import (
    BrainAgentError,
    DuplicateEmailError,
    InvalidApprovalError,
    LeaseLostError,
    NoPendingApprovalError,
    NotFoundError,
    ThreadBusyError,
)

logger = structlog.get_logger(__name__)

# Most specific first; the first isinstance match wins.
DOMAIN_ERRORS: tuple[tuple[type[BrainAgentError], int, str], ...] = (
    (ThreadBusyError, 409, "thread_busy"),
    (NoPendingApprovalError, 409, "no_pending_approval"),
    (DuplicateEmailError, 409, "email_taken"),
    (InvalidApprovalError, 422, "invalid_approval"),
    (NotFoundError, 404, "not_found"),
    (LeaseLostError, 503, "lease_lost"),
)


class ApiError(HTTPException):
    """An HTTP failure with a stable machine-readable ``code``."""

    def __init__(
        self, status_code: int, code: str, message: str, headers: dict[str, str] | None = None
    ) -> None:
        super().__init__(status_code, detail=message, headers=headers)
        self.code = code


def error_response(
    status_code: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    body = {"error": {"code": code, "message": message}}
    return JSONResponse(body, status_code=status_code, headers=headers)


def _internal_error(request: Request, exc: Exception) -> JSONResponse:
    """Log the failure with its request id; the client gets the id, never the exception."""
    request_id = request_id_of(request.scope)
    logger.error(
        "unhandled_exception",
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        exc_info=exc,
    )
    body = {
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
            "request_id": request_id,
        }
    }
    return JSONResponse(body, status_code=500, headers={HEADER: request_id or ""})


def install_error_handlers(app: FastAPI) -> None:
    async def domain(request: Request, exc: Exception) -> JSONResponse:
        for kind, status, code in DOMAIN_ERRORS:
            if isinstance(exc, kind):
                return error_response(status, code, str(exc))
        return _internal_error(request, exc)

    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        return _internal_error(request, exc)

    async def http(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, StarletteHTTPException)
        code = exc.code if isinstance(exc, ApiError) else f"http_{exc.status_code}"
        return error_response(exc.status_code, code, str(exc.detail), dict(exc.headers or {}))

    async def validation(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, RequestValidationError)
        first = exc.errors()[0]  # never echo the input: it may hold a password
        where = ".".join(str(part) for part in first["loc"])
        return error_response(422, "validation_error", f"{where}: {first['msg']}")

    app.add_exception_handler(Exception, unhandled)
    app.add_exception_handler(BrainAgentError, domain)
    app.add_exception_handler(StarletteHTTPException, http)
    app.add_exception_handler(RequestValidationError, validation)
