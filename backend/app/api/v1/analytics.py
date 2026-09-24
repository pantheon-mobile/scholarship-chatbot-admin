from app.services.client_ip import client_ip
from app.services.server_access import verify_page_request
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.api.v1.auth import require_authenticated_session
from app.models.auth import AuthSession
from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import (
    AccessCreateRequest,
    AccessResponse,
    ChatSessionCreateRequest,
    ChatSessionResponse,
    FeedbackResponse,
    FeedbackUpsertRequest,
    InteractionCompletionRequest,
    InteractionCreateRequest,
    InteractionResponse,
)
from app.services.analytics_service import AnalyticsError, AnalyticsService


router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_service(session: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(AnalyticsRepository(session))


def api_error(error: AnalyticsError) -> HTTPException:
    if error.code == "ANALYTICS_SECRET_NOT_CONFIGURED":
        status = 500
    elif error.code in ("CHAT_SESSION_NOT_FOUND", "INTERACTION_NOT_FOUND", "FAQ_NOT_FOUND"):
        status = 404
    elif error.code in ("IDEMPOTENCY_CONFLICT", "INTERACTION_SEQUENCE_CONFLICT", "INTERACTION_STATE_CONFLICT"):
        status = 409
    else:
        status = 422
    return HTTPException(status_code=status, detail={"code": error.code, "message": error.message})


@router.post("/accesses", response_model=AccessResponse, status_code=201)
async def record_access(
    payload: AccessCreateRequest,
    request: Request,
    current: AuthSession = Depends(require_authenticated_session),
    service: AnalyticsService = Depends(get_service),
):
    surface = await verify_page_request(request, request.cookies.get("scholarship_session"))
    payload = payload.model_copy(update={"surface": surface})
    payload = payload.model_copy(update={"identity": payload.identity.model_copy(update={
        "identity_kind": "AUTHENTICATED", "identifier": f"{current.site}:{current.subject}",
    })})
    request.state.audit_surface = payload.surface
    request.state.audit_ip_address = client_ip(request, forwarded_for=payload.forwarded_for or "")
    request.state.audit_user_agent = (payload.user_agent or "")[:1000] or None
    try:
        return await service.record_access(
            payload, subject=current.subject, display_name=current.display_name,
            role=current.role, site=current.site,
            ip_address=request.state.audit_ip_address,
            user_agent=request.state.audit_user_agent,
        )
    except AnalyticsError as error:
        raise api_error(error) from None


@router.post("/chat-sessions", response_model=ChatSessionResponse, status_code=201)
async def start_chat_session(
    payload: ChatSessionCreateRequest,
    current: AuthSession = Depends(require_authenticated_session),
    service: AnalyticsService = Depends(get_service),
):
    payload = payload.model_copy(update={"identity": payload.identity.model_copy(update={
        "identity_kind": "AUTHENTICATED", "identifier": f"{current.site}:{current.subject}",
    })})
    try:
        return await service.start_chat_session(
            payload, subject=current.subject, display_name=current.display_name,
            role=current.role, site=current.site,
        )
    except AnalyticsError as error:
        raise api_error(error) from None


@router.post("/chat-sessions/{session_id}/interactions", response_model=InteractionResponse, status_code=201)
async def start_interaction(
    session_id: UUID,
    payload: InteractionCreateRequest,
    current: AuthSession = Depends(require_authenticated_session),
    service: AnalyticsService = Depends(get_service),
):
    try:
        return await service.start_interaction(
            session_id, payload,
            visitor_key=service.visitor_key("AUTHENTICATED", f"{current.site}:{current.subject}"),
        )
    except AnalyticsError as error:
        raise api_error(error) from None


@router.patch("/interactions/{interaction_id}/completion", response_model=InteractionResponse)
async def complete_interaction(
    interaction_id: UUID,
    payload: InteractionCompletionRequest,
    current: AuthSession = Depends(require_authenticated_session),
    service: AnalyticsService = Depends(get_service),
):
    # Answer contents are committed by /chat/messages, never by the browser.
    row = await service.repository.get_owned_interaction(
        interaction_id, service.visitor_key("AUTHENTICATED", f"{current.site}:{current.subject}"),
        for_update=True,
    )
    if row is None:
        raise api_error(AnalyticsError("INTERACTION_NOT_FOUND", "指定された応答が見つかりません。"))
    if payload.processing_status == "COMPLETED":
        if (row.processing_status != "COMPLETED" or row.answer_text != payload.answer_text
                or row.answer_type != payload.answer_type or row.faq_id != payload.faq_id
                or (row.citations or []) != payload.citations):
            raise HTTPException(status_code=409, detail="保存された回答と一致しません。")
        return row
    # A disconnected browser cannot erase a successfully generated answer.
    if row.processing_status == "COMPLETED":
        return row
    try:
        return await service.complete_interaction(
            interaction_id, payload,
            visitor_key=service.visitor_key("AUTHENTICATED", f"{current.site}:{current.subject}"),
        )
    except AnalyticsError as error:
        raise api_error(error) from None


@router.put("/interactions/{interaction_id}/feedback", response_model=FeedbackResponse)
async def upsert_feedback(
    interaction_id: UUID,
    payload: FeedbackUpsertRequest,
    current: AuthSession = Depends(require_authenticated_session),
    service: AnalyticsService = Depends(get_service),
):
    try:
        return await service.upsert_feedback(
            interaction_id, payload,
            visitor_key=service.visitor_key("AUTHENTICATED", f"{current.site}:{current.subject}"),
        )
    except AnalyticsError as error:
        raise api_error(error) from None
