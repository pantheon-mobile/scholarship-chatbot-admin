"""add request context to access and operation logs

Revision ID: 0015_log_request_context
Revises: 0014_access_surface
"""
from alembic import op
import sqlalchemy as sa


revision = "0015_log_request_context"
down_revision = "0014_access_surface"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("access_logs", sa.Column("ip_address", sa.String(length=64), nullable=True))
    op.add_column("access_logs", sa.Column("user_agent", sa.String(length=1000), nullable=True))
    op.add_column(
        "admin_operation_logs",
        sa.Column("surface", sa.String(length=20), nullable=False, server_default="ADMIN"),
    )
    op.add_column("admin_operation_logs", sa.Column("ip_address", sa.String(length=64), nullable=True))
    op.add_column("admin_operation_logs", sa.Column("user_agent", sa.String(length=1000), nullable=True))
    op.create_check_constraint(
        "ck_admin_operation_logs_surface", "admin_operation_logs", "surface IN ('CHAT', 'ADMIN')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_admin_operation_logs_surface", "admin_operation_logs", type_="check")
    op.drop_column("admin_operation_logs", "user_agent")
    op.drop_column("admin_operation_logs", "ip_address")
    op.drop_column("admin_operation_logs", "surface")
    op.drop_column("access_logs", "user_agent")
    op.drop_column("access_logs", "ip_address")
