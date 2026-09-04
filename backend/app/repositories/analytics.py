from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AccessLog, AnalyticsVisitor, ChatFeedback, ChatInteraction, ChatSession
from app.models.faq import Faq


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_visitor(
        self, visitor_key: str, identity_kind: str, now: datetime, *,
        subject: str | None = None, display_name: str | None = None,
        role: str | None = None, site: str | None = None,
    ) -> AnalyticsVisitor:
        statement = insert(AnalyticsVisitor).values(
            id=uuid4(), visitor_key=visitor_key, identity_kind=identity_kind,
            subject=subject, display_name=display_name, role=role, site=site,
            created_at=now, last_seen_at=now,
        ).on_conflict_do_update(
            constraint="uq_analytics_visitors_visitor_key",
            set_={
                "last_seen_at": now,
                "subject": subject,
                "display_name": display_name,
                "role": role,
                "site": site,
            },
        ).returning(AnalyticsVisitor.id)
        visitor_id = (await self.session.execute(statement)).scalar_one()
        return (await self.session.execute(select(AnalyticsVisitor).where(AnalyticsVisitor.id == visitor_id))).scalar_one()

    async def get_access(self, access_id: UUID) -> AccessLog | None:
        return await self.session.get(AccessLog, access_id)

    async def create_access(self, access_id: UUID, visitor_id: UUID, accessed_at: datetime, recorded_at: datetime, surface: str = "CHAT") -> AccessLog:
        row = AccessLog(id=access_id, visitor_id=visitor_id, accessed_at=accessed_at, recorded_at=recorded_at, surface=surface)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_chat_session(self, session_id: UUID) -> ChatSession | None:
        return await self.session.get(ChatSession, session_id)

    async def create_chat_session(
        self, session_id: UUID, visitor_id: UUID, started_at: datetime, ended_at: datetime | None, recorded_at: datetime,
    ) -> ChatSession:
        row = ChatSession(
            id=session_id, visitor_id=visitor_id, started_at=started_at, ended_at=ended_at, recorded_at=recorded_at,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_interaction(self, interaction_id: UUID, *, for_update: bool = False) -> ChatInteraction | None:
        statement = select(ChatInteraction).where(ChatInteraction.id == interaction_id)
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def create_interaction(
        self, interaction_id: UUID, session_id: UUID, sequence_number: int, question_submitted_at: datetime,
        question_text: str, now: datetime,
    ) -> ChatInteraction:
        row = ChatInteraction(
            id=interaction_id,
            chat_session_id=session_id,
            sequence_number=sequence_number,
            question_submitted_at=question_submitted_at,
            processing_status="PROCESSING",
            answer_type=None,
            answer_displayed_at=None,
            faq_id=None,
            question_text=question_text,
            answer_text=None,
            citations=None,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def faq_exists(self, faq_id: int) -> bool:
        return (await self.session.execute(select(Faq.id).where(Faq.id == faq_id))).scalar_one_or_none() is not None

    async def get_feedback(self, interaction_id: UUID, *, for_update: bool = False) -> ChatFeedback | None:
        statement = select(ChatFeedback).where(ChatFeedback.interaction_id == interaction_id)
        if for_update:
            statement = statement.with_for_update()
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def create_feedback(
        self, interaction_id: UUID, rating: str, comment: str | None, now: datetime,
    ) -> ChatFeedback:
        row = ChatFeedback(
            interaction_id=interaction_id, rating=rating, comment=comment, created_at=now, updated_at=now,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
