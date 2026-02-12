"""Add full-text search (tsvector) on items for SEARCH_BACKEND=fts.

Revision ID: 004
Revises: 003
Create Date: 2025-02-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE items
        ADD COLUMN IF NOT EXISTS search_tsv tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('english', coalesce(title, '')), 'A')
            || setweight(to_tsvector('english', coalesce(summary, '')), 'B')
            || setweight(to_tsvector('english', coalesce(payload::text, '')), 'C')
        ) STORED
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_items_search_tsv ON items USING GIN (search_tsv)")
    # Backfill existing rows (GENERATED ALWAYS AS ... STORED does it automatically in PG12+)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_items_search_tsv")
    op.execute("ALTER TABLE items DROP COLUMN IF EXISTS search_tsv")
