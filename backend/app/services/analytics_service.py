import hashlib
import hmac
import os
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.models.analytics import AccessLog, ChatFeedback, ChatInteraction, ChatSession
from app.repositories.analytics import AnalyticsRepository
from app.schemas.analytics import (
    AccessCreateRequest,
    ChatSessionCreateRequest,
    FeedbackUpsertRequest,
    InteractionCompletionRequest,
    InteractionCreateRequest,
)


class AnalyticsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AnalyticsService:
    def __init__(self, repository: AnalyticsRepository, identity_secret: str | None = None) -> None:
        self.repository = repository
        self.identity_secret = identity_secret

    def visitor_key(self, identity_kind: str, identifier: str) -> str:
        secret = self.identity_secret or os.getenv("ANALYTICS_IDENTITY_SECRET")
        if not secret:
            raise AnalyticsError("ANALYTICS_SECRET_NOT_CONFIGURED", "利用統計の識別子秘密鍵が設定されていません。")
        message = f"{identity_kind}:{identifier}".encode("utf-8")
        return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    async def record_access(self, payload: AccessCreateRequest) -> AccessLog:
        now = datetime.now(timezone.utc)
        visitor_id = None
        try:
            visitor = await self.repository.get_or_create_visitor(
                self.visitor_key(payload.identity.identity_kind, payload.identity.identifier),
                payload.identity.identity_kind,
                now,
            )
            visitor_id = visitor.id
            existing = await self.repository.get_access(payload.id)
            if existing is not None:
                if existing.visitor_id != visitor_id or existing.accessed_at != payload.accessed_at:
                    raise AnalyticsError("IDEMPOTENCY_CONFLICT", "同じイベントIDに異なるアクセス内容が指定されています。")
                await self.repository.commit()
                return existing
            row = await self.repository.create_access(payload.id, visitor_id, payload.accessed_at, now)
            await self.repository.commit()
            return row
        except AnalyticsError:
            await self.repository.rollback()
            raise
        except IntegrityError as error:
            await self.repository.rollback()
            existing = await self.repository.get_access(payload.id)
            if visitor_id is not None and existing is not None and existing.visitor_id == visitor_id and existing.accessed_at == payload.accessed_at:
                return existing
            raise AnalyticsError("IDEMPOTENCY_CONFLICT", "アクセス記録が競合しました。") from error

    async def start_chat_session(self, payload: ChatSessionCreateRequest) -> ChatSession:
        now = datetime.now(timezone.utc)
        visitor_id = None
        try:
            visitor = await self.repository.get_or_create_visitor(
                self.visitor_key(payload.identity.identity_kind, payload.identity.identifier),
                payload.identity.identity_kind,
                now,
            )
            visitor_id = visitor.id
            existing = await self.repository.get_chat_session(payload.id)
            if existing is not None:
                if (
                    existing.visitor_id != visitor_id
                    or existing.started_at != payload.started_at
                    or existing.ended_at != payload.ended_at
                ):
                    raise AnalyticsError("IDEMPOTENCY_CONFLICT", "同じセッションIDに異なる内容が指定されています。")
                await self.repository.commit()
                return existing
            row = await self.repository.create_chat_session(
                payload.id, visitor_id, payload.started_at, payload.ended_at, now,
            )
            await self.repository.commit()
            return row
        except AnalyticsError:
            await self.repository.rollback()
            raise
        except IntegrityError as error:
            await self.repository.rollback()
            existing = await self.repository.get_chat_session(payload.id)
            if visitor_id is not None and existing is not None and (
                existing.visitor_id == visitor_id
                and existing.started_at == payload.started_at
                and existing.ended_at == payload.ended_at
            ):
                return existing
            raise AnalyticsError("IDEMPOTENCY_CONFLICT", "チャットセッション記録が競合しました。") from error

    async def start_interaction(self, session_id, payload: InteractionCreateRequest) -> ChatInteraction:
        now = datetime.now(timezone.utc)
        session = await self.repository.get_chat_session(session_id)
        if session is None:
            raise AnalyticsError("CHAT_SESSION_NOT_FOUND", "指定されたチャットセッションが見つかりません。")
        if payload.question_submitted_at < session.started_at:
            raise AnalyticsError("INVALID_INTERACTION_TIME", "質問送信日時はチャット開始日時以降を指定してください。")
        try:
            existing = await self.repository.get_interaction(payload.id)
            if existing is not None:
                if (
                    existing.chat_session_id != session_id
                    or existing.sequence_number != payload.sequence_number
                    or existing.question_submitted_at != payload.question_submitted_at
                    or existing.question_text != payload.question_text
                ):
                    raise AnalyticsError("IDEMPOTENCY_CONFLICT", "同じ応答IDに異なる内容が指定されています。")
                return existing
            row = await self.repository.create_interaction(
                payload.id, session_id, payload.sequence_number, payload.question_submitted_at, payload.question_text, now,
            )
            await self.repository.commit()
            return row
        except AnalyticsError:
            await self.repository.rollback()
            raise
        except IntegrityError as error:
            await self.repository.rollback()
            existing = await self.repository.get_interaction(payload.id)
            if existing is not None and (
                existing.chat_session_id == session_id
                and existing.sequence_number == payload.sequence_number
                and existing.question_submitted_at == payload.question_submitted_at
                and existing.question_text == payload.question_text
            ):
                return existing
            raise AnalyticsError("INTERACTION_SEQUENCE_CONFLICT", "同じチャット内の質問順序が重複しています。") from error

    async def complete_interaction(self, interaction_id, payload: InteractionCompletionRequest) -> ChatInteraction:
        try:
            row = await self.repository.get_interaction(interaction_id, for_update=True)
            if row is None:
                raise AnalyticsError("INTERACTION_NOT_FOUND", "指定された応答が見つかりません。")
            if row.processing_status != "PROCESSING":
                if (
                    row.processing_status == payload.processing_status
                    and row.answer_type == payload.answer_type
                    and row.answer_displayed_at == payload.answer_displayed_at
                    and row.faq_id == payload.faq_id
                    and row.answer_text == payload.answer_text
                    and (row.citations or []) == payload.citations
                ):
                    await self.repository.commit()
                    return row
                raise AnalyticsError("INTERACTION_STATE_CONFLICT", "応答はすでに別の内容で完了しています。")
            if payload.answer_displayed_at is not None and payload.answer_displayed_at < row.question_submitted_at:
                raise AnalyticsError("INVALID_INTERACTION_TIME", "回答表示完了日時は質問送信日時以降を指定してください。")
            if payload.answer_type == "FAQ" and not await self.repository.faq_exists(payload.faq_id):
                raise AnalyticsError("FAQ_NOT_FOUND", "指定されたFAQが見つかりません。")
            row.processing_status = payload.processing_status
            row.answer_type = payload.answer_type
            row.answer_displayed_at = payload.answer_displayed_at
            row.faq_id = payload.faq_id
            row.answer_text = payload.answer_text
            row.citations = payload.citations
            row.updated_at = datetime.now(timezone.utc)
            await self.repository.commit()
            return row
        except AnalyticsError:
            await self.repository.rollback()
            raise

    async def upsert_feedback(self, interaction_id, payload: FeedbackUpsertRequest) -> ChatFeedback:
        try:
            interaction = await self.repository.get_interaction(interaction_id, for_update=True)
            if interaction is None:
                raise AnalyticsError("INTERACTION_NOT_FOUND", "指定された応答が見つかりません。")
            if interaction.processing_status != "COMPLETED" or interaction.answer_type not in ("FAQ", "GENERATED_AI"):
                raise AnalyticsError("FEEDBACK_NOT_ALLOWED", "有効回答以外には評価を登録できません。")
            now = datetime.now(timezone.utc)
            row = await self.repository.get_feedback(interaction_id, for_update=True)
            if row is None:
                row = await self.repository.create_feedback(interaction_id, payload.rating, payload.comment, now)
            else:
                row.rating = payload.rating
                row.comment = payload.comment
                row.updated_at = now
            await self.repository.commit()
            return row
        except AnalyticsError:
            await self.repository.rollback()
            raise
