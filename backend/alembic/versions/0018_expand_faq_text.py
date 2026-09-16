"""Expand FAQ questions to 1500 and answers to 4000 characters."""
from alembic import op
import sqlalchemy as sa

revision = "0018_faq_text_limits"
down_revision = "0017_category_name_30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("faqs", "question", existing_type=sa.String(500), type_=sa.String(1500), existing_nullable=False)
    op.alter_column("faqs", "answer", existing_type=sa.String(1000), type_=sa.String(4000), existing_nullable=False)
    op.alter_column("faq_similar_questions", "question", existing_type=sa.String(500), type_=sa.String(1500), existing_nullable=False)


def downgrade() -> None:
    # Do not truncate customer data when rolling back the length expansion.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM faqs WHERE char_length(question) > 500 OR char_length(answer) > 1000)
               OR EXISTS (SELECT 1 FROM faq_similar_questions WHERE char_length(question) > 500) THEN
                RAISE EXCEPTION 'Cannot reduce FAQ limits: longer texts exist';
            END IF;
        END $$;
    """)
    op.alter_column("faq_similar_questions", "question", existing_type=sa.String(1500), type_=sa.String(500), existing_nullable=False)
    op.alter_column("faqs", "answer", existing_type=sa.String(4000), type_=sa.String(1000), existing_nullable=False)
    op.alter_column("faqs", "question", existing_type=sa.String(1500), type_=sa.String(500), existing_nullable=False)
