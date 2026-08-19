"""create analytics tables for CB-201

Revision ID: 0007_analytics
Revises: 0006_faqs
Create Date: 2026-08-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_analytics"
down_revision = "0006_faqs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analytics_visitors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("visitor_key", sa.String(length=64), nullable=False),
        sa.Column("identity_kind", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("visitor_key", name="uq_analytics_visitors_visitor_key"),
        sa.CheckConstraint(
            "identity_kind IN ('AUTHENTICATED', 'ANONYMOUS')",
            name="ck_analytics_visitors_identity_kind",
        ),
    )
    op.create_table(
        "access_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("visitor_id", sa.Uuid(), nullable=False),
        sa.Column("accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["visitor_id"], ["analytics_visitors.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_access_logs_accessed_at", "access_logs", ["accessed_at"])
    op.create_index("ix_access_logs_visitor_accessed_at", "access_logs", ["visitor_id", "accessed_at"])

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("visitor_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["visitor_id"], ["analytics_visitors.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("ended_at IS NULL OR ended_at >= started_at", name="ck_chat_sessions_end_after_start"),
    )
    op.create_index("ix_chat_sessions_started_at", "chat_sessions", ["started_at"])
    op.create_index("ix_chat_sessions_visitor_started_at", "chat_sessions", ["visitor_id", "started_at"])

    op.create_table(
        "chat_interactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("chat_session_id", sa.Uuid(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("question_submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answer_displayed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_status", sa.String(length=20), nullable=False),
        sa.Column("answer_type", sa.String(length=20), nullable=True),
        sa.Column("faq_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chat_session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["faq_id"], ["faqs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("chat_session_id", "sequence_number", name="uq_chat_interactions_session_sequence"),
        sa.CheckConstraint("sequence_number >= 1", name="ck_chat_interactions_sequence_positive"),
        sa.CheckConstraint(
            "processing_status IN ('PROCESSING', 'COMPLETED', 'FAILED')",
            name="ck_chat_interactions_processing_status",
        ),
        sa.CheckConstraint(
            "answer_type IS NULL OR answer_type IN ('FAQ', 'GENERATED_AI', 'NO_ANSWER')",
            name="ck_chat_interactions_answer_type",
        ),
        sa.CheckConstraint(
            "(processing_status = 'COMPLETED' AND answer_type IS NOT NULL AND answer_displayed_at IS NOT NULL) "
            "OR (processing_status IN ('PROCESSING', 'FAILED') AND answer_type IS NULL AND answer_displayed_at IS NULL)",
            name="ck_chat_interactions_completion_state",
        ),
        sa.CheckConstraint(
            "answer_type = 'FAQ' OR faq_id IS NULL",
            name="ck_chat_interactions_faq_only_for_faq_answer",
        ),
        sa.CheckConstraint(
            "answer_displayed_at IS NULL OR answer_displayed_at >= question_submitted_at",
            name="ck_chat_interactions_answer_after_question",
        ),
    )
    op.create_index("ix_chat_interactions_question_submitted_at", "chat_interactions", ["question_submitted_at"])
    op.create_index(
        "ix_chat_interactions_answer_type_question_submitted_at",
        "chat_interactions",
        ["answer_type", "question_submitted_at"],
    )

    op.create_table(
        "chat_feedback",
        sa.Column("interaction_id", sa.Uuid(), primary_key=True),
        sa.Column("rating", sa.String(length=10), nullable=False),
        sa.Column("comment", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["interaction_id"], ["chat_interactions.id"], ondelete="CASCADE"),
        sa.CheckConstraint("rating IN ('GOOD', 'BAD')", name="ck_chat_feedback_rating"),
    )


def downgrade() -> None:
    op.drop_table("chat_feedback")
    op.drop_index("ix_chat_interactions_answer_type_question_submitted_at", table_name="chat_interactions")
    op.drop_index("ix_chat_interactions_question_submitted_at", table_name="chat_interactions")
    op.drop_table("chat_interactions")
    op.drop_index("ix_chat_sessions_visitor_started_at", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_started_at", table_name="chat_sessions")
    op.drop_table("chat_sessions")
    op.drop_index("ix_access_logs_visitor_accessed_at", table_name="access_logs")
    op.drop_index("ix_access_logs_accessed_at", table_name="access_logs")
    op.drop_table("access_logs")
    op.drop_table("analytics_visitors")
