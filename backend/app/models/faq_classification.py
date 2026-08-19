from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, relationship

from app.db.base_class import Base


class FaqClassificationType(Base):
    __tablename__ = "faq_classification_types"

    id: Mapped[int] = Column(BigInteger, primary_key=True)
    type_code: Mapped[str] = Column(String, unique=True, nullable=False)
    fixed_name: Mapped[str] = Column(String, nullable=False)
    display_label: Mapped[str] = Column(String, nullable=False)
    display_order: Mapped[int] = Column(Integer, nullable=False)
    version: Mapped[int] = Column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    values = relationship(
        "FaqClassificationValue",
        back_populates="classification_type",
        order_by="FaqClassificationValue.display_order",
        cascade="all, delete-orphan",
    )


class FaqClassificationValue(Base):
    __tablename__ = "faq_classification_values"
    __table_args__ = (
        UniqueConstraint("classification_type_id", "value_name", name="uq_faq_classification_value_name"),
        Index("ix_faq_classification_values_type_id", "classification_type_id"),
    )

    id: Mapped[int] = Column(BigInteger, primary_key=True)
    classification_type_id: Mapped[int] = Column(
        ForeignKey("faq_classification_types.id", ondelete="CASCADE"), nullable=False
    )
    value_name: Mapped[str] = Column(String, nullable=False)
    display_order: Mapped[int] = Column(Integer, nullable=False)
    version: Mapped[int] = Column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    classification_type = relationship("FaqClassificationType", back_populates="values")
