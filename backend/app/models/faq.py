from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, relationship

from app.db.base_class import Base


class Faq(Base):
    __tablename__ = "faqs"
    __table_args__ = (Index("ix_faqs_updated_at", "updated_at"), Index("ix_faqs_chat_enabled", "chat_enabled"))

    id: Mapped[int] = Column(BigInteger, primary_key=True)
    question: Mapped[str] = Column(String(500), nullable=False)
    answer: Mapped[str] = Column(String(1000), nullable=False)
    chat_enabled: Mapped[bool] = Column(Boolean, nullable=False)
    version: Mapped[int] = Column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    similar_questions = relationship(
        "FaqSimilarQuestion", back_populates="faq", order_by="FaqSimilarQuestion.display_order", cascade="all, delete-orphan"
    )
    classification_assignments = relationship("FaqClassificationAssignment", back_populates="faq", cascade="all, delete-orphan")


class FaqSimilarQuestion(Base):
    __tablename__ = "faq_similar_questions"
    __table_args__ = (
        UniqueConstraint("faq_id", "display_order", name="uq_faq_similar_question_order"),
        Index("ix_faq_similar_questions_faq_id", "faq_id"),
    )

    id: Mapped[int] = Column(BigInteger, primary_key=True)
    faq_id: Mapped[int] = Column(ForeignKey("faqs.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = Column(String(500), nullable=False)
    display_order: Mapped[int] = Column(Integer, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    faq = relationship("Faq", back_populates="similar_questions")


class FaqClassificationAssignment(Base):
    __tablename__ = "faq_classification_assignments"
    __table_args__ = (Index("ix_faq_classification_assignments_value_id", "classification_value_id"),)

    faq_id: Mapped[int] = Column(ForeignKey("faqs.id", ondelete="CASCADE"), primary_key=True)
    classification_type_id: Mapped[int] = Column(ForeignKey("faq_classification_types.id", ondelete="RESTRICT"), primary_key=True)
    classification_value_id: Mapped[int] = Column(ForeignKey("faq_classification_values.id", ondelete="RESTRICT"), nullable=False)

    faq = relationship("Faq", back_populates="classification_assignments")
    classification_type = relationship("FaqClassificationType")
    classification_value = relationship("FaqClassificationValue")
