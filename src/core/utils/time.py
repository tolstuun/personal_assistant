"""Time utilities for consistent timezone handling."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """
    Get current UTC time as a timezone-aware datetime.

    This replaces the deprecated datetime.utcnow() with a timezone-aware
    alternative. All timestamps in the application should use this function
    to ensure consistency and avoid deprecation warnings.

    Returns:
        datetime: Current UTC time with timezone information.

    Example:
        >>> now = utcnow()
        >>> now.tzinfo is not None
        True
        >>> now.tzinfo == UTC
        True
    """
    return datetime.now(UTC)


def utcnow_naive() -> datetime:
    """
    Get current UTC time as a naive datetime (no timezone info).

    This function is intended for use as a default value in SQLAlchemy
    DateTime columns that don't have timezone=True. It provides the same
    behavior as the deprecated datetime.utcnow() but uses the modern
    datetime.now(UTC) internally.

    For all other uses, prefer utcnow() which returns timezone-aware datetimes.

    Returns:
        datetime: Current UTC time without timezone information.

    Example:
        >>> now = utcnow_naive()
        >>> now.tzinfo is None
        True
    """
    return datetime.now(UTC).replace(tzinfo=None)
