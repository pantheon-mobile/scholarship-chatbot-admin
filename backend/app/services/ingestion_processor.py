from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import PurePath
import time
from typing import Protocol

import boto3
import httpx

from app.models.data_source import DataSource
from app.services.document_conversion import (
    convert_pdf,
    convert_plain_text,
    convert_pptx,
    convert_xlsx,
    crawl_website,
)
from app.storage import LocalStorage, S3Storage


@dataclass(frozen=True)
class IngestionResult:
    character_count: int | None = None


@dataclass(frozen=True)
class IngestionArtifact:
    name: str
    body: bytes
    content_type: str
    character_count: int | None = None
    source_url: str | None = None
    metadata: dict | None = None


class IngestionProcessor(Protocol):
    async def process(self, data_source: DataSource) -> IngestionResult: ...


class HttpIngestionProcessor:
    """Adapter for the conversion/crawl/S3/Knowledge Base processing service."""

    def __init__(self, endpoint: str, *, timeout_seconds: float = 1800) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def process(self, data_source: DataSource) -> IngestionResult:
        payload = {
            "data_source_id": data_source.id,
            "source_type": data_source.source_type,
            "format": data_source.format,
            "title": data_source.title,
            "file": {
                "file_name": data_source.file.file_name,
                "storage_key": data_source.file.storage_key,
                "mime_type": data_source.file.mime_type,
            } if data_source.file else None,
            "website": {"url": data_source.website.url} if data_source.website else None,
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.endpoint}/process", json=payload)
            response.raise_for_status()
            body = response.json()
        return IngestionResult(character_count=body.get("character_count"))


class AwsIngestionProcessor:
    """Prepare a source, place Bedrock artifacts in S3, then synchronize its KB."""

    def __init__(self) -> None:
        self.region = os.getenv("AWS_REGION", "ap-northeast-1")
        self.bucket = os.getenv("INGESTION_S3_BUCKET", "").strip()
        if not self.bucket:
            raise RuntimeError("INGESTION_S3_BUCKET is required")
        self.s3 = boto3.client("s3", region_name=self.region)
        self.bedrock = boto3.client("bedrock-agent", region_name=self.region)
        if os.getenv("STORAGE_BACKEND", "local").lower() == "s3":
            self.source_storage = S3Storage(
                self.bucket,
                os.getenv("INGESTION_ORIGINAL_PREFIX", "documents/admin/originals/"),
            )
        else:
            self.source_storage = LocalStorage()

    async def process(self, data_source: DataSource) -> IngestionResult:
        kind = self._kind(data_source)
        knowledge_base_id, bedrock_data_source_id = self._kb_config(kind)
        artifacts = self._artifacts(data_source, kind)
        if not artifacts:
            raise RuntimeError("取り込み対象の文書が0件です。")
        prefix = os.getenv(
            f"INGESTION_{kind}_S3_PREFIX",
            f"documents/admin/kb-source/{kind.lower()}/",
        ).strip("/") + "/"
        source_prefix = f"{prefix}{data_source.id}/"
        self._clear_prefix(source_prefix)
        total_characters = 0
        has_character_count = False
        for artifact in artifacts:
            if artifact.character_count is not None:
                total_characters += artifact.character_count
                has_character_count = True
            key = f"{source_prefix}{artifact.name}"
            attributes = {
                "data_source_id": str(data_source.id),
                "source_type": data_source.source_type,
                "source_format": data_source.format,
                "source_title": data_source.title[:500],
                "ingestion_kind": kind,
                "source_url": artifact.source_url or "",
                "processed_at": datetime.now(timezone.utc).isoformat(),
                **(artifact.metadata or {}),
            }
            attributes = {key: value for key, value in attributes.items() if value not in (None, "")}
            metadata = json.dumps(
                {"metadataAttributes": attributes}, ensure_ascii=False
            ).encode("utf-8")
            self.s3.put_object(
                Bucket=self.bucket, Key=key, Body=artifact.body,
                ContentType=artifact.content_type,
            )
            self.s3.put_object(
                Bucket=self.bucket, Key=f"{key}.metadata.json", Body=metadata,
                ContentType="application/json",
            )
        self._synchronize(knowledge_base_id, bedrock_data_source_id)
        return IngestionResult(
            character_count=total_characters if has_character_count else None
        )

    def _clear_prefix(self, prefix: str) -> None:
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if objects:
                self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})

    @staticmethod
    def _kind(data_source: DataSource) -> str:
        if data_source.source_type == "WEB":
            return "WEB"
        extension = data_source.format.lower().lstrip(".")
        kinds = {
            "pdf": "PDF", "xlsx": "EXCEL", "docx": "WORD", "pptx": "PPT",
            "txt": "TEXT", "csv": "TEXT",
        }
        if extension not in kinds:
            raise RuntimeError(f"夜間変換に未対応のファイル形式です: {extension}")
        return kinds[extension]

    def _artifacts(self, data_source: DataSource, kind: str) -> list[IngestionArtifact]:
        if kind == "WEB":
            return self._markdown_artifacts(crawl_website(data_source.website.url))
        if data_source.file is None or not data_source.file.storage_key:
            raise RuntimeError("元ファイルの保存先がありません。")
        content = self.source_storage.read(data_source.file.storage_key)
        name = data_source.file.file_name
        extension = data_source.format.lower().lstrip(".")
        if extension == "docx":
            return [IngestionArtifact(
                name=PurePath(name).name,
                body=content,
                content_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "wordprocessingml.document"
                ),
                metadata={
                    "conversion_method": "original",
                    "ingestion_format": "WORD_DOCX",
                    "original_source_file_name": PurePath(name).name,
                },
            )]
        if extension == "pdf":
            documents = convert_pdf(content, name)
        if extension == "xlsx":
            documents = convert_xlsx(content, name)
        elif extension == "pptx":
            documents = convert_pptx(content, name)
        elif extension in {"txt", "csv"}:
            documents = convert_plain_text(content, name)
        elif extension != "pdf":
            raise AssertionError(f"Unsupported configured ingestion kind: {kind}")
        return self._markdown_artifacts(documents)

    @staticmethod
    def _markdown_artifacts(documents) -> list[IngestionArtifact]:
        return [IngestionArtifact(
            name=document.name,
            body=document.markdown.encode("utf-8"),
            content_type="text/markdown; charset=utf-8",
            character_count=len(document.markdown),
            source_url=document.source_url,
            metadata=document.metadata,
        ) for document in documents]

    @staticmethod
    def _kb_config(kind: str) -> tuple[str, str]:
        knowledge_base_id = os.getenv(f"INGESTION_{kind}_KNOWLEDGE_BASE_ID", "").strip()
        data_source_id = os.getenv(f"INGESTION_{kind}_DATA_SOURCE_ID", "").strip()
        if not knowledge_base_id or not data_source_id:
            raise RuntimeError(f"{kind}用のKnowledge Base IDまたはData Source IDが未設定です。")
        return knowledge_base_id, data_source_id

    def _synchronize(self, knowledge_base_id: str, data_source_id: str) -> None:
        response = self.bedrock.start_ingestion_job(
            knowledgeBaseId=knowledge_base_id,
            dataSourceId=data_source_id,
        )
        ingestion_job_id = response["ingestionJob"]["ingestionJobId"]
        timeout_seconds = int(os.getenv("KNOWLEDGE_BASE_SYNC_TIMEOUT_SECONDS", "1800"))
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            current = self.bedrock.get_ingestion_job(
                knowledgeBaseId=knowledge_base_id,
                dataSourceId=data_source_id,
                ingestionJobId=ingestion_job_id,
            )["ingestionJob"]
            status = current["status"]
            if status == "COMPLETE":
                return
            if status in {"FAILED", "STOPPED"}:
                reasons = "; ".join(current.get("failureReasons", []))
                raise RuntimeError(f"Knowledge Base同期失敗: {reasons or status}")
            time.sleep(5)
        raise TimeoutError(f"Knowledge Base同期が{timeout_seconds}秒以内に完了しませんでした。")
