from types import SimpleNamespace
from unittest.mock import MagicMock
import json

import pytest

from app.services.ingestion_processor import AwsIngestionProcessor


def test_text_and_csv_artifacts_share_pdf_data_source_prefix():
    assert AwsIngestionProcessor._default_s3_prefix("TEXT") == (
        "documents/admin/kb-source/pdf/"
    )
    assert AwsIngestionProcessor._default_s3_prefix("PDF") == (
        "documents/admin/kb-source/pdf/"
    )


def test_word_docx_is_uploaded_as_original_without_markdown_conversion():
    processor = object.__new__(AwsIngestionProcessor)
    processor.source_storage = SimpleNamespace(read=lambda key: b"original-docx-bytes")
    data_source = SimpleNamespace(
        format="docx",
        file=SimpleNamespace(
            file_name="guide.docx",
            storage_key="originals/guide.docx",
        ),
    )

    artifacts = processor._artifacts(data_source, "WORD")

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.name == "guide.docx"
    assert artifact.body == b"original-docx-bytes"
    assert artifact.content_type == (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    )
    assert artifact.character_count is None
    assert artifact.metadata == {
        "conversion_method": "original",
        "ingestion_format": "WORD_DOCX",
        "original_source_file_name": "guide.docx",
    }


def test_word_docx_discards_path_components_from_uploaded_file_name():
    processor = object.__new__(AwsIngestionProcessor)
    processor.source_storage = SimpleNamespace(read=lambda key: b"docx")
    data_source = SimpleNamespace(
        format="docx",
        file=SimpleNamespace(
            file_name="../outside/guide.docx",
            storage_key="originals/guide.docx",
        ),
    )

    artifact = processor._artifacts(data_source, "WORD")[0]

    assert artifact.name == "guide.docx"
    assert artifact.metadata["original_source_file_name"] == "guide.docx"


def test_pdf_artifacts_include_generated_semantic_metadata(monkeypatch):
    processor = object.__new__(AwsIngestionProcessor)
    processor.source_storage = SimpleNamespace(read=lambda key: b"pdf-bytes")
    document = SimpleNamespace(
        name="source.md", markdown="# guide.pdf\n\n本文", source_url=None,
        metadata={"page_count": 3, "conversion_method": "TEXT_MARKDOWN"},
    )
    monkeypatch.setattr("app.services.ingestion_processor.convert_pdf", lambda *_: [document])
    monkeypatch.setattr(
        "app.services.ingestion_processor.generate_pdf_content_metadata",
        lambda *_args, **_kwargs: {
            "document_type": "規程", "keywords": ["奨学金", "申請"],
            "summary": "奨学金申請の案内です。", "metadata_source_pages": 3,
        },
    )
    data_source = SimpleNamespace(
        format="pdf",
        file=SimpleNamespace(file_name="guide.pdf", storage_key="originals/guide.pdf"),
    )

    artifact = processor._artifacts(data_source, "PDF")[0]

    assert artifact.metadata["page_count"] == 3
    assert artifact.metadata["document_type"] == "規程"
    assert artifact.metadata["keywords"] == ["奨学金", "申請"]
    assert artifact.metadata["summary"] == "奨学金申請の案内です。"
    assert artifact.metadata["metadata_source_pages"] == 3


def test_pdf_metadata_failure_does_not_abort_conversion(monkeypatch):
    processor = object.__new__(AwsIngestionProcessor)
    processor.source_storage = SimpleNamespace(read=lambda key: b"pdf-bytes")
    document = SimpleNamespace(name="source.md", markdown="本文", source_url=None, metadata={})
    monkeypatch.setattr("app.services.ingestion_processor.convert_pdf", lambda *_: [document])
    monkeypatch.setattr(
        "app.services.ingestion_processor.generate_pdf_content_metadata",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("Bedrock unavailable")),
    )
    data_source = SimpleNamespace(
        format="pdf",
        file=SimpleNamespace(file_name="guide.pdf", storage_key="originals/guide.pdf"),
    )

    artifact = processor._artifacts(data_source, "PDF")[0]

    assert artifact.metadata["metadata_generation_status"] == "FAILED"
    assert artifact.metadata["metadata_generation_error"] == "Bedrock unavailable"


@pytest.mark.anyio
async def test_word_process_uploads_docx_and_sidecar_then_synchronizes(monkeypatch):
    monkeypatch.setenv("INGESTION_WORD_KNOWLEDGE_BASE_ID", "word-kb")
    monkeypatch.setenv("INGESTION_WORD_DATA_SOURCE_ID", "word-ds")
    processor = object.__new__(AwsIngestionProcessor)
    processor.bucket = "development-bucket"
    processor.source_storage = SimpleNamespace(read=lambda key: b"original-docx")
    processor.s3 = MagicMock()
    processor._clear_prefix = MagicMock()
    processor._synchronize = MagicMock()
    data_source = SimpleNamespace(
        id=42,
        source_type="FILE",
        format="docx",
        title="奨学金案内",
        answer_source_enabled=True,
        priority="HIGH",
        reference_link_visible=False,
        website=None,
        file=SimpleNamespace(
            file_name="guide.docx",
            storage_key="originals/guide.docx",
        ),
    )

    result = await processor.process(data_source)

    processor._clear_prefix.assert_called_once_with(
        "documents/admin/kb-source/word/42/"
    )
    docx_upload = processor.s3.put_object.call_args_list[0].kwargs
    assert docx_upload == {
        "Bucket": "development-bucket",
        "Key": "documents/admin/kb-source/word/42/guide.docx",
        "Body": b"original-docx",
        "ContentType": (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
    }
    metadata_upload = processor.s3.put_object.call_args_list[1].kwargs
    assert metadata_upload["Key"].endswith("guide.docx.metadata.json")
    assert b'"ingestion_format": "WORD_DOCX"' in metadata_upload["Body"]
    assert b'"answer_source_enabled": true' in metadata_upload["Body"]
    assert b'"answer_priority": "HIGH"' in metadata_upload["Body"]
    assert b'"reference_link_visible": false' in metadata_upload["Body"]
    processor._synchronize.assert_called_once_with("word-kb", "word-ds")
    assert result.character_count is None


@pytest.mark.anyio
async def test_web_process_returns_root_title_and_uses_it_in_metadata(monkeypatch):
    monkeypatch.setenv("INGESTION_WEB_KNOWLEDGE_BASE_ID", "web-kb")
    monkeypatch.setenv("INGESTION_WEB_DATA_SOURCE_ID", "web-ds")
    document = SimpleNamespace(
        name="web-root.md", markdown="# 取得したタイトル\n\n本文", source_url="https://example.com/",
        metadata={"page_title": "取得したタイトル"},
    )
    def fake_crawl(url, report):
        report.update({"pages": [{"source_url": url, "title": "取得したタイトル", "content_hash": "hash"}], "errors": [], "skipped": [], "summary": {}})
        return [document]
    monkeypatch.setattr("app.services.ingestion_processor.crawl_website", fake_crawl)
    processor = object.__new__(AwsIngestionProcessor)
    processor.bucket = "development-bucket"
    processor.s3 = MagicMock()
    processor.s3.get_object.side_effect = RuntimeError("no manifest")
    processor._clear_prefix = MagicMock()
    processor._synchronize = MagicMock()
    data_source = SimpleNamespace(
        id=43, source_type="WEB", format="Web", title="https://example.com/",
        answer_source_enabled=True, priority="MEDIUM", reference_link_visible=True,
        website=SimpleNamespace(url="https://example.com/"), file=None,
    )

    result = await processor.process(data_source)

    metadata_upload = next(call.kwargs for call in processor.s3.put_object.call_args_list if call.kwargs["Key"].endswith(".metadata.json"))
    assert "取得したタイトル" in metadata_upload["Body"].decode("utf-8")
    assert result.discovered_title == "取得したタイトル"


def test_web_crawl_logs_compare_manifest_and_store_audit_files():
    processor = object.__new__(AwsIngestionProcessor)
    processor.bucket = "development-bucket"
    processor.s3 = MagicMock()
    processor.s3.get_object.return_value = {
        "Body": SimpleNamespace(read=lambda: json.dumps({"pages": [
            {"source_url": "https://example.com/same", "content_hash": "same"},
            {"source_url": "https://example.com/changed", "content_hash": "old"},
            {"source_url": "https://example.com/removed", "content_hash": "old"},
        ]}).encode("utf-8"))
    }
    report = {
        "pages": [
            {"source_url": "https://example.com/same", "content_hash": "same"},
            {"source_url": "https://example.com/changed", "content_hash": "new"},
            {"source_url": "https://example.com/new", "content_hash": "new"},
        ],
        "errors": [{"url": "https://example.com/error", "depth": 1, "reason": "HTTP 500"}],
        "skipped": [],
        "summary": {},
    }

    processor._write_web_crawl_logs(42, report)

    assert [item["change"] for item in report["pages"]] == ["UNCHANGED", "UPDATED", "NEW"]
    assert report["deleted_candidates"] == ["https://example.com/removed"]
    keys = [call.kwargs["Key"] for call in processor.s3.put_object.call_args_list]
    assert "documents/admin/crawl-logs/42/manifest.json" in keys
    assert any(key.endswith("/crawl-report.json") for key in keys)
    assert any(key.endswith("/crawl-errors.csv") for key in keys)
    assert any(key.endswith("/crawl-skipped.csv") for key in keys)
