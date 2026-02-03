"""
Fetcher primitive — downloads content from URLs.

This is an atomic primitive that does ONE thing:
fetch content from a URL and return it in a structured way.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ContentType(StrEnum):
    """Detected content type."""
    HTML = "html"
    JSON = "json"
    XML = "xml"
    PDF = "pdf"
    TEXT = "text"
    BINARY = "binary"
    UNKNOWN = "unknown"


@dataclass
class FetchResult:
    """Result of fetching a URL."""
    url: str
    status_code: int
    content_type: ContentType
    content: bytes
    text: str | None
    headers: dict[str, str]
    fetched_at: datetime
    elapsed_ms: int
    encoding: str | None = None
    content_length: int | None = None

    @property
    def ok(self) -> bool:
        """True if request was successful (2xx status)."""
        return 200 <= self.status_code < 300


@dataclass
class FetcherConfig:
    """Configuration for Fetcher."""
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    extra_headers: dict[str, str] = field(default_factory=dict)
    follow_redirects: bool = True
    verify_ssl: bool = True


class Fetcher:
    """
    Fetches content from URLs.

    Usage:
        fetcher = Fetcher()
        result = await fetcher.fetch("https://example.com")

        if result.ok:
            print(result.text)
    """

    def __init__(self, config: FetcherConfig | None = None):
        self.config = config or FetcherConfig()

    async def fetch(self, url: str, **kwargs: Any) -> FetchResult:
        """Fetch content from URL."""
        timeout = kwargs.get("timeout", self.config.timeout)
        headers = {
            "User-Agent": self.config.user_agent,
            **self.config.extra_headers,
            **kwargs.get("headers", {}),
        }

        start_time = datetime.now()

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=self.config.follow_redirects,
            verify=self.config.verify_ssl,
        ) as client:

            last_error: Exception | None = None

            for attempt in range(self.config.max_retries):
                try:
                    response = await client.get(url, headers=headers)

                    elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                    content_type = self._detect_content_type(response)

                    text = None
                    if content_type not in (ContentType.PDF, ContentType.BINARY):
                        try:
                            text = response.text
                        except Exception:
                            pass

                    return FetchResult(
                        url=str(response.url),
                        status_code=response.status_code,
                        content_type=content_type,
                        content=response.content,
                        text=text,
                        headers=dict(response.headers),
                        fetched_at=datetime.now(),
                        elapsed_ms=elapsed_ms,
                        encoding=response.encoding,
                        content_length=len(response.content),
                    )

                except httpx.TimeoutException as e:
                    last_error = e
                    logger.warning(f"Timeout fetching {url}, attempt {attempt + 1}")

                except httpx.RequestError as e:
                    last_error = e
                    logger.warning(f"Error fetching {url}: {e}, attempt {attempt + 1}")

                if attempt < self.config.max_retries - 1:
                    import asyncio
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))

            raise RuntimeError(
                f"Failed to fetch {url} after {self.config.max_retries} attempts"
            ) from last_error

    def _detect_content_type(self, response: httpx.Response) -> ContentType:
        """Detect content type from response headers."""
        content_type_header = response.headers.get("content-type", "").lower()

        if "application/json" in content_type_header:
            return ContentType.JSON
        elif "text/html" in content_type_header:
            return ContentType.HTML
        elif "application/xml" in content_type_header or "text/xml" in content_type_header:
            return ContentType.XML
        elif "application/pdf" in content_type_header:
            return ContentType.PDF
        elif "text/" in content_type_header:
            return ContentType.TEXT
        elif content_type_header.startswith(("image/", "audio/", "video/")):
            return ContentType.BINARY
        else:
            content = response.content[:100]
            if content.startswith(b"%PDF"):
                return ContentType.PDF
            elif b"<!DOCTYPE html" in content or b"<html" in content:
                return ContentType.HTML
            elif content.startswith(b"<?xml"):
                return ContentType.XML

            return ContentType.UNKNOWN


async def fetch(url: str, **kwargs: Any) -> FetchResult:
    """Fetch content from URL (convenience function)."""
    fetcher = Fetcher()
    return await fetcher.fetch(url, **kwargs)
