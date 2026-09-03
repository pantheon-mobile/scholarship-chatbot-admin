"""store chat content for user history

Revision ID: 0011_chat_content
Revises: 0010_operation_logs
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_chat_content"
down_revision = "0010_operation_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_interactions", sa.Column("question_text", sa.Text(), nullable=True))
    op.add_column("chat_interactions", sa.Column("answer_text", sa.Text(), nullable=True))
    op.add_column("chat_interactions", sa.Column("citations", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_interactions", "citations")
    op.drop_column("chat_interactions", "answer_text")
    op.drop_column("chat_interactions", "question_text")
