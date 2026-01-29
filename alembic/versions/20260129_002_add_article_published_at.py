"""Add published_at column to articles table.

Revision ID: 002
Revises: 001
Create Date: 2026-01-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add published_at column and index to articles table."""
    op.add_column(
        "articles",
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_articles_published_at",
        "articles",
        ["published_at"],
    )


def downgrade() -> None:
    """Remove published_at column and index from articles table."""
    op.drop_index("ix_articles_published_at", table_name="articles")
    op.drop_column("articles", "published_at")
