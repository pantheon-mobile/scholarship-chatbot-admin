from __future__ import annotations

import json
import os
import secrets
import time
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import jwt

from app.models.auth import AuthSession
from app.repositories.auth import AuthRepository
from app.schemas.auth import AuthenticatedUserResponse
from app.services.auth_token import session_token_hash


class AuthConfigurationError(Exception):
    pass


class CpfAuthenticationError(Exception):
    pass


class CpfReplayError(CpfAuthenticationError):
    pass


class SessionNotFoundError(Exception):
    pass


def development_mock_enabled() -> bool:
    return (
        os.getenv("APP_ENV", "production") == "development"
        and os.getenv("ENABLE_DEVELOPMENT_CPF_MOCK", "false").lower() == "true"
    )


def development_jwt_secret() -> str:
    secret = os.getenv("CPF_DEVELOPMENT_JWT_SECRET", "")
    if len(secret) < 32:
        raise AuthConfigurationError("development CPF JWT secret is not configured")
    return secret


def issue_development_cpf_token(*, subject: str, display_name: str, role: str) -> str:
    if not development_mock_enabled():
        raise AuthConfigurationError("development CPF mock is disabled")
    now = int(time.time())
    ttl = max(1, min(int(os.getenv("CPF_DEVELOPMENT_JWT_TTL_SECONDS", "300")), 300))
    return jwt.encode(
        {
            "iss": "cpf-development",
            "aud": "chatbot-development",
            "sub": subject.strip(),
            "name": display_name.strip(),
            "role": role,
            "site": "faculty",
            "purpose": "sso-development",
            "jti": str(uuid4()),
            "iat": now,
            "exp": now + ttl,
        },
        development_jwt_secret(),
        algorithm="HS256",
    )


def verify_development_cpf_token(token: str) -> dict:
    if not development_mock_enabled():
        raise AuthConfigurationError("development CPF mock is disabled")
    try:
        claims = jwt.decode(
            token,
            development_jwt_secret(),
            algorithms=["HS256"],
            issuer="cpf-development",
            audience="chatbot-development",
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise CpfAuthenticationError("invalid development CPF token") from exc
    if claims.get("purpose") != "sso-development" or claims.get("site") != "faculty":
        raise CpfAuthenticationError("invalid development CPF claims")
    if claims.get("role") not in {"admin", "staff"}:
        raise CpfAuthenticationError("invalid development CPF role")
    subject, display_name = claims.get("sub"), claims.get("name")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 500:
        raise CpfAuthenticationError("invalid development CPF subject")
    if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 500:
        raise CpfAuthenticationError("invalid development CPF display name")
    try:
        claims["jti_uuid"] = UUID(str(claims.get("jti")))
    except (TypeError, ValueError) as exc:
        raise CpfAuthenticationError("invalid development CPF jti") from exc
    claims["sub"] = subject.strip()
    claims["name"] = display_name.strip()
    return claims


def load_cpf_public_keys() -> dict[str, str] | list[str]:
    keyed: dict[str, str] = {}
    inline_by_kid = os.getenv("CPF_PUBLIC_KEYS_BY_KID", "").strip()
    paths_by_kid = os.getenv("CPF_PUBLIC_KEY_PATHS_BY_KID", "").strip()
    try:
        if inline_by_kid:
            values = json.loads(inline_by_kid)
            if not isinstance(values, dict):
                raise ValueError
            keyed.update(
                {
                    str(kid): str(value).replace("\\n", "\n")
                    for kid, value in values.items()
                }
            )
        if paths_by_kid:
            values = json.loads(paths_by_kid)
            if not isinstance(values, dict):
                raise ValueError
            keyed.update(
                {
                    str(kid): Path(str(path)).read_text(encoding="utf-8")
                    for kid, path in values.items()
                }
            )
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        raise AuthConfigurationError("CPF kid public key configuration is invalid") from exc
    if keyed:
        if any(not kid.strip() or not key.strip() for kid, key in keyed.items()):
            raise AuthConfigurationError("CPF kid public key configuration is invalid")
        return keyed

    keys: list[str] = []
    inline = os.getenv("CPF_PUBLIC_KEYS", "").strip()
    if inline:
        keys.extend(item.strip().replace("\\n", "\n") for item in inline.split("||") if item.strip())
    paths = os.getenv("CPF_PUBLIC_KEY_PATHS", "").strip()
    if paths:
        for raw_path in paths.split(","):
            path = Path(raw_path.strip())
            if path:
                keys.append(path.read_text(encoding="utf-8"))
    if not keys:
        raise AuthConfigurationError("CPF public key is not configured")
    return keys


def verify_cpf_token(
    token: str,
    public_keys: Mapping[str, str] | list[str],
    *,
    now: float | None = None,
) -> dict:
    current_time = time.time() if now is None else now
    claims = None
    last_error: Exception | None = None
    if isinstance(public_keys, Mapping):
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise CpfAuthenticationError("invalid CPF token header") from exc
        kid = header.get("kid")
        if not isinstance(kid, str) or kid not in public_keys:
            raise CpfAuthenticationError("unknown CPF kid")
        candidate_keys = [public_keys[kid]]
    else:
        candidate_keys = public_keys
    for public_key in candidate_keys:
        try:
            candidate = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=os.getenv("CPF_JWT_ISSUER", "cpf"),
                audience=os.getenv("CPF_JWT_AUDIENCE", "chatbot"),
                options={"require": ["exp", "iat", "sub", "jti"]},
                leeway=int(os.getenv("CPF_JWT_LEEWAY_SECONDS", "30")),
            )
            claims = candidate
            break
        except jwt.PyJWTError as exc:
            last_error = exc
    if claims is None:
        raise CpfAuthenticationError("invalid CPF token") from last_error
    if not isinstance(claims.get("aud"), str):
        raise CpfAuthenticationError("aud must be a string")
    if claims.get("purpose") != "sso":
        raise CpfAuthenticationError("purpose mismatch")
    if claims.get("site") not in {"student", "faculty"}:
        raise CpfAuthenticationError("site mismatch")
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 500:
        raise CpfAuthenticationError("invalid subject")
    role = claims.get("role")
    accepted_roles = {
        item.strip() for item in os.getenv("CPF_ACCEPTED_ROLES", "admin,staff").split(",")
        if item.strip()
    }
    if role not in {"admin", "staff", "student"} or role not in accepted_roles:
        raise CpfAuthenticationError("role is not accepted")
    issued_at, expire_at = claims.get("iat"), claims.get("exp")
    if not isinstance(issued_at, (int, float)) or not isinstance(expire_at, (int, float)):
        raise CpfAuthenticationError("invalid token timestamps")
    max_ttl = int(os.getenv("CPF_JWT_MAX_TTL_SECONDS", "360"))
    if expire_at > current_time + max_ttl or expire_at - issued_at > max_ttl:
        raise CpfAuthenticationError("token expiry is too far")
    try:
        claims["jti_uuid"] = UUID(str(claims.get("jti")))
    except (TypeError, ValueError) as exc:
        raise CpfAuthenticationError("jti must be UUID") from exc
    display_name = claims.get("name", "")
    if not isinstance(display_name, str) or len(display_name) > 500:
        raise CpfAuthenticationError("invalid display name")
    claims["sub"] = subject.strip()
    claims["name"] = display_name.strip()
    return claims


class AuthService:
    def __init__(
        self,
        repository: AuthRepository,
        public_keys: Mapping[str, str] | list[str] | None = None,
    ) -> None:
        self.repository = repository
        self.public_keys = public_keys

    async def exchange_cpf_token(self, token: str) -> tuple[str, AuthenticatedUserResponse]:
        claims = verify_cpf_token(token, self.public_keys or load_cpf_public_keys())
        return await self._create_session(claims)

    async def exchange_development_cpf_token(self, token: str) -> tuple[str, AuthenticatedUserResponse]:
        return await self._create_session(verify_development_cpf_token(token))

    async def _create_session(self, claims: dict) -> tuple[str, AuthenticatedUserResponse]:
        now = datetime.now(timezone.utc)
        session_seconds = int(os.getenv("AUTH_SESSION_TTL_SECONDS", "28800"))
        raw_session_token = secrets.token_urlsafe(48)
        session = AuthSession(
            token_hash=session_token_hash(raw_session_token),
            user_key=f"{claims['site']}:{claims['sub']}",
            subject=claims["sub"],
            display_name=claims["name"],
            role=claims["role"],
            site=claims["site"],
            created_at=now,
            expire_at=now + timedelta(seconds=session_seconds),
            last_seen_at=now,
        )
        consumed = await self.repository.create_session_once(
            jti=claims["jti_uuid"],
            jwt_expire_at=datetime.fromtimestamp(claims["exp"], timezone.utc),
            session=session,
        )
        if not consumed:
            raise CpfReplayError("CPF token has already been used")
        return raw_session_token, self._response(session)

    async def get_session(self, raw_session_token: str) -> AuthenticatedUserResponse:
        row = await self.repository.get_session(
            session_token_hash(raw_session_token), datetime.now(timezone.utc)
        )
        if row is None:
            raise SessionNotFoundError()
        return self._response(row)

    async def logout(self, raw_session_token: str | None) -> None:
        if raw_session_token:
            await self.repository.delete_session(session_token_hash(raw_session_token))

    @staticmethod
    def _response(session: AuthSession) -> AuthenticatedUserResponse:
        return AuthenticatedUserResponse(
            subject=session.subject,
            display_name=session.display_name,
            role=session.role,
            site=session.site,
        )
