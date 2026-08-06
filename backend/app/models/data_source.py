from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

from app.db.base_class import Base


class DataSource(Base):
    __tablename__ = "data_sources"
    __table_args__ = (
        CheckConstraint("source_type IN ('FILE', 'WEB')", name="ck_data_sources_source_type"),
        CheckConstraint("status IN ('PREPARING', 'TRAINING', 'AVAILABLE', 'ERROR')", name="ck_data_sources_status"),
        CheckConstraint("priority IN ('HIGH', 'MEDIUM', 'LOW')", name="ck_data_sources_priority"),
    )

    id: Mapped[int] = Column(BigInteger, primary_key=True, index=True)
    source_type: Mapped[str] = Column(String(10), nullable=False, index=True)
    title: Mapped[str] = Column(String(500), nullable=False, index=True)
    format: Mapped[str] = Column(String(20), nullable=False, index=True)
    status: Mapped[str] = Column(String(20), nullable=False, index=True)
    category_name: Mapped[str | None] = Column(String(200), nullable=True)
    size_bytes: Mapped[int | None] = Column(BigInteger, nullable=True)
    character_count: Mapped[int | None] = Column(BigInteger, nullable=True)
    answer_source_enabled: Mapped[bool] = Column(Boolean, nullable=False, default=True, index=True)
    priority: Mapped[str] = Column(String(10), nullable=False, index=True)
    reference_link_visible: Mapped[bool] = Column(Boolean, nullable=False, default=True, index=True)
    updated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, index=True)
    version: Mapped[int] = Column(Integer, nullable=False, default=1)

    file = relationship("DataSourceFile", back_populates="data_source", uselist=False, cascade="all, delete-orphan")
    website = relationship("DataSourceWebsite", back_populates="data_source", uselist=False, cascade="all, delete-orphan")
    classification_links = relationship("DataSourceClassificationValue", back_populates="data_source", cascade="all, delete-orphan")


class DataSourceFile(Base):
    __tablename__ = "data_source_files"

    data_source_id: Mapped[int] = Column(ForeignKey("data_sources.id", ondelete="CASCADE"), primary_key=True)
    file_name: Mapped[str] = Column(String(500), nullable=False)
    storage_key: Mapped[str | None] = Column(String(1000), nullable=True)
    mime_type: Mapped[str | None] = Column(String(255), nullable=True)
    data_source = relationship("DataSource", back_populates="file")


class DataSourceWebsite(Base):
    __tablename__ = "data_source_websites"

    data_source_id: Mapped[int] = Column(ForeignKey("data_sources.id", ondelete="CASCADE"), primary_key=True)
    url: Mapped[str] = Column(Text, nullable=False)
    last_fetched_at: Mapped[datetime | None] = Column(DateTime(timezone=True), nullable=True)
    data_source = relationship("DataSource", back_populates="website")


class DataSourceClassificationValue(Base):
    __tablename__ = "data_source_classification_values"

    data_source_id: Mapped[int] = Column(ForeignKey("data_sources.id", ondelete="CASCADE"), primary_key=True)
    classification_type_id: Mapped[int] = Column(ForeignKey("classification_types.id", ondelete="RESTRICT"), primary_key=True)
    classification_value_id: Mapped[int] = Column(ForeignKey("classification_values.id", ondelete="RESTRICT"), nullable=False, index=True)

    data_source = relationship("DataSource", back_populates="classification_links")
    classification_type = relationship("ClassificationType")
    classification_value = relationship("ClassificationValue")
