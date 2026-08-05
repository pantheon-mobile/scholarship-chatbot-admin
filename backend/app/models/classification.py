from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, relationship

from app.db.base_class import Base


class ClassificationType(Base):
    __tablename__ = "classification_types"

    id: Mapped[int] = Column(BigInteger, primary_key=True, index=True)
    type_code: Mapped[str] = Column(String(20), unique=True, nullable=False)
    fixed_name: Mapped[str] = Column(String(50), nullable=False)
    display_label: Mapped[str] = Column(String(100), nullable=False)
    display_order: Mapped[int] = Column(Integer, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    version: Mapped[int] = Column(Integer, nullable=False, default=1)

    values = relationship(
        "ClassificationValue",
        back_populates="classification_type",
        order_by="ClassificationValue.display_order",
        cascade="all, delete-orphan",
    )


class ClassificationValue(Base):
    __tablename__ = "classification_values"
    __table_args__ = (
        UniqueConstraint("classification_type_id", "value_name", name="uq_classification_value_name"),
    )

    id: Mapped[int] = Column(BigInteger, primary_key=True, index=True)
    classification_type_id: Mapped[int] = Column(ForeignKey("classification_types.id"), nullable=False)
    value_name: Mapped[str] = Column(String(200), nullable=False)
    display_order: Mapped[int] = Column(Integer, nullable=False)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    version: Mapped[int] = Column(Integer, nullable=False, default=1)

    classification_type = relationship("ClassificationType", back_populates="values")
