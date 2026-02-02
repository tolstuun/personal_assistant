"""
Tests for SettingsService.

Integration tests that use a real PostgreSQL database.
"""

import pytest

from src.core.services.settings import SettingsService


class TestSettingsServiceDefaults:
    """Tests for SettingsService default values."""

    def test_defaults_defined(self) -> None:
        """All required defaults are defined."""
        service = SettingsService()

        assert "fetch_interval_minutes" in service.DEFAULTS
        assert "digest_time" in service.DEFAULTS
        assert "telegram_notifications" in service.DEFAULTS
        assert "digest_sections" in service.DEFAULTS

    def test_default_values(self) -> None:
        """Default values are correct."""
        service = SettingsService()

        assert service.DEFAULTS["fetch_interval_minutes"] == 60
        assert service.DEFAULTS["digest_time"] == "08:00"
        assert service.DEFAULTS["telegram_notifications"] is True
        assert "security_news" in service.DEFAULTS["digest_sections"]

    def test_types_defined(self) -> None:
        """All settings have types defined."""
        service = SettingsService()

        for key in service.DEFAULTS:
            assert key in service.TYPES, f"Missing type for {key}"

    def test_descriptions_defined(self) -> None:
        """All settings have descriptions defined."""
        service = SettingsService()

        for key in service.DEFAULTS:
            assert key in service.DESCRIPTIONS, f"Missing description for {key}"


class TestSettingsServiceValidation:
    """Tests for SettingsService value validation."""

    def test_validate_number_positive(self) -> None:
        """Number settings must be positive integers."""
        service = SettingsService()

        # Valid
        service._validate_value("fetch_interval_minutes", 60)
        service._validate_value("fetch_interval_minutes", 1)

        # Invalid
        with pytest.raises(ValueError):
            service._validate_value("fetch_interval_minutes", 0)

        with pytest.raises(ValueError):
            service._validate_value("fetch_interval_minutes", -1)

        with pytest.raises(ValueError):
            service._validate_value("fetch_interval_minutes", "60")

    def test_validate_time_format(self) -> None:
        """Time settings must be in HH:MM format."""
        service = SettingsService()

        # Valid
        service._validate_value("digest_time", "08:00")
        service._validate_value("digest_time", "00:00")
        service._validate_value("digest_time", "23:59")

        # Invalid
        with pytest.raises(ValueError):
            service._validate_value("digest_time", "8:00")  # Missing leading zero

        with pytest.raises(ValueError):
            service._validate_value("digest_time", "24:00")

        with pytest.raises(ValueError):
            service._validate_value("digest_time", "invalid")

    def test_validate_boolean(self) -> None:
        """Boolean settings must be actual booleans."""
        service = SettingsService()

        # Valid
        service._validate_value("telegram_notifications", True)
        service._validate_value("telegram_notifications", False)

        # Invalid
        with pytest.raises(ValueError):
            service._validate_value("telegram_notifications", "true")

        with pytest.raises(ValueError):
            service._validate_value("telegram_notifications", 1)

    def test_validate_multiselect(self) -> None:
        """Multiselect settings must be lists of valid options."""
        service = SettingsService()

        # Valid
        service._validate_value("digest_sections", ["security_news"])
        service._validate_value("digest_sections", ["security_news", "product_news"])
        service._validate_value("digest_sections", [])

        # Invalid
        with pytest.raises(ValueError):
            service._validate_value("digest_sections", "security_news")

        with pytest.raises(ValueError):
            service._validate_value("digest_sections", ["invalid_section"])


class TestSettingsServiceIntegration:
    """Integration tests for SettingsService with real database."""

    @pytest.fixture
    def settings_conftest(self, clean_database):
        """Use the clean_database fixture from fetcher tests."""
        return clean_database

    @pytest.mark.asyncio
    async def test_get_returns_default_when_not_set(self, settings_conftest, monkeypatch) -> None:
        """Get returns default value when setting not in database."""

        async def mock_get_db():
            return settings_conftest

        monkeypatch.setattr("src.core.services.settings.get_db", mock_get_db)

        service = SettingsService()
        value = await service.get("fetch_interval_minutes")

        assert value == 60  # Default value

    @pytest.mark.asyncio
    async def test_set_and_get(self, settings_conftest, monkeypatch) -> None:
        """Set persists value and get retrieves it."""

        async def mock_get_db():
            return settings_conftest

        monkeypatch.setattr("src.core.services.settings.get_db", mock_get_db)

        service = SettingsService()

        # Set a new value
        await service.set("fetch_interval_minutes", 30)

        # Get it back
        value = await service.get("fetch_interval_minutes")
        assert value == 30

    @pytest.mark.asyncio
    async def test_set_updates_existing(self, settings_conftest, monkeypatch) -> None:
        """Set updates an existing setting."""

        async def mock_get_db():
            return settings_conftest

        monkeypatch.setattr("src.core.services.settings.get_db", mock_get_db)

        service = SettingsService()

        # Set initial value
        await service.set("fetch_interval_minutes", 30)

        # Update it
        await service.set("fetch_interval_minutes", 45)

        # Verify updated
        value = await service.get("fetch_interval_minutes")
        assert value == 45

    @pytest.mark.asyncio
    async def test_reset_removes_setting(self, settings_conftest, monkeypatch) -> None:
        """Reset removes setting from database so default is used."""

        async def mock_get_db():
            return settings_conftest

        monkeypatch.setattr("src.core.services.settings.get_db", mock_get_db)

        service = SettingsService()

        # Set a custom value
        await service.set("fetch_interval_minutes", 30)
        assert await service.get("fetch_interval_minutes") == 30

        # Reset to default
        await service.reset("fetch_interval_minutes")

        # Should return default
        value = await service.get("fetch_interval_minutes")
        assert value == 60  # Default value

    @pytest.mark.asyncio
    async def test_get_all_returns_all_settings(self, settings_conftest, monkeypatch) -> None:
        """get_all returns all settings with metadata."""

        async def mock_get_db():
            return settings_conftest

        monkeypatch.setattr("src.core.services.settings.get_db", mock_get_db)

        service = SettingsService()

        # Set one custom value
        await service.set("fetch_interval_minutes", 30)

        # Get all settings
        settings = await service.get_all()

        # Verify structure
        assert "fetch_interval_minutes" in settings
        assert "digest_time" in settings

        # Custom setting
        assert settings["fetch_interval_minutes"]["value"] == 30
        assert settings["fetch_interval_minutes"]["is_default"] is False

        # Default setting
        assert settings["digest_time"]["value"] == "08:00"
        assert settings["digest_time"]["is_default"] is True

    @pytest.mark.asyncio
    async def test_get_unknown_key_raises(self, settings_conftest, monkeypatch) -> None:
        """Get with unknown key raises KeyError."""

        async def mock_get_db():
            return settings_conftest

        monkeypatch.setattr("src.core.services.settings.get_db", mock_get_db)

        service = SettingsService()

        with pytest.raises(KeyError):
            await service.get("unknown_key")

    @pytest.mark.asyncio
    async def test_set_unknown_key_raises(self, settings_conftest, monkeypatch) -> None:
        """Set with unknown key raises KeyError."""

        async def mock_get_db():
            return settings_conftest

        monkeypatch.setattr("src.core.services.settings.get_db", mock_get_db)

        service = SettingsService()

        with pytest.raises(KeyError):
            await service.set("unknown_key", "value")
