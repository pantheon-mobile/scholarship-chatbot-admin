"""add analytics visitor profile

Revision ID: 0013_visitor_profile
Revises: 0012_chat_title
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_visitor_profile"
down_revision = "0012_chat_title"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analytics_visitors", sa.Column("subject", sa.String(length=500), nullable=True))
    op.add_column("analytics_visitors", sa.Column("display_name", sa.String(length=500), nullable=True))
    op.add_column("analytics_visitors", sa.Column("role", sa.String(length=20), nullable=True))
    op.add_column("analytics_visitors", sa.Column("site", sa.String(length=20), nullable=True))
    op.add_column("admin_operation_logs", sa.Column("operator_subject", sa.String(length=500), nullable=True))
    op.add_column("admin_operation_logs", sa.Column("operator_display_name", sa.String(length=500), nullable=True))
    op.add_column("admin_operation_logs", sa.Column("operator_site", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_operation_logs", "operator_site")
    op.drop_column("admin_operation_logs", "operator_display_name")
    op.drop_column("admin_operation_logs", "operator_subject")
    op.drop_column("analytics_visitors", "site")
    op.drop_column("analytics_visitors", "role")
    op.drop_column("analytics_visitors", "display_name")
    op.drop_column("analytics_visitors", "subject")
