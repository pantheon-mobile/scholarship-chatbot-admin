"""Expand category names to 30 characters without changing existing data."""
from alembic import op
import sqlalchemy as sa

revision = "0017_category_name_30"
down_revision = "0016_operation_name"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("categories", "name", existing_type=sa.String(15), type_=sa.String(30), existing_nullable=False)


def downgrade() -> None:
    # Refuse rollback if it would lose names accepted under the expanded limit.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM categories WHERE char_length(name) > 15) THEN
                RAISE EXCEPTION 'Cannot reduce category name limit: names longer than 15 characters exist';
            END IF;
        END $$;
    """)
    op.alter_column("categories", "name", existing_type=sa.String(30), type_=sa.String(15), existing_nullable=False)
