"""
Tests for SummarizerService.

Unit tests that mock the LLM to avoid real API calls.
"""

import pytest

from src.core.services.summarizer import SummarizerService, SummaryResult


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, response: dict | None = None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls: list[tuple[str, dict | None]] = []

    async def complete_json(self, prompt: str, schema: dict | None = None) -> dict:
        self.calls.append((prompt, schema))
        if self.error:
            raise self.error
        return self.response or {}


class MockSettingsService:
    """Mock settings service for testing."""

    def __init__(self, provider: str = "ollama", tier: str = "fast"):
        self.provider = provider
        self.tier = tier
        self.get_calls: list[str] = []

    async def get(self, key: str):
        self.get_calls.append(key)
        if key == "summarizer_provider":
            return self.provider
        if key == "summarizer_tier":
            return self.tier
        raise KeyError(f"Unknown key: {key}")


class TestSummarizerServiceSuccess:
    """Tests for successful summarization."""

    @pytest.mark.asyncio
    async def test_summarize_returns_summary_result(self, monkeypatch) -> None:
        """Successful summarization returns SummaryResult with summary."""
        mock_llm = MockLLM(response={"summary": "This is a test summary."})

        def mock_get_llm(**kwargs):
            return mock_llm

        monkeypatch.setattr("src.core.services.summarizer.get_llm", mock_get_llm)

        service = SummarizerService(settings_service=MockSettingsService())

        result = await service.summarize(
            title="Test Article",
            content="Some article content here.",
            url="https://example.com/article",
        )

        assert isinstance(result, SummaryResult)
        assert result.summary == "This is a test summary."
        assert result.title == "Test Article"
        assert result.url == "https://example.com/article"

    @pytest.mark.asyncio
    async def test_summarize_strips_whitespace(self, monkeypatch) -> None:
        """Summary is stripped of leading/trailing whitespace."""
        mock_llm = MockLLM(response={"summary": "  Summary with spaces.  "})

        def mock_get_llm(**kwargs):
            return mock_llm

        monkeypatch.setattr("src.core.services.summarizer.get_llm", mock_get_llm)

        service = SummarizerService(settings_service=MockSettingsService())

        result = await service.summarize(
            title="Test Article",
            content="Content",
            url="https://example.com",
        )

        assert result.summary == "Summary with spaces."


class TestSummarizerServiceFallback:
    """Tests for fallback to title on error."""

    @pytest.mark.asyncio
    async def test_empty_summary_falls_back_to_title(self, monkeypatch) -> None:
        """Empty summary string falls back to title."""
        mock_llm = MockLLM(response={"summary": ""})

        def mock_get_llm(**kwargs):
            return mock_llm

        monkeypatch.setattr("src.core.services.summarizer.get_llm", mock_get_llm)

        service = SummarizerService(settings_service=MockSettingsService())

        result = await service.summarize(
            title="Fallback Title",
            content="Content",
            url="https://example.com",
        )

        assert result.summary == "Fallback Title"

    @pytest.mark.asyncio
    async def test_whitespace_only_summary_falls_back_to_title(self, monkeypatch) -> None:
        """Whitespace-only summary falls back to title."""
        mock_llm = MockLLM(response={"summary": "   "})

        def mock_get_llm(**kwargs):
            return mock_llm

        monkeypatch.setattr("src.core.services.summarizer.get_llm", mock_get_llm)

        service = SummarizerService(settings_service=MockSettingsService())

        result = await service.summarize(
            title="Fallback Title",
            content="Content",
            url="https://example.com",
        )

        assert result.summary == "Fallback Title"

    @pytest.mark.asyncio
    async def test_missing_summary_key_falls_back_to_title(self, monkeypatch) -> None:
        """Missing summary key in response falls back to title."""
        mock_llm = MockLLM(response={"other_key": "value"})

        def mock_get_llm(**kwargs):
            return mock_llm

        monkeypatch.setattr("src.core.services.summarizer.get_llm", mock_get_llm)

        service = SummarizerService(settings_service=MockSettingsService())

        result = await service.summarize(
            title="Fallback Title",
            content="Content",
            url="https://example.com",
        )

        assert result.summary == "Fallback Title"

    @pytest.mark.asyncio
    async def test_non_string_summary_falls_back_to_title(self, monkeypatch) -> None:
        """Non-string summary value falls back to title."""
        mock_llm = MockLLM(response={"summary": 12345})

        def mock_get_llm(**kwargs):
            return mock_llm

        monkeypatch.setattr("src.core.services.summarizer.get_llm", mock_get_llm)

        service = SummarizerService(settings_service=MockSettingsService())

        result = await service.summarize(
            title="Fallback Title",
            content="Content",
            url="https://example.com",
        )

        assert result.summary == "Fallback Title"

    @pytest.mark.asyncio
    async def test_llm_value_error_falls_back_to_title(self, monkeypatch) -> None:
        """ValueError from LLM (invalid JSON) falls back to title."""
        mock_llm = MockLLM(error=ValueError("Invalid JSON"))

        def mock_get_llm(**kwargs):
            return mock_llm

        monkeypatch.setattr("src.core.services.summarizer.get_llm", mock_get_llm)

        service = SummarizerService(settings_service=MockSettingsService())

        result = await service.summarize(
            title="Fallback Title",
            content="Content",
            url="https://example.com",
        )

        assert result.summary == "Fallback Title"

    @pytest.mark.asyncio
    async def test_llm_exception_falls_back_to_title(self, monkeypatch) -> None:
        """Any exception from LLM falls back to title."""
        mock_llm = MockLLM(error=RuntimeError("API error"))

        def mock_get_llm(**kwargs):
            return mock_llm

        monkeypatch.setattr("src.core.services.summarizer.get_llm", mock_get_llm)

        service = SummarizerService(settings_service=MockSettingsService())

        result = await service.summarize(
            title="Fallback Title",
            content="Content",
            url="https://example.com",
        )

        assert result.summary == "Fallback Title"


class TestSummarizerServiceSettings:
    """Tests for settings integration."""

    @pytest.mark.asyncio
    async def test_uses_settings_provider_and_tier(self, monkeypatch) -> None:
        """get_llm is called with provider and tier from settings."""
        mock_llm = MockLLM(response={"summary": "Test summary"})
        get_llm_calls: list[dict] = []

        def mock_get_llm(**kwargs):
            get_llm_calls.append(kwargs)
            return mock_llm

        monkeypatch.setattr("src.core.services.summarizer.get_llm", mock_get_llm)

        mock_settings = MockSettingsService(provider="anthropic", tier="smart")
        service = SummarizerService(settings_service=mock_settings)

        await service.summarize(
            title="Test",
            content="Content",
            url="https://example.com",
        )

        # Verify settings were read
        assert "summarizer_provider" in mock_settings.get_calls
        assert "summarizer_tier" in mock_settings.get_calls

        # Verify get_llm was called with correct values
        assert len(get_llm_calls) == 1
        assert get_llm_calls[0]["provider"] == "anthropic"
        assert get_llm_calls[0]["tier"] == "smart"

    @pytest.mark.asyncio
    async def test_uses_default_llm_config(self, monkeypatch) -> None:
        """get_llm is called with temperature=0.2 and max_tokens=200."""
        mock_llm = MockLLM(response={"summary": "Test summary"})
        get_llm_calls: list[dict] = []

        def mock_get_llm(**kwargs):
            get_llm_calls.append(kwargs)
            return mock_llm

        monkeypatch.setattr("src.core.services.summarizer.get_llm", mock_get_llm)

        service = SummarizerService(settings_service=MockSettingsService())

        await service.summarize(
            title="Test",
            content="Content",
            url="https://example.com",
        )

        assert len(get_llm_calls) == 1
        assert get_llm_calls[0]["temperature"] == 0.2
        assert get_llm_calls[0]["max_tokens"] == 200
