"""
Tests for MinIO/S3 file storage.

Requires docker-compose minio service to be running.
Run: docker-compose up -d minio

Note: These tests are skipped in CI (MinIO service not available).
Run locally with docker-compose for full test coverage.
"""

import os

import pytest

from src.core.storage.exceptions import NotFoundError
from src.core.storage.file_storage import FileStorage

# Skip all tests in this file if running in CI (no MinIO service)
pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true" and not os.environ.get("MINIO_ENDPOINT"),
    reason="MinIO not available in CI"
)


@pytest.mark.asyncio
async def test_file_storage_connection(file_storage: FileStorage) -> None:
    """Test that file storage connects successfully."""
    assert await file_storage.health_check() is True


@pytest.mark.asyncio
async def test_file_storage_upload_download(file_storage: FileStorage) -> None:
    """Test uploading and downloading files."""
    test_key = "test/upload_download.txt"
    test_content = b"Hello, World!"

    try:
        # Upload
        key = await file_storage.upload(test_key, test_content, "text/plain")
        assert key == test_key

        # Download
        content = await file_storage.download(test_key)
        assert content == test_content

    finally:
        # Cleanup
        await file_storage.delete(test_key)


@pytest.mark.asyncio
async def test_file_storage_download_nonexistent(file_storage: FileStorage) -> None:
    """Test downloading a file that doesn't exist."""
    with pytest.raises(NotFoundError):
        await file_storage.download("nonexistent/file.txt")


@pytest.mark.asyncio
async def test_file_storage_exists(file_storage: FileStorage) -> None:
    """Test checking if file exists."""
    test_key = "test/exists_check.txt"
    test_content = b"Test content"

    try:
        # File doesn't exist yet
        assert await file_storage.exists(test_key) is False

        # Upload file
        await file_storage.upload(test_key, test_content)

        # File now exists
        assert await file_storage.exists(test_key) is True

    finally:
        await file_storage.delete(test_key)


@pytest.mark.asyncio
async def test_file_storage_delete(file_storage: FileStorage) -> None:
    """Test deleting files."""
    test_key = "test/to_delete.txt"
    test_content = b"Delete me"

    # Upload
    await file_storage.upload(test_key, test_content)
    assert await file_storage.exists(test_key) is True

    # Delete
    await file_storage.delete(test_key)
    assert await file_storage.exists(test_key) is False


@pytest.mark.asyncio
async def test_file_storage_get_info(file_storage: FileStorage) -> None:
    """Test getting file metadata."""
    test_key = "test/file_info.txt"
    test_content = b"File info test content"

    try:
        await file_storage.upload(test_key, test_content, "text/plain")

        info = await file_storage.get_info(test_key)

        assert info.key == test_key
        assert info.size == len(test_content)
        assert info.content_type == "text/plain"
        assert info.last_modified is not None

    finally:
        await file_storage.delete(test_key)


@pytest.mark.asyncio
async def test_file_storage_get_info_nonexistent(file_storage: FileStorage) -> None:
    """Test getting info for nonexistent file."""
    with pytest.raises(NotFoundError):
        await file_storage.get_info("nonexistent/file.txt")


@pytest.mark.asyncio
async def test_file_storage_list_files(file_storage: FileStorage) -> None:
    """Test listing files with prefix."""
    test_files = [
        ("test/list/file1.txt", b"Content 1"),
        ("test/list/file2.txt", b"Content 2"),
        ("test/other/file3.txt", b"Content 3"),
    ]

    try:
        # Upload test files
        for key, content in test_files:
            await file_storage.upload(key, content)

        # List files with prefix
        files = await file_storage.list_files("test/list/")

        assert len(files) == 2
        keys = [f.key for f in files]
        assert "test/list/file1.txt" in keys
        assert "test/list/file2.txt" in keys
        assert "test/other/file3.txt" not in keys

    finally:
        # Cleanup
        for key, _ in test_files:
            try:
                await file_storage.delete(key)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_file_storage_presigned_url(file_storage: FileStorage) -> None:
    """Test generating presigned URLs."""
    test_key = "test/presigned.txt"
    test_content = b"Presigned URL content"

    try:
        await file_storage.upload(test_key, test_content)

        url = await file_storage.get_presigned_url(test_key, expires=3600)

        assert url is not None
        assert test_key in url
        assert "X-Amz-Signature" in url or "Signature" in url

    finally:
        await file_storage.delete(test_key)


@pytest.mark.asyncio
async def test_file_storage_presigned_upload_url(file_storage: FileStorage) -> None:
    """Test generating presigned upload URLs."""
    test_key = "test/presigned_upload.txt"

    url = await file_storage.get_presigned_upload_url(test_key, "text/plain", expires=3600)

    assert url is not None
    assert test_key in url
    assert "X-Amz-Signature" in url or "Signature" in url


@pytest.mark.asyncio
async def test_file_storage_binary_content(file_storage: FileStorage) -> None:
    """Test uploading and downloading binary content."""
    test_key = "test/binary.bin"
    # Generate some binary content
    test_content = bytes(range(256))

    try:
        await file_storage.upload(test_key, test_content, "application/octet-stream")
        content = await file_storage.download(test_key)

        assert content == test_content
        assert len(content) == 256

    finally:
        await file_storage.delete(test_key)
