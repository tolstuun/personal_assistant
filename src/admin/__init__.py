"""
Admin Web UI for managing Security Digest sources.

Provides a simple HTMX-based interface for CRUD operations
on categories and sources.
"""

from src.admin.app import create_admin_app

__all__ = ["create_admin_app"]
