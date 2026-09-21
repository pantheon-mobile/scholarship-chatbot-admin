"""Store feedback reason and free text separately for restoration."""
from alembic import op
import sqlalchemy as sa
revision = "0019_feedback_details"
down_revision = "0018_faq_text_limits"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("chat_feedback", sa.Column("reason", sa.String(1000), nullable=True))
    op.add_column("chat_feedback", sa.Column("comment_text", sa.String(1000), nullable=True))

def downgrade():
    # The existing combined comment retains the text even after downgrade.
    op.drop_column("chat_feedback", "comment_text")
    op.drop_column("chat_feedback", "reason")
