"""
Settings service for managing application configuration.

Provides a high-level interface for reading and writing settings
with default value fallbacks.
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.core.models import Setting
from src.core.storage.postgres import get_db
from src.core.utils.time import utcnow_naive

logger = logging.getLogger(__name__)


class SettingsService:
    """
    Service for managing application settings.

    Provides methods to get, set, and reset settings with default
    value support. Settings are stored in the database but fall
    back to defaults when not set.
    """

    # Valid values for constrained settings
    VALID_PROVIDERS = ["anthropic", "openai", "google", "ollama"]
    VALID_TIERS = ["fast", "smart", "smartest"]

    # Default values for all settings
    DEFAULTS: dict[str, Any] = {
        "fetch_interval_minutes": 60,
        "fetch_worker_count": 3,
        "digest_time": "08:00",
        "telegram_notifications": True,
        "digest_sections": ["security_news", "product_news", "market"],
        "summarizer_provider": "ollama",
        "summarizer_tier": "fast",
    }

    # Setting descriptions for UI
    DESCRIPTIONS: dict[str, str] = {
        "fetch_interval_minutes": "How often to fetch new content (in minutes)",
        "fetch_worker_count": "Number of parallel fetch workers to run",
        "digest_time": "When to generate the daily digest (24-hour format)",
        "telegram_notifications": "Send notifications via Telegram",
        "digest_sections": "Which sections to include in the digest",
        "summarizer_provider": "LLM provider for summarization (anthropic, openai, google, ollama)",
        "summarizer_tier": "LLM model tier for summarization (fast, smart, smartest)",
    }

    # Setting types for UI rendering
    TYPES: dict[str, str] = {
        "fetch_interval_minutes": "number",
        "fetch_worker_count": "number",
        "digest_time": "time",
        "telegram_notifications": "boolean",
        "digest_sections": "multiselect",
        "summarizer_provider": "text",
        "summarizer_tier": "text",
    }

    # Available options for multiselect settings
    OPTIONS: dict[str, list[str]] = {
        "digest_sections": ["security_news", "product_news", "market", "research"],
    }

    async def get(self, key: str) -> Any:
        """
        Get a setting value by key.

        Args:
            key: The setting key.

        Returns:
            The setting value, or the default if not set.

        Raises:
            KeyError: If the key is not a valid setting.
        """
        if key not in self.DEFAULTS:
            raise KeyError(f"Unknown setting: {key}")

        db = await get_db()
        async with db.session() as session:
            stmt = select(Setting).where(Setting.key == key)
            result = await session.execute(stmt)
            setting = result.scalar_one_or_none()

            if setting is not None:
                # Value is stored as {"value": actual_value} in JSONB
                return setting.value.get("value", self.DEFAULTS[key])

            return self.DEFAULTS[key]

    async def set(self, key: str, value: Any) -> None:
        """
        Set a setting value.

        Uses upsert to create or update the setting.

        Args:
            key: The setting key.
            value: The value to set.

        Raises:
            KeyError: If the key is not a valid setting.
            ValueError: If the value type is invalid.
        """
        if key not in self.DEFAULTS:
            raise KeyError(f"Unknown setting: {key}")

        # Validate value type
        self._validate_value(key, value)

        db = await get_db()
        async with db.session() as session:
            # Use upsert (INSERT ... ON CONFLICT DO UPDATE)
            stmt = (
                pg_insert(Setting)
                .values(
                    key=key,
                    value={"value": value},
                    updated_at=utcnow_naive(),
                )
                .on_conflict_do_update(
                    index_elements=["key"],
                    set_={
                        "value": {"value": value},
                        "updated_at": utcnow_naive(),
                    },
                )
            )
            await session.execute(stmt)
            await session.commit()

        logger.info(f"Setting '{key}' updated to: {value}")

    async def get_all(self) -> dict[str, dict[str, Any]]:
        """
        Get all settings with their metadata.

        Returns:
            Dict mapping setting keys to their info:
            {
                "key": {
                    "value": current_value,
                    "default": default_value,
                    "description": description,
                    "type": setting_type,
                    "options": options_if_multiselect,
                    "is_default": bool,
                }
            }
        """
        db = await get_db()
        async with db.session() as session:
            stmt = select(Setting)
            result = await session.execute(stmt)
            db_settings = {s.key: s.value.get("value") for s in result.scalars().all()}

        settings = {}
        for key, default in self.DEFAULTS.items():
            current_value = db_settings.get(key, default)
            settings[key] = {
                "value": current_value,
                "default": default,
                "description": self.DESCRIPTIONS.get(key, ""),
                "type": self.TYPES.get(key, "text"),
                "options": self.OPTIONS.get(key, []),
                "is_default": key not in db_settings,
            }

        return settings

    async def reset(self, key: str) -> None:
        """
        Reset a setting to its default value.

        Removes the setting from the database so the default is used.

        Args:
            key: The setting key.

        Raises:
            KeyError: If the key is not a valid setting.
        """
        if key not in self.DEFAULTS:
            raise KeyError(f"Unknown setting: {key}")

        db = await get_db()
        async with db.session() as session:
            stmt = select(Setting).where(Setting.key == key)
            result = await session.execute(stmt)
            setting = result.scalar_one_or_none()

            if setting is not None:
                await session.delete(setting)
                await session.commit()
                logger.info(f"Setting '{key}' reset to default")

    def _validate_value(self, key: str, value: Any) -> None:
        """
        Validate a setting value.

        Args:
            key: The setting key.
            value: The value to validate.

        Raises:
            ValueError: If the value is invalid.
        """
        setting_type = self.TYPES.get(key, "text")

        if setting_type == "number":
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"{key} must be a positive integer")

        elif setting_type == "time":
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string in HH:MM format")
            # Validate HH:MM format strictly (must be 5 chars: XX:XX)
            if len(value) != 5 or value[2] != ":":
                raise ValueError(f"{key} must be in HH:MM format (00:00-23:59)")
            try:
                hours, minutes = value.split(":")
                if len(hours) != 2 or len(minutes) != 2:
                    raise ValueError()
                h, m = int(hours), int(minutes)
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError()
            except (ValueError, AttributeError):
                raise ValueError(f"{key} must be in HH:MM format (00:00-23:59)")

        elif setting_type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be a boolean")

        elif setting_type == "multiselect":
            if not isinstance(value, list):
                raise ValueError(f"{key} must be a list")
            valid_options = self.OPTIONS.get(key, [])
            for item in value:
                if item not in valid_options:
                    raise ValueError(f"Invalid option for {key}: {item}")

        elif setting_type == "text":
            if not isinstance(value, str):
                raise ValueError(f"{key} must be a string")
            # Validate constrained text settings
            if key == "summarizer_provider":
                if value not in self.VALID_PROVIDERS:
                    raise ValueError(
                        f"Invalid provider '{value}'. "
                        f"Must be one of: {', '.join(self.VALID_PROVIDERS)}"
                    )
            elif key == "summarizer_tier":
                if value not in self.VALID_TIERS:
                    raise ValueError(
                        f"Invalid tier '{value}'. "
                        f"Must be one of: {', '.join(self.VALID_TIERS)}"
                    )


# Singleton instance for convenience
_settings_service: SettingsService | None = None


async def get_settings_service() -> SettingsService:
    """Get the global settings service instance."""
    global _settings_service
    if _settings_service is None:
        _settings_service = SettingsService()
    return _settings_service
