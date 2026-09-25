"""Keep user-deleted chats for administrators and persist admission timestamps."""
from alembic import op
import sqlalchemy as sa
revision = "0020_user_deleted_and_limits"
down_revision = "0019_feedback_details"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("chat_sessions", sa.Column("user_deleted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table("chat_request_limits",
        sa.Column("visitor_key", sa.String(64), primary_key=True),
        sa.Column("accepted_at", sa.JSON(), nullable=False))

def downgrade():
    # Retained conversations remain present when reverting the schema.
    op.drop_table("chat_request_limits")
    op.drop_column("chat_sessions", "user_deleted")
