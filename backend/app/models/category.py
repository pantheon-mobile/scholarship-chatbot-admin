from datetime import datetime, timezone

from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped

from app.db.base_class import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("name = btrim(name) AND name <> ''", name="ck_categories_name_trimmed"),
        CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_categories_not_self_parent"),
        CheckConstraint("display_order >= 1", name="ck_categories_display_order_positive"),
        Index(
            "uq_categories_parent_name",
            "parent_id",
            "name",
            unique=True,
            postgresql_where=text("parent_id IS NOT NULL"),
        ),
        Index(
            "uq_categories_root_name",
            "name",
            unique=True,
            postgresql_where=text("parent_id IS NULL"),
        ),
    )

    id: Mapped[int] = Column(BigInteger, primary_key=True)
    name: Mapped[str] = Column(String(15), nullable=False)
    parent_id: Mapped[int | None] = Column(ForeignKey("categories.id", ondelete="CASCADE"), nullable=True, index=True)
    display_order: Mapped[int] = Column(Integer, nullable=False)
    version: Mapped[int] = Column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
