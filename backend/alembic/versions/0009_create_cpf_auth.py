"""create CPF SSO replay protection and sessions

Revision ID: 0009_cpf_auth
Revises: 0008_ingestion_jobs
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_cpf_auth"
down_revision = "0008_ingestion_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cpf_used_jtis",
        sa.Column("jti", sa.Uuid(), primary_key=True),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cpf_used_jtis_expire_at", "cpf_used_jtis", ["expire_at"])
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(length=64), primary_key=True),
        sa.Column("user_key", sa.String(length=1100), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=False),
        sa.Column("display_name", sa.String(length=500), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("site", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expire_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('admin', 'staff', 'student')", name="ck_auth_sessions_role"),
        sa.CheckConstraint("site IN ('student', 'faculty')", name="ck_auth_sessions_site"),
    )
    op.create_index("ix_auth_sessions_user_key", "auth_sessions", ["user_key"])
    op.create_index("ix_auth_sessions_role", "auth_sessions", ["role"])
    op.create_index("ix_auth_sessions_site", "auth_sessions", ["site"])
    op.create_index("ix_auth_sessions_expire_at", "auth_sessions", ["expire_at"])


def downgrade() -> None:
    op.drop_table("auth_sessions")
    op.drop_table("cpf_used_jtis")
