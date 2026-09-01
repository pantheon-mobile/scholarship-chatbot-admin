from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


class S3Storage:
    def __init__(self, bucket: str, prefix: str = "documents/admin/originals/") -> None:
        if not bucket.strip():
            raise ValueError("S3 bucket is required")
        self.bucket = bucket.strip()
        self.prefix = prefix.strip("/") + "/"
        self.client = boto3.client("s3", region_name=os.getenv("AWS_REGION", "ap-northeast-1"))

    def create_storage_key(self, extension: str) -> str:
        normalized = extension.lower().lstrip(".")
        return f"{self.prefix}{uuid.uuid4().hex}.{normalized}"

    def save_temporary(self, source) -> Path:
        descriptor, name = tempfile.mkstemp(prefix="admin-upload-", suffix=".tmp")
        path = Path(name)
        try:
            source.seek(0)
            with os.fdopen(descriptor, "wb") as destination:
                while chunk := source.read(1024 * 1024):
                    destination.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path

    def finalize(self, temporary_path: Path, storage_key: str) -> None:
        self._validate_key(storage_key)
        self.client.upload_file(str(temporary_path), self.bucket, storage_key)
        temporary_path.unlink(missing_ok=True)

    def delete_temporary(self, temporary_path: Path) -> None:
        temporary_path.unlink(missing_ok=True)

    def delete(self, storage_key: str) -> None:
        self._validate_key(storage_key)
        self.client.delete_object(Bucket=self.bucket, Key=storage_key)

    def exists(self, storage_key: str) -> bool:
        self._validate_key(storage_key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=storage_key)
            return True
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            raise

    def read(self, storage_key: str) -> bytes:
        self._validate_key(storage_key)
        return self.client.get_object(Bucket=self.bucket, Key=storage_key)["Body"].read()

    def _validate_key(self, storage_key: str) -> None:
        if not storage_key.startswith(self.prefix) or ".." in storage_key.split("/"):
            raise ValueError("invalid_storage_key")
