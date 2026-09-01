"""create ingestion jobs

Revision ID: 0008_ingestion_jobs
Revises: 0007_analytics
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_ingestion_jobs"
down_revision = "0007_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("data_source_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("worker_id", sa.String(length=200), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')",
            name="ck_ingestion_jobs_status",
        ),
        sa.CheckConstraint("attempt_count >= 0", name="ck_ingestion_jobs_attempt_count"),
        sa.CheckConstraint("max_attempts >= 1", name="ck_ingestion_jobs_max_attempts"),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ingestion_jobs_id", "ingestion_jobs", ["id"])
    op.create_index("ix_ingestion_jobs_data_source_id", "ingestion_jobs", ["data_source_id"])
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])
    op.create_index("ix_ingestion_jobs_scheduled_at", "ingestion_jobs", ["scheduled_at"])
    op.create_index(
        "uq_ingestion_jobs_active_data_source",
        "ingestion_jobs",
        ["data_source_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('QUEUED', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index("uq_ingestion_jobs_active_data_source", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_scheduled_at", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_status", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_data_source_id", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_id", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
