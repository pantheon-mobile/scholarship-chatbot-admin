import os

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.models.auth import AuthSession
from app.repositories.auth import AuthRepository
from app.schemas.auth import (
    AuthenticatedUserResponse,
    CpfTokenExchangeRequest,
    DevelopmentCpfTokenRequest,
    DevelopmentCpfTokenResponse,
)
from app.services.auth_service import (
    AuthConfigurationError,
    AuthService,
    CpfAuthenticationError,
    SessionNotFoundError,
    issue_development_cpf_token,
)


router = APIRouter(prefix="/auth", tags=["auth"])
SESSION_COOKIE_NAME = "scholarship_session"


def get_service(session: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(AuthRepository(session))


async def require_authenticated_session(
    request: Request,
    scholarship_session: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_db),
) -> AuthSession:
    if not scholarship_session:
        raise HTTPException(status_code=401, detail="認証が必要です。")
    repository = AuthRepository(session)
    row = await repository.get_session_row(scholarship_session)
    if row is None:
        raise HTTPException(status_code=401, detail="セッションの有効期限が切れています。")
    if row.role not in {"admin", "staff"}:
        raise HTTPException(status_code=403, detail="管理画面を利用する権限がありません。")
    request.state.auth_session = row
    return row


async def require_system_admin_session(
    current_session: AuthSession = Depends(require_authenticated_session),
) -> AuthSession:
    if current_session.role != "admin":
        raise HTTPException(status_code=403, detail="システム管理者の権限が必要です。")
    return current_session


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=int(os.getenv("AUTH_SESSION_TTL_SECONDS", "28800")),
        httponly=True,
        secure=os.getenv("AUTH_COOKIE_SECURE", "true").lower() == "true",
        samesite="lax",
        path="/",
        domain=os.getenv("AUTH_COOKIE_DOMAIN") or None,
    )


@router.post("/cpf", response_model=AuthenticatedUserResponse)
async def exchange_cpf_token(
    payload: CpfTokenExchangeRequest,
    response: Response,
    service: AuthService = Depends(get_service),
):
    try:
        session_token, user = await service.exchange_cpf_token(payload.token)
    except AuthConfigurationError:
        raise HTTPException(status_code=503, detail="SSO設定が完了していません。") from None
    except CpfAuthenticationError:
        raise HTTPException(status_code=401, detail="CPFからもう一度アクセスしてください。") from None
    _set_session_cookie(response, session_token)
    return user


@router.post("/development/token", response_model=DevelopmentCpfTokenResponse)
async def create_development_cpf_token(payload: DevelopmentCpfTokenRequest):
    try:
        token = issue_development_cpf_token(
            subject=payload.subject,
            display_name=payload.display_name,
            role=payload.role,
        )
    except AuthConfigurationError:
        raise HTTPException(status_code=404, detail="開発用CPFは利用できません。") from None
    return DevelopmentCpfTokenResponse(token=token)


@router.post("/development/cpf", response_model=AuthenticatedUserResponse)
async def exchange_development_cpf_token(
    payload: CpfTokenExchangeRequest,
    response: Response,
    service: AuthService = Depends(get_service),
):
    try:
        session_token, user = await service.exchange_development_cpf_token(payload.token)
    except AuthConfigurationError:
        raise HTTPException(status_code=404, detail="開発用CPFは利用できません。") from None
    except CpfAuthenticationError:
        raise HTTPException(status_code=401, detail="開発用ログイン情報が無効です。") from None
    _set_session_cookie(response, session_token)
    return user


@router.get("/session", response_model=AuthenticatedUserResponse)
async def get_current_session(
    scholarship_session: str | None = Cookie(default=None),
    service: AuthService = Depends(get_service),
):
    if not scholarship_session:
        raise HTTPException(status_code=401, detail="認証が必要です。")
    try:
        return await service.get_session(scholarship_session)
    except SessionNotFoundError:
        raise HTTPException(status_code=401, detail="セッションの有効期限が切れています。") from None


@router.delete("/session", status_code=204)
async def logout(
    response: Response,
    scholarship_session: str | None = Cookie(default=None),
    service: AuthService = Depends(get_service),
):
    await service.logout(scholarship_session)
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        domain=os.getenv("AUTH_COOKIE_DOMAIN") or None,
    )
