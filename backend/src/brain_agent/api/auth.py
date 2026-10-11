"""Registration, login and JWT bearer authentication."""

import asyncio
import contextlib
import time
from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, Field

from brain_agent.api.container import AppContainer
from brain_agent.api.errors import ApiError
from brain_agent.api.ratelimit import client_ip, enforce
from brain_agent.config import Settings
from brain_agent.errors import DuplicateEmailError
from brain_agent.persistence.users import Role, User

ALGORITHM = "HS256"
ISSUER = "brain-agent"
MIN_PASSWORD_LENGTH = 10
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

_hasher = PasswordHash.recommended()
# Verified against when the email is unknown, so both login failures cost the same time.
_DUMMY_HASH = _hasher.hash("not-a-real-password")
_bearer = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    display_name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str
    role: Role
    created_at: datetime

    @classmethod
    def of(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            created_at=user.created_at,
        )


class RegisterAccepted(BaseModel):
    status: Literal["accepted"] = "accepted"


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut


def get_container(request: Request) -> AppContainer:
    container: AppContainer = request.app.state.container
    return container


Container = Annotated[AppContainer, Depends(get_container)]


def issue_token(settings: Settings, user: User) -> tuple[str, int]:
    """Sign a JWT for ``user``; returns it with its lifetime in seconds."""
    assert settings.jwt_secret is not None
    ttl = settings.jwt_ttl_minutes * 60
    now = int(time.time())
    claims = {"sub": user.id, "role": user.role, "iat": now, "exp": now + ttl, "iss": ISSUER}
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=ALGORITHM), ttl


def _unauthorized(message: str = "Not authenticated") -> ApiError:
    return ApiError(401, "unauthorized", message, {"WWW-Authenticate": "Bearer"})


async def _hashed[T](request: Request, work: Callable[[], T]) -> T:
    """Run a password hash/verify off the event loop, at most ``auth_hash_concurrency`` at once."""
    async with request.app.state.hash_gate:
        return await asyncio.to_thread(work)


async def _authenticate(container: AppContainer, token: str | None) -> User:
    """The user a JWT belongs to; the account is re-read, so deleted users lose access at once."""
    if token is None:
        raise _unauthorized()
    assert container.settings.jwt_secret is not None
    try:
        claims = jwt.decode(
            token,
            container.settings.jwt_secret.get_secret_value(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"require": ["sub", "exp", "iat", "iss"]},
        )
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid or expired token") from None
    user = await container.users.get(str(claims["sub"]))
    if user is None:
        raise _unauthorized("Invalid or expired token")
    return user


async def current_user(
    container: Container,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    return await _authenticate(container, credentials.credentials if credentials else None)


async def stream_user(
    container: Container,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    access_token: Annotated[str | None, Query(max_length=2048)] = None,
) -> User:
    """Like :func:`current_user`, plus ``?access_token=`` for ``EventSource`` (no headers).

    Only the event stream route uses this: a token in a URL ends up in logs and history.
    """
    return await _authenticate(container, credentials.credentials if credentials else access_token)


CurrentUser = Annotated[User, Depends(current_user)]
StreamUser = Annotated[User, Depends(stream_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise ApiError(403, "forbidden", "Administrator role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


@router.post("/register", status_code=202, response_model=RegisterAccepted)
async def register(
    body: RegisterRequest, container: Container, request: Request
) -> RegisterAccepted:
    """Always answers 202, whether or not the email already had an account.

    A different answer for a taken email would let anyone probe which emails are registered.
    The password is hashed either way so the response time does not tell them apart; the
    owner of an existing account is not told here (sign in, or reset the password in phase 7).
    """
    if not container.settings.registration_enabled:
        raise ApiError(403, "registration_disabled", "Registration is disabled")
    enforce(
        request,
        "register",
        client_ip(request),
        container.settings.rate_limit_register_per_hour,
        3600,
    )
    password_hash = await _hashed(request, lambda: _hasher.hash(body.password))
    with contextlib.suppress(DuplicateEmailError):
        await container.users.create(body.email.strip().lower(), password_hash, body.display_name)
    return RegisterAccepted()


@router.post("/login", response_model=TokenOut)
async def login(body: LoginRequest, container: Container, request: Request) -> TokenOut:
    email = body.email.strip().lower()
    enforce(
        request,
        "login",
        f"{client_ip(request)}|{email}",
        container.settings.rate_limit_login_per_minute,
        60,
    )
    user = await container.users.get_by_email(email)
    hashed = user.password_hash if user else _DUMMY_HASH
    valid = await _hashed(request, lambda: _hasher.verify(body.password, hashed))
    if user is None or not valid:
        raise _unauthorized("Invalid email or password")
    token, expires_in = issue_token(container.settings, user)
    return TokenOut(access_token=token, expires_in=expires_in, user=UserOut.of(user))


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.of(user)
