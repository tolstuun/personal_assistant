"""
Tests for Security Digest models.

Unit tests verify model structure and relationships without database.
Integration tests (marked with pytest.mark.integration) require PostgreSQL.
"""

import uuid
from datetime import date

from sqlalchemy import inspect

from src.core.models.security_digest import (
    Article,
    Category,
    Digest,
    DigestStatus,
    Source,
    SourceType,
)
from src.core.storage.postgres import Base


class TestEnums:
    """Tests for enum types."""

    def test_source_type_values(self) -> None:
        """SourceType enum has expected values."""
        assert SourceType.WEBSITE.value == "website"
        assert SourceType.TWITTER.value == "twitter"
        assert SourceType.REDDIT.value == "reddit"

    def test_digest_status_values(self) -> None:
        """DigestStatus enum has expected values."""
        assert DigestStatus.BUILDING.value == "building"
        assert DigestStatus.READY.value == "ready"
        assert DigestStatus.PUBLISHED.value == "published"


class TestCategoryModel:
    """Tests for Category model."""

    def test_category_table_name(self) -> None:
        """Category model has correct table name."""
        assert Category.__tablename__ == "categories"

    def test_category_columns(self) -> None:
        """Category model has expected columns."""
        mapper = inspect(Category)
        column_names = [c.key for c in mapper.columns]

        assert "id" in column_names
        assert "name" in column_names
        assert "digest_section" in column_names
        assert "keywords" in column_names
        assert "created_at" in column_names

    def test_category_inherits_from_base(self) -> None:
        """Category inherits from SQLAlchemy Base."""
        assert issubclass(Category, Base)

    def test_category_instantiation(self) -> None:
        """Category can be instantiated with required fields."""
        category = Category(
            name="CVE Alerts",
            digest_section="security_news",
            keywords=["CVE", "vulnerability"],
        )

        assert category.name == "CVE Alerts"
        assert category.digest_section == "security_news"
        assert category.keywords == ["CVE", "vulnerability"]

    def test_category_repr(self) -> None:
        """Category __repr__ returns readable string."""
        category = Category(name="Test", digest_section="security_news")
        repr_str = repr(category)

        assert "Category" in repr_str
        assert "Test" in repr_str
        assert "security_news" in repr_str


class TestSourceModel:
    """Tests for Source model."""

    def test_source_table_name(self) -> None:
        """Source model has correct table name."""
        assert Source.__tablename__ == "sources"

    def test_source_columns(self) -> None:
        """Source model has expected columns."""
        mapper = inspect(Source)
        column_names = [c.key for c in mapper.columns]

        expected = [
            "id",
            "category_id",
            "name",
            "url",
            "source_type",
            "keywords",
            "enabled",
            "fetch_interval_minutes",
            "last_fetched_at",
            "created_at",
        ]
        for col in expected:
            assert col in column_names, f"Missing column: {col}"

    def test_source_column_defaults(self) -> None:
        """Source columns have correct default values defined."""
        # Check defaults are defined at the column level (applied on INSERT)
        enabled_col = Source.__table__.c.enabled
        fetch_interval_col = Source.__table__.c.fetch_interval_minutes
        source_type_col = Source.__table__.c.source_type

        assert enabled_col.default.arg is True
        assert fetch_interval_col.default.arg == 60
        assert source_type_col.default.arg == SourceType.WEBSITE

    def test_source_repr(self) -> None:
        """Source __repr__ returns readable string."""
        source = Source(
            category_id=uuid.uuid4(),
            name="Test Source",
            url="https://example.com",
            source_type=SourceType.TWITTER,
        )
        repr_str = repr(source)

        assert "Source" in repr_str
        assert "Test Source" in repr_str
        assert "twitter" in repr_str


class TestDigestModel:
    """Tests for Digest model."""

    def test_digest_table_name(self) -> None:
        """Digest model has correct table name."""
        assert Digest.__tablename__ == "digests"

    def test_digest_columns(self) -> None:
        """Digest model has expected columns."""
        mapper = inspect(Digest)
        column_names = [c.key for c in mapper.columns]

        expected = [
            "id",
            "date",
            "status",
            "html_path",
            "created_at",
            "published_at",
            "notified_at",
        ]
        for col in expected:
            assert col in column_names, f"Missing column: {col}"

    def test_digest_status_default(self) -> None:
        """Digest status column has BUILDING as default."""
        status_col = Digest.__table__.c.status
        assert status_col.default.arg == DigestStatus.BUILDING

    def test_digest_repr(self) -> None:
        """Digest __repr__ returns readable string."""
        digest = Digest(date=date(2026, 1, 28), status=DigestStatus.READY)
        repr_str = repr(digest)

        assert "Digest" in repr_str
        assert "2026-01-28" in repr_str
        assert "ready" in repr_str


class TestArticleModel:
    """Tests for Article model."""

    def test_article_table_name(self) -> None:
        """Article model has correct table name."""
        assert Article.__tablename__ == "articles"

    def test_article_columns(self) -> None:
        """Article model has expected columns."""
        mapper = inspect(Article)
        column_names = [c.key for c in mapper.columns]

        expected = [
            "id",
            "source_id",
            "url",
            "title",
            "raw_content",
            "summary",
            "digest_section",
            "relevance_score",
            "fetched_at",
            "digest_id",
        ]
        for col in expected:
            assert col in column_names, f"Missing column: {col}"

    def test_article_instantiation(self) -> None:
        """Article can be instantiated with required fields."""
        article = Article(
            source_id=uuid.uuid4(),
            url="https://example.com/article",
            title="Test Article",
            raw_content="Article content here",
            summary="Brief summary",
            relevance_score=0.85,
        )

        assert article.title == "Test Article"
        assert article.relevance_score == 0.85

    def test_article_repr(self) -> None:
        """Article __repr__ returns readable string with truncated title."""
        article = Article(
            source_id=uuid.uuid4(),
            url="https://example.com/article",
            title="A" * 100,  # Long title
            relevance_score=0.75,
        )
        repr_str = repr(article)

        assert "Article" in repr_str
        assert "0.75" in repr_str
        # Title should be truncated to 50 chars
        assert "..." in repr_str


class TestRelationships:
    """Tests for model relationships."""

    def test_category_has_sources_relationship(self) -> None:
        """Category has sources relationship defined."""
        mapper = inspect(Category)
        relationships = [r.key for r in mapper.relationships]

        assert "sources" in relationships

    def test_source_has_category_relationship(self) -> None:
        """Source has category relationship defined."""
        mapper = inspect(Source)
        relationships = [r.key for r in mapper.relationships]

        assert "category" in relationships
        assert "articles" in relationships

    def test_source_has_articles_relationship(self) -> None:
        """Source has articles relationship defined."""
        mapper = inspect(Source)
        relationships = [r.key for r in mapper.relationships]

        assert "articles" in relationships

    def test_article_has_source_relationship(self) -> None:
        """Article has source relationship defined."""
        mapper = inspect(Article)
        relationships = [r.key for r in mapper.relationships]

        assert "source" in relationships
        assert "digest" in relationships

    def test_digest_has_articles_relationship(self) -> None:
        """Digest has articles relationship defined."""
        mapper = inspect(Digest)
        relationships = [r.key for r in mapper.relationships]

        assert "articles" in relationships


class TestIndexes:
    """Tests for model indexes."""

    def test_source_indexes(self) -> None:
        """Source model has expected indexes."""
        indexes = {idx.name for idx in Source.__table__.indexes}

        assert "ix_sources_enabled" in indexes
        assert "ix_sources_last_fetched_at" in indexes

    def test_article_indexes(self) -> None:
        """Article model has expected indexes."""
        indexes = {idx.name for idx in Article.__table__.indexes}

        assert "ix_articles_fetched_at" in indexes
        assert "ix_articles_relevance_score" in indexes
        assert "ix_articles_digest_id" in indexes

    def test_digest_indexes(self) -> None:
        """Digest model has expected indexes."""
        indexes = {idx.name for idx in Digest.__table__.indexes}

        assert "ix_digests_status" in indexes


class TestConstraints:
    """Tests for model constraints."""

    def test_article_url_unique(self) -> None:
        """Article URL has unique constraint."""
        url_column = Article.__table__.c.url
        # Check if there's a unique constraint on the URL column
        assert url_column.unique is True

    def test_digest_date_unique(self) -> None:
        """Digest date has unique constraint."""
        date_column = Digest.__table__.c.date
        assert date_column.unique is True
