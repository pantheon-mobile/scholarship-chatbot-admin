from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, DateTime, Integer, String, Uuid
from sqlalchemy.orm import Mapped

from app.db.base_class import Base


class CpfUsedJti(Base):
    __tablename__ = "cpf_used_jtis"

    jti: Mapped[UUID] = Column(Uuid, primary_key=True)
    expire_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'staff', 'student')", name="ck_auth_sessions_role"),
        CheckConstraint("site IN ('student', 'faculty')", name="ck_auth_sessions_site"),
    )

    token_hash: Mapped[str] = Column(String(64), primary_key=True)
    user_key: Mapped[str] = Column(String(1100), nullable=False, index=True)
    subject: Mapped[str] = Column(String(500), nullable=False)
    display_name: Mapped[str] = Column(String(500), nullable=False, default="")
    role: Mapped[str] = Column(String(20), nullable=False, index=True)
    site: Mapped[str] = Column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)
    expire_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, index=True)
    last_seen_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False)


class AdminOperationLog(Base):
    __tablename__ = "admin_operation_logs"

    id: Mapped[UUID] = Column(Uuid, primary_key=True)
    operator_key: Mapped[str] = Column(String(64), nullable=False, index=True)
    operator_role: Mapped[str] = Column(String(20), nullable=False)
    http_method: Mapped[str] = Column(String(10), nullable=False)
    request_path: Mapped[str] = Column(String(1000), nullable=False)
    status_code: Mapped[int] = Column(Integer, nullable=False)
    operated_at: Mapped[datetime] = Column(DateTime(timezone=True), nullable=False, index=True)
