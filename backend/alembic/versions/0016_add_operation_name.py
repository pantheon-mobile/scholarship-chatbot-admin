"""add human-readable operation name

Revision ID: 0016_operation_name
Revises: 0015_log_request_context
"""
from alembic import op
import sqlalchemy as sa


revision = "0016_operation_name"
down_revision = "0015_log_request_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_operation_logs", sa.Column("operation_name", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_operation_logs", "operation_name")
