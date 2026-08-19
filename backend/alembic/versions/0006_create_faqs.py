"""create FAQ tables for CB-208

Revision ID: 0006_faqs
Revises: 0005_faq_classifications
Create Date: 2026-08-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_faqs"
down_revision = "0005_faq_classifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "faqs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("question", sa.String(length=500), nullable=False),
        sa.Column("answer", sa.String(length=1000), nullable=False),
        sa.Column("chat_enabled", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_faqs_updated_at", "faqs", ["updated_at"])
    op.create_index("ix_faqs_chat_enabled", "faqs", ["chat_enabled"])
    op.create_table(
        "faq_similar_questions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("faq_id", sa.BigInteger(), nullable=False),
        sa.Column("question", sa.String(length=500), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["faq_id"], ["faqs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("faq_id", "display_order", name="uq_faq_similar_question_order"),
        sa.CheckConstraint("display_order >= 1", name="ck_faq_similar_question_order_positive"),
    )
    op.create_index("ix_faq_similar_questions_faq_id", "faq_similar_questions", ["faq_id"])
    op.create_table(
        "faq_classification_assignments",
        sa.Column("faq_id", sa.BigInteger(), nullable=False),
        sa.Column("classification_type_id", sa.BigInteger(), nullable=False),
        sa.Column("classification_value_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["faq_id"], ["faqs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["classification_type_id"], ["faq_classification_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["classification_value_id"], ["faq_classification_values.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("faq_id", "classification_type_id"),
    )
    op.create_index("ix_faq_classification_assignments_value_id", "faq_classification_assignments", ["classification_value_id"])


def downgrade() -> None:
    op.drop_index("ix_faq_classification_assignments_value_id", table_name="faq_classification_assignments")
    op.drop_table("faq_classification_assignments")
    op.drop_index("ix_faq_similar_questions_faq_id", table_name="faq_similar_questions")
    op.drop_table("faq_similar_questions")
    op.drop_index("ix_faqs_chat_enabled", table_name="faqs")
    op.drop_index("ix_faqs_updated_at", table_name="faqs")
    op.drop_table("faqs")
