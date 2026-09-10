from types import SimpleNamespace
from unittest.mock import MagicMock

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
