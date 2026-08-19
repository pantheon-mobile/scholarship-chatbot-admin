"""link data sources to categories

Revision ID: 0004_category_link
Revises: 0003_cb213
Create Date: 2026-08-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_category_link"
down_revision = "0003_cb213"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("data_sources", sa.Column("category_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        "fk_data_sources_category_id_categories",
        "data_sources",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_data_sources_category_id", "data_sources", ["category_id"])


def downgrade() -> None:
    op.drop_index("ix_data_sources_category_id", table_name="data_sources")
    op.drop_constraint("fk_data_sources_category_id_categories", "data_sources", type_="foreignkey")
    op.drop_column("data_sources", "category_id")
