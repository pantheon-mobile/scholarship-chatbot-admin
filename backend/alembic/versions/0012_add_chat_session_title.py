"""add editable chat session title

Revision ID: 0012_chat_title
Revises: 0011_chat_content
"""

from alembic import op
import sqlalchemy as sa


revision = "0012_chat_title"
down_revision = "0011_chat_content"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chat_sessions", sa.Column("title", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_sessions", "title")
