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
