import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.auth import require_authenticated_session
from app.core.db import get_db
from app.models.analytics import AnalyticsVisitor, ChatInteraction, ChatSession
from app.models.auth import AuthSession
from app.schemas.chat import (
    ChatHistoryDetail, ChatHistoryMessage, ChatHistorySummary, ChatHistoryTitleUpdate, ChatMessageRequest,
    ChatMessageResponse, ChatUiConfigResponse,
)
from app.repositories.analytics import AnalyticsRepository
from app.services.analytics_service import AnalyticsService
from app.services.chat_service import ChatConfigurationError, ChatGenerationError, ChatService


router = APIRouter(prefix="/chat", tags=["chat"])


def get_service() -> ChatService:
    return ChatService()


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() == "true"


def _options(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split("|") if item.strip()]


def _visitor_key(current_user: AuthSession) -> str:
    return AnalyticsService(AnalyticsRepository(None)).visitor_key(
        "AUTHENTICATED", f"{current_user.site}:{current_user.subject}"
    )


@router.get("/config", response_model=ChatUiConfigResponse)
async def get_chat_config(_current_user: AuthSession = Depends(require_authenticated_session)):
    return ChatUiConfigResponse(
        title=os.getenv("CHAT_UI_TITLE", "東京理科大学奨学金問合せチャット"),
        initial_message=os.getenv("CHAT_INITIAL_MESSAGE", "奨学金について知りたいことを入力してください。登録されている資料をもとに回答します。"),
        input_placeholder=os.getenv("CHAT_INPUT_PLACEHOLDER", "奨学金について質問を入力してください"),
        question_max_length=max(1, min(int(os.getenv("CHAT_QUESTION_MAX_LENGTH", "2000")), 5000)),
        frame_color=os.getenv("CHAT_FRAME_COLOR", "#171a1d"),
        bot_icon_url=os.getenv("CHAT_BOT_ICON_URL") or None,
        history_enabled=_flag("CHAT_HISTORY_ENABLED", "true"),
        maintenance_enabled=_flag("CHAT_MAINTENANCE_ENABLED"),
        maintenance_message=os.getenv("CHAT_MAINTENANCE_MESSAGE", "現在メンテナンス中です。時間をおいて再度お試しください。"),
        good_message=os.getenv("CHAT_GOOD_FEEDBACK_MESSAGE", "ご評価ありがとうございます。よろしければ理由をお聞かせください。"),
        bad_message=os.getenv("CHAT_BAD_FEEDBACK_MESSAGE", "改善のため、回答が役に立たなかった理由をお聞かせください。"),
        good_options=_options("CHAT_GOOD_FEEDBACK_OPTIONS", "知りたい内容だった|分かりやすかった|参照資料が役立った"),
        bad_options=_options("CHAT_BAD_FEEDBACK_OPTIONS", "回答が違う|情報が不足している|分かりにくい|参照資料が適切でない"),
    )


@router.get("/sessions", response_model=list[ChatHistorySummary])
async def list_chat_sessions(
    limit: int = Query(default=100, ge=1, le=200),
    search: str | None = Query(default=None, max_length=200),
    current_user: AuthSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_db),
):
    completed_interaction_exists = select(ChatInteraction.id).where(
        ChatInteraction.chat_session_id == ChatSession.id,
        ChatInteraction.processing_status == "COMPLETED",
    ).correlate(ChatSession).exists()
    statement = (
        select(ChatSession)
        .join(AnalyticsVisitor)
        .where(
            AnalyticsVisitor.visitor_key == _visitor_key(current_user),
            completed_interaction_exists,
        )
        .options(selectinload(ChatSession.interactions))
        .order_by(ChatSession.started_at.desc())
    )
    normalized_search = search.strip() if search else ""
    if normalized_search:
        pattern = f"%{normalized_search}%"
        statement = statement.join(ChatInteraction, ChatInteraction.chat_session_id == ChatSession.id, isouter=True).where(
            ChatInteraction.processing_status == "COMPLETED",
            or_(ChatSession.title.ilike(pattern), ChatInteraction.question_text.ilike(pattern), ChatInteraction.answer_text.ilike(pattern))
        ).distinct()
    statement = statement.limit(limit)
    rows = (await session.execute(statement)).scalars().unique().all()
    result = []
    for row in rows:
        interactions = sorted(
            (item for item in row.interactions if item.processing_status == "COMPLETED"),
            key=lambda item: item.sequence_number,
        )
        first_question = next((item.question_text for item in interactions if item.question_text), None)
        updated_at = max((item.updated_at for item in interactions), default=row.started_at)
        result.append(ChatHistorySummary(
            id=row.id,
            title=row.title or ((first_question[:40] + ("…" if len(first_question) > 40 else "")) if first_question else "新しいチャット"),
            started_at=row.started_at,
            updated_at=updated_at,
        ))
    return result


@router.get("/sessions/{session_id}", response_model=ChatHistoryDetail)
async def get_chat_session_history(
    session_id: UUID,
    current_user: AuthSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_db),
):
    completed_interaction_exists = select(ChatInteraction.id).where(
        ChatInteraction.chat_session_id == ChatSession.id,
        ChatInteraction.processing_status == "COMPLETED",
    ).correlate(ChatSession).exists()
    statement = (
        select(ChatSession)
        .join(AnalyticsVisitor)
        .where(
            ChatSession.id == session_id,
            AnalyticsVisitor.visitor_key == _visitor_key(current_user),
            completed_interaction_exists,
        )
        .options(selectinload(ChatSession.interactions).selectinload(ChatInteraction.feedback))
    )
    row = (await session.execute(statement)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="チャット履歴が見つかりません。")
    interactions = sorted(
        (item for item in row.interactions if item.processing_status == "COMPLETED"),
        key=lambda item: item.sequence_number,
    )
    messages: list[ChatHistoryMessage] = []
    for item in interactions:
        if item.question_text:
            messages.append(ChatHistoryMessage(
                id=f"{item.id}-question", role="user", content=item.question_text,
                sent_at=item.question_submitted_at,
            ))
        if item.answer_text and item.answer_displayed_at:
            messages.append(ChatHistoryMessage(
                id=f"{item.id}-answer", role="assistant", content=item.answer_text,
                sent_at=item.answer_displayed_at, citations=item.citations or [],
                interaction_id=item.id, rating=item.feedback.rating if item.feedback else None,
                answer_type=item.answer_type,
            ))
    first_question = next((item.question_text for item in interactions if item.question_text), None)
    title = row.title or ((first_question[:40] + ("…" if len(first_question) > 40 else "")) if first_question else "新しいチャット")
    return ChatHistoryDetail(id=row.id, title=title, messages=messages)


async def _owned_chat_session(session_id: UUID, current_user: AuthSession, session: AsyncSession) -> ChatSession:
    statement = (
        select(ChatSession)
        .join(AnalyticsVisitor)
        .where(
            ChatSession.id == session_id,
            AnalyticsVisitor.visitor_key == _visitor_key(current_user),
        )
        .options(selectinload(ChatSession.interactions))
    )
    row = (await session.execute(statement)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="チャット履歴が見つかりません。")
    return row


@router.patch("/sessions/{session_id}", response_model=ChatHistorySummary)
async def update_chat_session_title(
    session_id: UUID,
    payload: ChatHistoryTitleUpdate,
    current_user: AuthSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_db),
):
    row = await _owned_chat_session(session_id, current_user, session)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="チャット名を入力してください。")
    row.title = title
    await session.commit()
    updated_at = max((item.updated_at for item in row.interactions), default=row.started_at)
    return ChatHistorySummary(id=row.id, title=row.title, started_at=row.started_at, updated_at=updated_at)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_chat_session(
    session_id: UUID,
    current_user: AuthSession = Depends(require_authenticated_session),
    session: AsyncSession = Depends(get_db),
):
    row = await _owned_chat_session(session_id, current_user, session)
    await session.delete(row)
    await session.commit()


@router.post("/messages", response_model=ChatMessageResponse)
async def send_message(
    payload: ChatMessageRequest,
    _current_user: AuthSession = Depends(require_authenticated_session),
    service: ChatService = Depends(get_service),
):
    if _flag("CHAT_MAINTENANCE_ENABLED"):
        raise HTTPException(status_code=503, detail=os.getenv("CHAT_MAINTENANCE_MESSAGE", "現在メンテナンス中です。"))
    try:
        return await service.answer(payload.question, payload.bedrock_session_id)
    except ChatConfigurationError:
        raise HTTPException(status_code=503, detail="チャット機能の設定が完了していません。") from None
    except ChatGenerationError:
        raise HTTPException(status_code=502, detail="回答を生成できませんでした。時間をおいて再度お試しください。") from None
