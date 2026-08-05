"""create classification tables

Revision ID: 0001_cb207
Revises: 
Create Date: 2026-08-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = "0001_cb207"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "classification_types",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("type_code", sa.String(length=20), unique=True, nullable=False),
        sa.Column("fixed_name", sa.String(length=50), nullable=False),
        sa.Column("display_label", sa.String(length=100), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "classification_values",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("classification_type_id", sa.BigInteger(), sa.ForeignKey("classification_types.id"), nullable=False),
        sa.Column("value_name", sa.String(length=200), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("classification_type_id", "value_name", name="uq_classification_value_name"),
    )

    now = datetime.now(timezone.utc)
    op.bulk_insert(
        sa.table(
            "classification_types",
            sa.column("type_code", sa.String),
            sa.column("fixed_name", sa.String),
            sa.column("display_label", sa.String),
            sa.column("display_order", sa.Integer),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
            sa.column("version", sa.Integer),
        ),
        [
            {"type_code": "TYPE_1", "fixed_name": "種別1", "display_label": "種別1", "display_order": 1, "created_at": now, "updated_at": now, "version": 1},
            {"type_code": "TYPE_2", "fixed_name": "種別2", "display_label": "種別2", "display_order": 2, "created_at": now, "updated_at": now, "version": 1},
            {"type_code": "TYPE_3", "fixed_name": "種別3", "display_label": "種別3", "display_order": 3, "created_at": now, "updated_at": now, "version": 1},
        ],
    )

    op.bulk_insert(
        sa.table(
            "classification_values",
            sa.column("classification_type_id", sa.BigInteger),
            sa.column("value_name", sa.String),
            sa.column("display_order", sa.Integer),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
            sa.column("version", sa.Integer),
        ),
        [
            {"classification_type_id": 1, "value_name": "在学生", "display_order": 1, "created_at": now, "updated_at": now, "version": 1},
            {"classification_type_id": 1, "value_name": "新入生", "display_order": 2, "created_at": now, "updated_at": now, "version": 1},
            {"classification_type_id": 1, "value_name": "留学生", "display_order": 3, "created_at": now, "updated_at": now, "version": 1},
            {"classification_type_id": 1, "value_name": "その他", "display_order": 4, "created_at": now, "updated_at": now, "version": 1},
            {"classification_type_id": 2, "value_name": "給付", "display_order": 1, "created_at": now, "updated_at": now, "version": 1},
            {"classification_type_id": 2, "value_name": "貸与", "display_order": 2, "created_at": now, "updated_at": now, "version": 1},
            {"classification_type_id": 2, "value_name": "学内", "display_order": 3, "created_at": now, "updated_at": now, "version": 1},
            {"classification_type_id": 2, "value_name": "学外", "display_order": 4, "created_at": now, "updated_at": now, "version": 1},
            {"classification_type_id": 3, "value_name": "学部", "display_order": 1, "created_at": now, "updated_at": now, "version": 1},
            {"classification_type_id": 3, "value_name": "大学院", "display_order": 2, "created_at": now, "updated_at": now, "version": 1},
            {"classification_type_id": 3, "value_name": "その他", "display_order": 3, "created_at": now, "updated_at": now, "version": 1},
        ],
    )


def downgrade() -> None:
    op.drop_table("classification_values")
    op.drop_table("classification_types")
