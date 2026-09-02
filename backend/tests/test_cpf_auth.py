import time
from uuid import uuid4
from unittest.mock import AsyncMock

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.auth import get_service, router
from app.services.auth_service import (
    AuthConfigurationError,
    AuthService,
    CpfAuthenticationError,
    issue_development_cpf_token,
)


@pytest.fixture(scope="module")
def key_pair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode(),
    )


def make_token(private_key: bytes, **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": "cpf",
        "aud": "chatbot",
        "sub": "user-001",
        "name": "奨学 太郎",
        "role": "staff",
        "site": "faculty",
        "purpose": "sso",
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256")


@pytest.mark.anyio
async def test_exchange_creates_chatbot_session_once(key_pair):
    private_key, public_key = key_pair
    repository = AsyncMock()
    repository.create_session_once.return_value = True
    service = AuthService(repository, [public_key])

    raw_token, user = await service.exchange_cpf_token(make_token(private_key))

    assert raw_token
    assert user.subject == "user-001"
    assert user.display_name == "奨学 太郎"
    assert user.role == "staff"
    assert user.site == "faculty"
    session = repository.create_session_once.await_args.kwargs["session"]
    assert session.token_hash != raw_token
    assert session.user_key == "faculty:user-001"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "overrides",
    [
        {"purpose": "other"},
        {"aud": ["chatbot"]},
        {"site": "other"},
        {"role": "student"},
        {"jti": "not-a-uuid"},
        {"exp": int(time.time()) + 700},
    ],
)
async def test_exchange_rejects_invalid_or_unaccepted_claims(key_pair, overrides):
    private_key, public_key = key_pair
    service = AuthService(AsyncMock(), [public_key])

    with pytest.raises(CpfAuthenticationError):
        await service.exchange_cpf_token(make_token(private_key, **overrides))


@pytest.mark.anyio
async def test_api_sets_http_only_session_cookie_and_hides_auth_reason(monkeypatch):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    service = AsyncMock()
    service.exchange_cpf_token.side_effect = CpfAuthenticationError("secret diagnostic")
    app.dependency_overrides[get_service] = lambda: service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        rejected = await client.post("/api/v1/auth/cpf", json={"token": "invalid"})
    assert rejected.status_code == 401
    assert "secret diagnostic" not in rejected.text

    from app.schemas.auth import AuthenticatedUserResponse

    service.exchange_cpf_token.side_effect = None
    service.exchange_cpf_token.return_value = (
        "opaque-session-token",
        AuthenticatedUserResponse(
            subject="user-001", display_name="奨学 太郎", role="staff", site="faculty"
        ),
    )
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        accepted = await client.post("/api/v1/auth/cpf", json={"token": "signed-jwt"})

    cookie = accepted.headers["set-cookie"]
    assert accepted.status_code == 200
    assert "scholarship_session=opaque-session-token" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie


@pytest.mark.anyio
async def test_development_cpf_issues_short_lived_token_and_creates_session(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ENABLE_DEVELOPMENT_CPF_MOCK", "true")
    monkeypatch.setenv("CPF_DEVELOPMENT_JWT_SECRET", "test-development-secret-at-least-32-characters")
    repository = AsyncMock()
    repository.create_session_once.return_value = True
    service = AuthService(repository)

    token = issue_development_cpf_token(
        subject=" staff-001 ", display_name=" 開発 職員 ", role="staff"
    )
    raw_session, user = await service.exchange_development_cpf_token(token)

    assert raw_session
    assert user.subject == "staff-001"
    assert user.display_name == "開発 職員"
    assert user.role == "staff"
    session = repository.create_session_once.await_args.kwargs["session"]
    assert session.user_key == "faculty:staff-001"


def test_development_cpf_is_disabled_outside_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ENABLE_DEVELOPMENT_CPF_MOCK", "true")
    monkeypatch.setenv("CPF_DEVELOPMENT_JWT_SECRET", "test-development-secret-at-least-32-characters")

    with pytest.raises(AuthConfigurationError):
        issue_development_cpf_token(subject="admin-001", display_name="管理者", role="admin")
