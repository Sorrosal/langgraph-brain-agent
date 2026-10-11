"""Registration, login and JWT bearer authentication."""

import asyncio
import time
from datetime import datetime
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from pydantic import BaseModel, Field

from brain_agent.api.container import AppContainer
from brain_agent.api.errors import ApiError
from brain_agent.config import Settings
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


async def current_user(
    container: Container,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """The authenticated user; the account is re-read, so deleted users lose access at once."""
    if credentials is None:
        raise _unauthorized()
    assert container.settings.jwt_secret is not None
    try:
        claims = jwt.decode(
            credentials.credentials,
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


CurrentUser = Annotated[User, Depends(current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise ApiError(403, "forbidden", "Administrator role required")
    return user


@router.post("/register", status_code=201, response_model=UserOut)
async def register(body: RegisterRequest, container: Container) -> UserOut:
    if not container.settings.registration_enabled:
        raise ApiError(403, "registration_disabled", "Registration is disabled")
    password_hash = await asyncio.to_thread(_hasher.hash, body.password)
    user = await container.users.create(
        body.email.strip().lower(), password_hash, body.display_name
    )
    return UserOut.of(user)


@router.post("/login", response_model=TokenOut)
async def login(body: LoginRequest, container: Container) -> TokenOut:
    user = await container.users.get_by_email(body.email.strip())
    valid = await asyncio.to_thread(
        _hasher.verify, body.password, user.password_hash if user else _DUMMY_HASH
    )
    if user is None or not valid:
        raise _unauthorized("Invalid email or password")
    token, expires_in = issue_token(container.settings, user)
    return TokenOut(access_token=token, expires_in=expires_in, user=UserOut.of(user))


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.of(user)
