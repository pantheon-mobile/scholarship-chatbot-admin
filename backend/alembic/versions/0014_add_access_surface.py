"""add access surface

Revision ID: 0014_access_surface
Revises: 0013_visitor_profile
"""
from alembic import op
import sqlalchemy as sa


revision = "0014_access_surface"
down_revision = "0013_visitor_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "access_logs",
        sa.Column("surface", sa.String(length=20), nullable=False, server_default="CHAT"),
    )
    op.create_check_constraint(
        "ck_access_logs_surface", "access_logs", "surface IN ('CHAT', 'ADMIN')"
    )
    op.create_index("ix_access_logs_surface_accessed_at", "access_logs", ["surface", "accessed_at"])


def downgrade() -> None:
    op.drop_index("ix_access_logs_surface_accessed_at", table_name="access_logs")
    op.drop_constraint("ck_access_logs_surface", "access_logs", type_="check")
    op.drop_column("access_logs", "surface")
