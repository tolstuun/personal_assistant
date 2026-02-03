"""
SQLAlchemy model for application settings.

Stores key-value configuration that can be managed through the admin UI.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.core.storage.postgres import Base
from src.core.utils.time import utcnow_naive


class Setting(Base):
    """
    Application setting stored as key-value pair.

    Settings are stored with JSON values to support various types:
    - Integers (fetch_interval_minutes)
    - Strings (digest_time)
    - Booleans (telegram_notifications)
    - Arrays (digest_sections)
    """

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow_naive, onupdate=utcnow_naive, nullable=False
    )

    def __repr__(self) -> str:
        return f"<Setting(key='{self.key}', value={self.value})>"
