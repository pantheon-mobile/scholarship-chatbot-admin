"""create categories table for CB-213

Revision ID: 0003_cb213
Revises: 0002_cb202
Create Date: 2026-08-18 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_cb213"
down_revision = "0002_cb202"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=15), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["categories.id"], ondelete="CASCADE"),
        sa.CheckConstraint("name = btrim(name) AND name <> ''", name="ck_categories_name_trimmed"),
        sa.CheckConstraint("parent_id IS NULL OR parent_id <> id", name="ck_categories_not_self_parent"),
        sa.CheckConstraint("display_order >= 1", name="ck_categories_display_order_positive"),
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])
    op.create_index(
        "uq_categories_parent_name",
        "categories",
        ["parent_id", "name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NOT NULL"),
    )
    op.create_index(
        "uq_categories_root_name",
        "categories",
        ["name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_categories_root_name", table_name="categories")
    op.drop_index("uq_categories_parent_name", table_name="categories")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_table("categories")
