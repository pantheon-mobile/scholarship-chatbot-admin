"""create FAQ classification tables for CB-212

Revision ID: 0005_faq_classifications
Revises: 0004_category_link
Create Date: 2026-08-19 00:00:00.000000
"""

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "0005_faq_classifications"
down_revision = "0004_category_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "faq_classification_types",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("type_code", sa.String(), nullable=False, unique=True),
        sa.Column("fixed_name", sa.String(), nullable=False),
        sa.Column("display_label", sa.String(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("display_label = btrim(display_label) AND display_label <> ''", name="ck_faq_classification_types_label_trimmed"),
        sa.CheckConstraint("display_order BETWEEN 1 AND 4", name="ck_faq_classification_types_order"),
    )
    op.create_table(
        "faq_classification_values",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("classification_type_id", sa.BigInteger(), nullable=False),
        sa.Column("value_name", sa.String(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["classification_type_id"],
            ["faq_classification_types.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("classification_type_id", "value_name", name="uq_faq_classification_value_name"),
        sa.CheckConstraint("value_name = btrim(value_name) AND value_name <> ''", name="ck_faq_classification_values_name_trimmed"),
        sa.CheckConstraint("display_order >= 1", name="ck_faq_classification_values_order_positive"),
    )
    op.create_index("ix_faq_classification_values_type_id", "faq_classification_values", ["classification_type_id"])

    now = datetime.now(timezone.utc)
    type_table = sa.table(
        "faq_classification_types",
        sa.column("type_code", sa.String()),
        sa.column("fixed_name", sa.String()),
        sa.column("display_label", sa.String()),
        sa.column("display_order", sa.Integer()),
        sa.column("version", sa.Integer()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(type_table, [
        {
            "type_code": f"FAQ_TYPE_{order}",
            "fixed_name": f"区分{order}",
            "display_label": f"区分{order}",
            "display_order": order,
            "version": 1,
            "created_at": now,
            "updated_at": now,
        }
        for order in range(1, 5)
    ])


def downgrade() -> None:
    op.drop_index("ix_faq_classification_values_type_id", table_name="faq_classification_values")
    op.drop_table("faq_classification_values")
    op.drop_table("faq_classification_types")
