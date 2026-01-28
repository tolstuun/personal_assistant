"""
Storage exceptions.

All storage components raise these exceptions for consistent error handling.
"""


class StorageError(Exception):
    """Base exception for all storage errors."""

    pass


class ConnectionError(StorageError):
    """Cannot connect to storage service."""

    pass


class NotFoundError(StorageError):
    """Requested item does not exist."""

    pass


class DuplicateError(StorageError):
    """Item already exists (unique constraint violation)."""

    pass


class ConfigurationError(StorageError):
    """Invalid storage configuration."""

    pass
