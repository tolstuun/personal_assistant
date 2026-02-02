"""
SQLAlchemy models for the Security Digest system.

These models store categories, sources, articles, and digest metadata
for the security news aggregation and digest generation workflow.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.storage.postgres import Base
from src.core.utils.time import utcnow_naive


class SourceType(enum.Enum):
    """Types of content sources."""

    WEBSITE = "website"
    TWITTER = "twitter"
    REDDIT = "reddit"


class DigestStatus(enum.Enum):
    """Workflow status for digest generation."""

    BUILDING = "building"
    READY = "ready"
    PUBLISHED = "published"


class Category(Base):
    """
    Content category that maps to a digest section.

    Categories group sources and define which section of the
    final digest their articles appear in.
    """

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    digest_section: Mapped[str] = mapped_column(String(50), nullable=False)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )

    # Relationships
    sources: Mapped[list["Source"]] = relationship(
        "Source", back_populates="category", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Category(name='{self.name}', section='{self.digest_section}')>"


class Source(Base):
    """
    Content source configuration.

    Defines where to fetch content from, how often to check,
    and what keywords to filter by.
    """

    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SourceType.WEBSITE
    )
    keywords: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    fetch_interval_minutes: Mapped[int] = mapped_column(
        Integer, default=60, nullable=False
    )
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="sources")
    articles: Mapped[list["Article"]] = relationship(
        "Article", back_populates="source", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_sources_enabled", "enabled"),
        Index("ix_sources_last_fetched_at", "last_fetched_at"),
    )

    def __repr__(self) -> str:
        return f"<Source(name='{self.name}', type='{self.source_type.value}')>"


class Digest(Base):
    """
    Digest record tracking generation and publishing workflow.

    Each digest represents a single day's aggregated content.
    """

    __tablename__ = "digests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    date: Mapped[datetime] = mapped_column(Date, unique=True, nullable=False)
    status: Mapped[DigestStatus] = mapped_column(
        Enum(DigestStatus, values_callable=lambda x: [e.value for e in x]),
        default=DigestStatus.BUILDING,
        nullable=False
    )
    html_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    articles: Mapped[list["Article"]] = relationship(
        "Article", back_populates="digest"
    )

    __table_args__ = (Index("ix_digests_status", "status"),)

    def __repr__(self) -> str:
        return f"<Digest(date='{self.date}', status='{self.status.value}')>"


class Article(Base):
    """
    Fetched article with AI-generated summary and relevance score.

    Articles are fetched from sources, processed by LLM for summarization,
    and optionally assigned to a digest for publication.
    """

    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    digest_section: Mapped[str | None] = mapped_column(String(50), nullable=True)
    relevance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, nullable=False
    )
    digest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("digests.id"), nullable=True
    )

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="articles")
    digest: Mapped["Digest | None"] = relationship("Digest", back_populates="articles")

    __table_args__ = (
        Index("ix_articles_fetched_at", "fetched_at"),
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_relevance_score", "relevance_score"),
        Index("ix_articles_digest_id", "digest_id"),
    )

    def __repr__(self) -> str:
        return f"<Article(title='{self.title[:50]}...', score={self.relevance_score})>"
