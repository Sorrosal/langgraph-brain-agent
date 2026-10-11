"""Auth endpoints: registration, login, tokens and JWT secret validation."""

import time

import jwt
import pytest

from brain_agent.errors import ConfigurationError
from tests.api_support import PASSWORD, make_settings, register, running_api


async def test_register_login_me_and_first_user_is_admin() -> None:
    async with running_api([]) as h:
        first = await h.client.post(
            "/auth/register",
            json={"email": "Ana@Acme.com", "password": PASSWORD, "display_name": "Ana"},
        )
        second = await h.client.post(
            "/auth/register",
            json={"email": "bob@acme.com", "password": PASSWORD, "display_name": "Bob"},
        )
        assert (first.status_code, second.status_code) == (202, 202)
        assert "password" not in first.text

        login = await h.client.post(
            "/auth/login", json={"email": "ana@acme.com", "password": PASSWORD}
        )
        body = login.json()
        assert (login.status_code, body["token_type"], body["expires_in"]) == (200, "bearer", 3600)
        claims = jwt.decode(
            body["access_token"], "s" * 40, algorithms=["HS256"], issuer="brain-agent"
        )
        assert claims["role"] == body["user"]["role"] == "admin"
        bob = await h.client.post(
            "/auth/login", json={"email": "bob@acme.com", "password": PASSWORD}
        )
        assert bob.json()["user"]["role"] == "operator"

        me = await h.client.get(
            "/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
        )
        assert me.json()["email"] == "ana@acme.com"


async def test_weak_password_is_rejected() -> None:
    async with running_api([]) as h:
        weak = await h.client.post(
            "/auth/register", json={"email": "x@acme.com", "password": "short"}
        )
        assert weak.status_code == 422


async def test_registration_can_be_disabled() -> None:
    async with running_api([], make_settings(allow_registration=False)) as h:
        response = await h.client.post(
            "/auth/register", json={"email": "a@acme.com", "password": PASSWORD}
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "registration_disabled"


async def test_login_failure_is_generic() -> None:
    async with running_api([]) as h:
        await register(h.client)
        wrong = await h.client.post(
            "/auth/login", json={"email": "ana@acme.com", "password": "wrong-password-1"}
        )
        unknown = await h.client.post(
            "/auth/login", json={"email": "nobody@acme.com", "password": PASSWORD}
        )
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json() == unknown.json()


@pytest.mark.parametrize("kind", ["missing", "expired", "forged", "garbage"])
async def test_invalid_tokens_are_rejected(kind: str) -> None:
    now = int(time.time())
    claims = {"sub": "u", "role": "admin", "iat": now - 100, "exp": now - 50, "iss": "brain-agent"}
    headers = {}
    if kind == "expired":
        headers = {"Authorization": f"Bearer {jwt.encode(claims, 's' * 40, algorithm='HS256')}"}
    elif kind == "forged":
        claims["exp"] = now + 3600
        headers = {"Authorization": f"Bearer {jwt.encode(claims, 'x' * 40, algorithm='HS256')}"}
    elif kind == "garbage":
        headers = {"Authorization": "Bearer not-a-token"}
    async with running_api([]) as h:
        response = await h.client.get("/auth/me", headers=headers)
        assert response.status_code == 401


def test_production_requires_a_strong_jwt_secret() -> None:
    with pytest.raises(ConfigurationError):
        make_settings(environment="production", jwt_secret=None)
    with pytest.raises(ConfigurationError):
        make_settings(environment="production", jwt_secret="short")
    settings = make_settings(environment="production", jwt_secret="p" * 32, allow_registration=None)
    assert settings.registration_enabled is False


def test_development_generates_a_random_secret_per_process() -> None:
    first = make_settings(environment="development", jwt_secret=None, allow_registration=None)
    second = make_settings(environment="development", jwt_secret=None, allow_registration=None)
    assert first.jwt_secret is not None and second.jwt_secret is not None
    assert first.jwt_secret.get_secret_value() != second.jwt_secret.get_secret_value()
    assert first.registration_enabled is True
