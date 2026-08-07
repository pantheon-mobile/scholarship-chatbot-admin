from io import BytesIO
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import UploadFile
from httpx import ASGITransport, AsyncClient
from starlette.datastructures import Headers

from app.api.v1.data_sources import get_service, get_storage
from app.main import app
from app.services.data_source_service import DataSourceService, FileUploadError
from app.services.file_upload_validation import MAX_TOTAL_SIZE, FileUploadValidationError, validate_uploads
from app.storage.local import LocalStorage


def make_row(version: int = 1):
    return SimpleNamespace(
        id=1, source_type="FILE", title="guide.pdf", format="pdf", status="PREPARING",
        category_name=None, size_bytes=100, character_count=None,
        answer_source_enabled=True, priority="MEDIUM", reference_link_visible=True,
        updated_at=datetime.now(timezone.utc), version=version,
        file=SimpleNamespace(file_name="guide.pdf"), website=None, classification_links=[],
    )


SIGNATURES = {
    "pdf": b"%PDF-1.7\ncontent",
    "doc": bytes.fromhex("D0CF11E0A1B11AE1") + b"content",
    "xls": bytes.fromhex("D0CF11E0A1B11AE1") + b"content",
    "ppt": bytes.fromhex("D0CF11E0A1B11AE1") + b"content",
    "docx": b"PK\x03\x04content",
    "xlsx": b"PK\x03\x04content",
    "pptx": b"PK\x03\x04content",
    "txt": "テキスト".encode(),
    "csv": "a,b\n1,2".encode(),
}
CONTENT_TYPES = {
    "pdf": "application/pdf", "doc": "application/msword", "xls": "application/vnd.ms-excel",
    "ppt": "application/vnd.ms-powerpoint", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain", "csv": "text/csv",
}


def upload(name: str, content: bytes | None = None, content_type: str | None = None) -> UploadFile:
    extension = name.rsplit(".", 1)[-1].lower()
    return UploadFile(
        file=BytesIO(SIGNATURES[extension] if content is None else content),
        filename=name,
        headers=Headers({"content-type": content_type or CONTENT_TYPES.get(extension, "application/octet-stream")}),
    )


class LogicalSizeFile(BytesIO):
    def __init__(self, content: bytes, logical_size: int):
        super().__init__(content)
        self.logical_size = logical_size
        self.at_logical_end = False

    def seek(self, offset, whence=0):
        if whence == 2 and offset == 0:
            self.at_logical_end = True
            return self.logical_size
        self.at_logical_end = False
        return super().seek(offset, whence)

    def tell(self):
        return self.logical_size if self.at_logical_end else super().tell()


def logical_upload(size: int) -> UploadFile:
    return UploadFile(file=LogicalSizeFile(SIGNATURES["pdf"], size), filename="large.pdf", headers=Headers({"content-type": "application/pdf"}))


@pytest.mark.parametrize("extension", list(SIGNATURES))
def test_all_supported_extensions_and_uppercase(extension):
    result = validate_uploads([upload(f"sample.{extension.upper()}")])
    assert result[0].extension == extension


@pytest.mark.parametrize(("files", "code"), [
    ([], "FILE_REQUIRED"),
    ([upload("empty.txt", b"")], "EMPTY_FILE"),
    ([UploadFile(file=BytesIO(b"x"), filename="sample.md")], "UNSUPPORTED_FILE_TYPE"),
    ([upload("same.txt"), upload("SAME.TXT")], "DUPLICATE_FILE_NAME"),
    ([upload("fake.pdf", b"not-pdf")], "FILE_SIGNATURE_MISMATCH"),
    ([upload("wrong.pdf", content_type="text/plain")], "FILE_SIGNATURE_MISMATCH"),
    ([upload("../unsafe.txt")], "UNSAFE_FILE_NAME"),
])
def test_file_validation_errors(files, code):
    with pytest.raises(FileUploadValidationError) as exc:
        validate_uploads(files)
    assert exc.value.code == code


def test_twenty_files_allowed_and_twenty_one_rejected():
    assert len(validate_uploads([upload(f"{index}.txt") for index in range(20)])) == 20
    with pytest.raises(FileUploadValidationError) as exc:
        validate_uploads([upload(f"{index}.txt") for index in range(21)])
    assert exc.value.code == "FILE_COUNT_EXCEEDED"


def test_total_size_boundary_and_exceeded():
    assert validate_uploads([logical_upload(MAX_TOTAL_SIZE)])[0].size_bytes == MAX_TOTAL_SIZE
    with pytest.raises(FileUploadValidationError) as exc:
        validate_uploads([logical_upload(MAX_TOTAL_SIZE + 1)])
    assert exc.value.code == "TOTAL_SIZE_EXCEEDED"


def service_dependencies(tmp_path: Path):
    repository = AsyncMock()
    repository.resolve_classification_value.return_value = (1, 1)
    repository.create_file_sources.return_value = [1]
    repository.get.return_value = make_row(version=1)
    return repository, LocalStorage(tmp_path)


@pytest.mark.anyio
async def test_single_file_registration_title_defaults_and_settings(tmp_path):
    repository, storage = service_dependencies(tmp_path)
    result = await DataSourceService(repository).create_file_sources(
        [upload("guide.PDF")], storage, title="", type_1_value_id=1,
        type_2_value_id=None, type_3_value_id=None, priority="MEDIUM",
        answer_source_enabled=True, reference_link_visible=True,
    )
    assert len(result) == 1
    records = repository.create_file_sources.await_args.args[0]
    assert records[0]["title"] == "guide.PDF"
    assert records[0]["extension"] == "pdf"
    assert records[0]["storage_key"] != "guide.PDF"
    assert repository.create_file_sources.await_args.kwargs == {
        "priority": "MEDIUM", "answer_source_enabled": True,
        "reference_link_visible": True, "classifications": [(1, 1)],
    }
    repository.commit.assert_awaited_once()
    assert storage.exists(records[0]["storage_key"])


@pytest.mark.anyio
async def test_explicit_title_and_multiple_file_title_rejection(tmp_path):
    repository, storage = service_dependencies(tmp_path)
    await DataSourceService(repository).create_file_sources(
        [upload("guide.pdf")], storage, title="募集要項", type_1_value_id=None,
        type_2_value_id=None, type_3_value_id=None, priority="HIGH",
        answer_source_enabled=False, reference_link_visible=False,
    )
    assert repository.create_file_sources.await_args.args[0][0]["title"] == "募集要項"
    with pytest.raises(FileUploadError) as exc:
        await DataSourceService(repository).create_file_sources(
            [upload("a.txt"), upload("b.txt")], storage, title="指定不可",
            type_1_value_id=None, type_2_value_id=None, type_3_value_id=None,
            priority="LOW", answer_source_enabled=True, reference_link_visible=True,
        )
    assert exc.value.code == "TITLE_NOT_ALLOWED"


@pytest.mark.anyio
async def test_invalid_classification_is_rejected(tmp_path):
    repository, storage = service_dependencies(tmp_path)
    repository.resolve_classification_value.return_value = None
    with pytest.raises(FileUploadError) as exc:
        await DataSourceService(repository).create_file_sources(
            [upload("a.txt")], storage, title=None, type_1_value_id=999,
            type_2_value_id=None, type_3_value_id=None, priority="MEDIUM",
            answer_source_enabled=True, reference_link_visible=True,
        )
    assert exc.value.code == "INVALID_CLASSIFICATION"
    repository.create_file_sources.assert_not_awaited()


@pytest.mark.anyio
async def test_failure_rolls_back_db_and_removes_all_staged_and_final_files(tmp_path):
    repository = AsyncMock()
    repository.create_file_sources.return_value = [1, 2]
    storage = LocalStorage(tmp_path)
    original_finalize = storage.finalize
    call_count = 0

    def fail_second(path, key):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise OSError("disk failure")
        original_finalize(path, key)

    storage.finalize = MagicMock(side_effect=fail_second)
    with pytest.raises(FileUploadError) as exc:
        await DataSourceService(repository).create_file_sources(
            [upload("a.txt"), upload("b.txt")], storage, title=None,
            type_1_value_id=None, type_2_value_id=None, type_3_value_id=None,
            priority="MEDIUM", answer_source_enabled=True, reference_link_visible=True,
        )
    assert exc.value.code == "FILE_SAVE_FAILED"
    repository.rollback.assert_awaited_once()
    repository.commit.assert_not_awaited()
    assert list(tmp_path.glob("*.txt")) == []
    assert list((tmp_path / ".tmp").glob("*")) == []


def test_local_storage_keys_are_unique_and_original_name_is_not_used(tmp_path):
    storage = LocalStorage(tmp_path)
    keys = {storage.create_storage_key("pdf") for _ in range(20)}
    assert len(keys) == 20
    assert "same.pdf" not in keys


@pytest.mark.anyio
async def test_api_returns_machine_readable_upload_error(tmp_path):
    service = AsyncMock()
    service.create_file_sources.side_effect = FileUploadError("FILE_REQUIRED", "ファイルを選択してください。")
    app.dependency_overrides[get_service] = lambda: service
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/data-sources/files")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "FILE_REQUIRED", "message": "ファイルを選択してください。"}
