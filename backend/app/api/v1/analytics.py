from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
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
async def record_access(payload: AccessCreateRequest, service: AnalyticsService = Depends(get_service)):
    try:
        return await service.record_access(payload)
    except AnalyticsError as error:
        raise api_error(error) from None


@router.post("/chat-sessions", response_model=ChatSessionResponse, status_code=201)
async def start_chat_session(payload: ChatSessionCreateRequest, service: AnalyticsService = Depends(get_service)):
    try:
        return await service.start_chat_session(payload)
    except AnalyticsError as error:
        raise api_error(error) from None


@router.post("/chat-sessions/{session_id}/interactions", response_model=InteractionResponse, status_code=201)
async def start_interaction(
    session_id: UUID,
    payload: InteractionCreateRequest,
    service: AnalyticsService = Depends(get_service),
):
    try:
        return await service.start_interaction(session_id, payload)
    except AnalyticsError as error:
        raise api_error(error) from None


@router.patch("/interactions/{interaction_id}/completion", response_model=InteractionResponse)
async def complete_interaction(
    interaction_id: UUID,
    payload: InteractionCompletionRequest,
    service: AnalyticsService = Depends(get_service),
):
    try:
        return await service.complete_interaction(interaction_id, payload)
    except AnalyticsError as error:
        raise api_error(error) from None


@router.put("/interactions/{interaction_id}/feedback", response_model=FeedbackResponse)
async def upsert_feedback(
    interaction_id: UUID,
    payload: FeedbackUpsertRequest,
    service: AnalyticsService = Depends(get_service),
):
    try:
        return await service.upsert_feedback(interaction_id, payload)
    except AnalyticsError as error:
        raise api_error(error) from None
