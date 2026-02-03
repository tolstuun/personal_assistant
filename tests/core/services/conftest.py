"""
Test fixtures for services tests.

Imports database fixtures from fetcher tests.
"""

# Import fixtures from fetcher tests - they are automatically available to pytest
from tests.core.primitives.fetchers.conftest import (
    clean_database,
    database,
    database_config,
)

__all__ = ["database_config", "database", "clean_database"]
