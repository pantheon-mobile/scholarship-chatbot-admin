"""create administrative operation logs

Revision ID: 0010_operation_logs
Revises: 0009_cpf_auth
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_operation_logs"
down_revision = "0009_cpf_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_operation_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("operator_key", sa.String(length=64), nullable=False),
        sa.Column("operator_role", sa.String(length=20), nullable=False),
        sa.Column("http_method", sa.String(length=10), nullable=False),
        sa.Column("request_path", sa.String(length=1000), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("operated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_admin_operation_logs_operator_key", "admin_operation_logs", ["operator_key"])
    op.create_index("ix_admin_operation_logs_operated_at", "admin_operation_logs", ["operated_at"])


def downgrade() -> None:
    op.drop_table("admin_operation_logs")
