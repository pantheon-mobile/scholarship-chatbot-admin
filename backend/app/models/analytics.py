from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, BigInteger, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, relationship

from app.db.base_class import Base


class AnalyticsVisitor(Base):
    __tablename__ = "analytics_visitors"
    __table_args__ = (
        UniqueConstraint("visitor_key", name="uq_analytics_visitors_visitor_key"),
        CheckConstraint("identity_kind IN ('AUTHENTICATED', 'ANONYMOUS')", name="ck_analytics_visitors_identity_kind"),
    )

    id: Mapped[UUID] = Column(Uuid, primary_key=True)
    visitor_key: Mapped[str] = Column(String(64), nullable=False)
    identity_kind: Mapped[str] = Column(String(20), nullable=False)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)


class AccessLog(Base):
    __tablename__ = "access_logs"
    __table_args__ = (
        Index("ix_access_logs_accessed_at", "accessed_at"),
        Index("ix_access_logs_visitor_accessed_at", "visitor_id", "accessed_at"),
    )

    id: Mapped[UUID] = Column(Uuid, primary_key=True)
    visitor_id: Mapped[UUID] = Column(ForeignKey("analytics_visitors.id", ondelete="RESTRICT"), nullable=False)
    accessed_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    visitor = relationship("AnalyticsVisitor")


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_chat_sessions_end_after_start"),
        Index("ix_chat_sessions_started_at", "started_at"),
        Index("ix_chat_sessions_visitor_started_at", "visitor_id", "started_at"),
    )

    id: Mapped[UUID] = Column(Uuid, primary_key=True)
    visitor_id: Mapped[UUID] = Column(ForeignKey("analytics_visitors.id", ondelete="RESTRICT"), nullable=False)
    started_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)
    recorded_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    visitor = relationship("AnalyticsVisitor")
    interactions = relationship("ChatInteraction", back_populates="chat_session", cascade="all, delete-orphan")


class ChatInteraction(Base):
    __tablename__ = "chat_interactions"
    __table_args__ = (
        UniqueConstraint("chat_session_id", "sequence_number", name="uq_chat_interactions_session_sequence"),
        CheckConstraint("sequence_number >= 1", name="ck_chat_interactions_sequence_positive"),
        CheckConstraint("processing_status IN ('PROCESSING', 'COMPLETED', 'FAILED')", name="ck_chat_interactions_processing_status"),
        CheckConstraint("answer_type IS NULL OR answer_type IN ('FAQ', 'GENERATED_AI', 'NO_ANSWER')", name="ck_chat_interactions_answer_type"),
        CheckConstraint(
            "(processing_status = 'COMPLETED' AND answer_type IS NOT NULL AND answer_displayed_at IS NOT NULL) "
            "OR (processing_status IN ('PROCESSING', 'FAILED') AND answer_type IS NULL AND answer_displayed_at IS NULL)",
            name="ck_chat_interactions_completion_state",
        ),
        CheckConstraint("answer_type = 'FAQ' OR faq_id IS NULL", name="ck_chat_interactions_faq_only_for_faq_answer"),
        CheckConstraint("answer_displayed_at IS NULL OR answer_displayed_at >= question_submitted_at", name="ck_chat_interactions_answer_after_question"),
        Index("ix_chat_interactions_question_submitted_at", "question_submitted_at"),
        Index("ix_chat_interactions_answer_type_question_submitted_at", "answer_type", "question_submitted_at"),
    )

    id: Mapped[UUID] = Column(Uuid, primary_key=True)
    chat_session_id: Mapped[UUID] = Column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    sequence_number: Mapped[int] = Column(Integer, nullable=False)
    question_submitted_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    answer_displayed_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)
    processing_status: Mapped[str] = Column(String(20), nullable=False)
    answer_type: Mapped[str | None] = Column(String(20), nullable=True)
    faq_id: Mapped[int | None] = Column(ForeignKey("faqs.id", ondelete="SET NULL"), nullable=True)
    question_text: Mapped[str | None] = Column(Text, nullable=True)
    answer_text: Mapped[str | None] = Column(Text, nullable=True)
    citations: Mapped[list | None] = Column(JSON, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    chat_session = relationship("ChatSession", back_populates="interactions")
    feedback = relationship("ChatFeedback", back_populates="interaction", uselist=False, cascade="all, delete-orphan")


class ChatFeedback(Base):
    __tablename__ = "chat_feedback"
    __table_args__ = (CheckConstraint("rating IN ('GOOD', 'BAD')", name="ck_chat_feedback_rating"),)

    interaction_id: Mapped[UUID] = Column(ForeignKey("chat_interactions.id", ondelete="CASCADE"), primary_key=True)
    rating: Mapped[str] = Column(String(10), nullable=False)
    comment: Mapped[str | None] = Column(String(1000), nullable=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    interaction = relationship("ChatInteraction", back_populates="feedback")
