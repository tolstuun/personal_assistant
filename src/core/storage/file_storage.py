"""
File storage implementation using MinIO/S3.

Provides file upload, download, and presigned URL generation.
Compatible with any S3-compatible storage service.
"""

import logging
from datetime import datetime  # noqa: F401 - may be used later
from io import BytesIO
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.core.config.loader import get_config
from src.core.storage.base import BaseFileStorage, FileInfo, FileStorageConfig
from src.core.storage.exceptions import ConfigurationError, ConnectionError, NotFoundError

logger = logging.getLogger(__name__)


class FileStorage(BaseFileStorage):
    """
    MinIO/S3 file storage implementation.

    Usage:
        storage = FileStorage(config)
        await storage.connect()

        # Upload file
        key = await storage.upload("reports/2024/jan.pdf", pdf_bytes)

        # Download file
        content = await storage.download("reports/2024/jan.pdf")

        # Generate presigned URL for direct access
        url = await storage.get_presigned_url("reports/2024/jan.pdf", expires=3600)

        await storage.disconnect()
    """

    def __init__(self, config: FileStorageConfig):
        """Initialize file storage with configuration."""
        super().__init__(config)
        self._client: Any = None  # boto3 client

    async def connect(self) -> None:
        """Establish connection and ensure bucket exists."""
        if self._client is not None:
            return

        try:
            endpoint_url = (
                f"https://{self.config.endpoint}"
                if self.config.secure
                else f"http://{self.config.endpoint}"
            )

            self._client = boto3.client(
                "s3",
                endpoint_url=endpoint_url,
                aws_access_key_id=self.config.access_key,
                aws_secret_access_key=self.config.secret_key,
                region_name=self.config.region,
                config=Config(signature_version="s3v4"),
            )

            # Ensure bucket exists
            await self._ensure_bucket()

            logger.info(f"Connected to MinIO/S3 at {self.config.endpoint}")
        except Exception as e:
            self._client = None
            raise ConnectionError(f"Failed to connect to MinIO/S3: {e}") from e

    async def _ensure_bucket(self) -> None:
        """Create bucket if it doesn't exist."""
        try:
            self._client.head_bucket(Bucket=self.config.bucket)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchBucket"):
                self._client.create_bucket(Bucket=self.config.bucket)
                logger.info(f"Created bucket: {self.config.bucket}")
            else:
                raise

    async def disconnect(self) -> None:
        """Close connection to file storage."""
        if self._client is not None:
            self._client = None
            logger.info("Disconnected from MinIO/S3")

    async def health_check(self) -> bool:
        """Check if file storage is reachable."""
        if self._client is None:
            return False

        try:
            self._client.head_bucket(Bucket=self.config.bucket)
            return True
        except Exception as e:
            logger.warning(f"MinIO/S3 health check failed: {e}")
            return False

    def _get_client(self) -> Any:
        """Get S3 client, raising if not connected."""
        if self._client is None:
            raise ConnectionError("File storage not connected. Call connect() first.")
        return self._client

    async def upload(
        self, key: str, content: bytes, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload file. Returns the file key."""
        client = self._get_client()

        client.upload_fileobj(
            BytesIO(content),
            self.config.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        logger.debug(f"Uploaded file: {key}")
        return key

    async def download(self, key: str) -> bytes:
        """Download file content."""
        client = self._get_client()

        try:
            response = client.get_object(Bucket=self.config.bucket, Key=key)
            content = response["Body"].read()
            return content
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                raise NotFoundError(f"File not found: {key}") from e
            raise

    async def delete(self, key: str) -> None:
        """Delete a file."""
        client = self._get_client()

        client.delete_object(Bucket=self.config.bucket, Key=key)
        logger.debug(f"Deleted file: {key}")

    async def exists(self, key: str) -> bool:
        """Check if file exists."""
        client = self._get_client()

        try:
            client.head_object(Bucket=self.config.bucket, Key=key)
            return True
        except ClientError:
            return False

    async def get_info(self, key: str) -> FileInfo:
        """Get file metadata."""
        client = self._get_client()

        try:
            response = client.head_object(Bucket=self.config.bucket, Key=key)
            return FileInfo(
                key=key,
                size=response["ContentLength"],
                last_modified=response["LastModified"].isoformat(),
                content_type=response.get("ContentType", ""),
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                raise NotFoundError(f"File not found: {key}") from e
            raise

    async def list_files(self, prefix: str = "") -> list[FileInfo]:
        """List files with optional prefix filter."""
        client = self._get_client()

        response = client.list_objects_v2(
            Bucket=self.config.bucket,
            Prefix=prefix,
        )

        files = []
        for obj in response.get("Contents", []):
            files.append(
                FileInfo(
                    key=obj["Key"],
                    size=obj["Size"],
                    last_modified=obj["LastModified"].isoformat(),
                )
            )

        return files

    async def get_presigned_url(self, key: str, expires: int = 3600) -> str:
        """Generate presigned URL for direct download."""
        client = self._get_client()

        url = client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.config.bucket,
                "Key": key,
            },
            ExpiresIn=expires,
        )
        return url

    async def get_presigned_upload_url(
        self, key: str, content_type: str = "application/octet-stream", expires: int = 3600
    ) -> str:
        """Generate presigned URL for direct upload."""
        client = self._get_client()

        url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.config.bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires,
        )
        return url


def _load_config() -> FileStorageConfig:
    """Load file storage configuration from config files."""
    config = get_config()
    minio_config = config.get("minio", {})

    if not minio_config:
        raise ConfigurationError("MinIO configuration not found")

    return FileStorageConfig(
        endpoint=minio_config.get("endpoint", "localhost:9000"),
        access_key=minio_config.get("access_key", "minioadmin"),
        secret_key=minio_config.get("secret_key", "minioadmin"),
        bucket=minio_config.get("bucket", "assistant"),
        secure=minio_config.get("secure", False),
        region=minio_config.get("region", "us-east-1"),
    )


# Global file storage instance
_file_storage_instance: FileStorage | None = None


async def get_file_storage() -> FileStorage:
    """
    Get the global file storage instance.

    Creates and connects the instance on first call.
    Subsequent calls return the same instance.

    Returns:
        Connected FileStorage instance.
    """
    global _file_storage_instance

    if _file_storage_instance is None:
        config = _load_config()
        _file_storage_instance = FileStorage(config)
        await _file_storage_instance.connect()

    return _file_storage_instance


async def close_file_storage() -> None:
    """Close the global file storage instance."""
    global _file_storage_instance

    if _file_storage_instance is not None:
        await _file_storage_instance.disconnect()
        _file_storage_instance = None
