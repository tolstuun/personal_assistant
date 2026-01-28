"""Create security digest tables.

Revision ID: 001
Revises: None
Create Date: 2026-01-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create categories, sources, digests, and articles tables."""
    # Create enum types
    op.execute("CREATE TYPE sourcetype AS ENUM ('website', 'twitter', 'reddit')")
    op.execute("CREATE TYPE digeststatus AS ENUM ('building', 'ready', 'published')")

    # Create categories table
    op.create_table(
        "categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("digest_section", sa.String(length=50), nullable=False),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create sources table
    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column(
            "source_type",
            postgresql.ENUM("website", "twitter", "reddit", name="sourcetype", create_type=False),
            nullable=False,
        ),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("fetch_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sources_enabled", "sources", ["enabled"])
    op.create_index("ix_sources_last_fetched_at", "sources", ["last_fetched_at"])

    # Create digests table
    op.create_table(
        "digests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "building", "ready", "published", name="digeststatus", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("html_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("notified_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date"),
    )
    op.create_index("ix_digests_status", "digests", ["status"])

    # Create articles table
    op.create_table(
        "articles",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("digest_section", sa.String(length=50), nullable=True),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("digest_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["digest_id"], ["digests.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_index("ix_articles_digest_id", "articles", ["digest_id"])
    op.create_index("ix_articles_fetched_at", "articles", ["fetched_at"])
    op.create_index("ix_articles_relevance_score", "articles", ["relevance_score"])


def downgrade() -> None:
    """Drop all security digest tables."""
    op.drop_index("ix_articles_relevance_score", table_name="articles")
    op.drop_index("ix_articles_fetched_at", table_name="articles")
    op.drop_index("ix_articles_digest_id", table_name="articles")
    op.drop_table("articles")

    op.drop_index("ix_digests_status", table_name="digests")
    op.drop_table("digests")

    op.drop_index("ix_sources_last_fetched_at", table_name="sources")
    op.drop_index("ix_sources_enabled", table_name="sources")
    op.drop_table("sources")

    op.drop_table("categories")

    op.execute("DROP TYPE digeststatus")
    op.execute("DROP TYPE sourcetype")
