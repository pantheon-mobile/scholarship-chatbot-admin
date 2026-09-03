from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook
from pydantic import ValidationError

from app.api.v1.data_sources import get_ingestion_launcher, get_service
from app.main import app
from app.repositories.data_source import DataSourceRepository
from app.schemas.data_source import (
    BulkDeleteRequest,
    ClassificationAssignment,
    DataSourceFilters,
    DeleteTarget,
    FileDataSourceUpdateRequest,
)
from app.services.data_source_service import (
    ClassificationMismatchError,
    DataSourceNotFoundError,
    DataSourceService,
    DataSourceCategoryNotFoundError,
    DataSourceUpdateError,
    DataSourceVersionConflictError,
    FileDataSourceRequiredError,
    PageNotFoundError,
)


def make_row(*, version: int = 1, answer: bool = True, reference: bool = True, source_type: str = "FILE", category_id: int | None = None, category_name: str | None = None):
    type_row = SimpleNamespace(id=1, type_code="TYPE_1", display_label="対象者", display_order=1)
    value_row = SimpleNamespace(id=1, value_name="在学生")
    link = SimpleNamespace(
        classification_type_id=1,
        classification_value_id=1,
        classification_type=type_row,
        classification_value=value_row,
    )
    return SimpleNamespace(
        id=1, source_type=source_type, title="［サンプル］募集要項", format="pdf", status="AVAILABLE",
        category_id=category_id, category_name=category_name, size_bytes=1024, character_count=2000,
        answer_source_enabled=answer, priority="HIGH", reference_link_visible=reference,
        updated_at=datetime(2026, 8, 6, 1, 2, tzinfo=timezone.utc), version=version,
        file=SimpleNamespace(file_name="sample.pdf", storage_key="fixed.pdf", mime_type="application/pdf") if source_type == "FILE" else None,
        website=SimpleNamespace(url="https://example.com") if source_type == "WEB" else None,
        classification_links=[link],
    )


@pytest.fixture
def mock_service():
    service = AsyncMock()
    app.dependency_overrides[get_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


def test_filters_default_sort_and_page_size():
    filters = DataSourceFilters()
    assert (filters.sort, filters.order, filters.page, filters.page_size) == ("updated_at", "desc", 1, 10)


@pytest.mark.parametrize("sort", ["id", "title", "updated_at"])
def test_three_sort_columns_are_allowed(sort):
    assert DataSourceFilters(sort=sort).sort == sort


def test_invalid_sort_and_page_size_are_rejected():
    with pytest.raises(ValidationError):
        DataSourceFilters(sort="status")
    with pytest.raises(ValidationError):
        DataSourceFilters(page_size=15)


def test_all_filters_are_combined_as_independent_and_conditions():
    filters = DataSourceFilters(
        keyword="募集", format="pdf", status="AVAILABLE", category_id=7,
        type_1_value_id=1, type_2_value_id=5, type_3_value_id=9,
        answer_source_enabled=True, priority="HIGH", reference_link_visible=False,
    )
    conditions = DataSourceRepository._conditions(filters)
    assert len(conditions) == 10
    assert "lower(data_sources.title) LIKE lower" in str(conditions[0])
    assert "data_source_files.file_name" in str(conditions[0])
    assert "data_source_websites.url" in str(conditions[0])
    assert "data_sources.category_id" in str(conditions[3])


@pytest.mark.anyio
async def test_category_path_and_legacy_fallback_use_one_category_query():
    categories = [
        SimpleNamespace(id=10, name="奨学金", parent_id=None),
        SimpleNamespace(id=11, name="給付", parent_id=10),
        SimpleNamespace(id=12, name="学部", parent_id=11),
    ]
    formal = make_row(category_id=12, category_name="旧カテゴリ")
    legacy = make_row(category_name="旧カテゴリ")
    legacy.id = 2
    repository = AsyncMock()
    repository.list.return_value = ([formal, legacy], 2, 1, 2048)
    repository.list_categories.return_value = categories
    result = await DataSourceService(repository).list(DataSourceFilters())
    assert result.items[0].category.path == "奨学金/給付/学部"
    assert result.items[0].category_name == "奨学金/給付/学部"
    assert result.items[1].category is None
    assert result.items[1].category_name == "旧カテゴリ"
    repository.list_categories.assert_awaited_once()


@pytest.mark.anyio
async def test_missing_category_is_rejected():
    repository = AsyncMock()
    repository.category_exists.return_value = False
    with pytest.raises(DataSourceCategoryNotFoundError):
        await DataSourceService(repository).validate_category(999)


@pytest.mark.anyio
async def test_page_not_found_has_dedicated_error_code(mock_service):
    mock_service.list.side_effect = PageNotFoundError()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/data-sources?page=99")
    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "PAGE_NOT_FOUND", "message": "ページがありません。"}


@pytest.mark.anyio
async def test_empty_bulk_delete_is_422(mock_service):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/data-sources/bulk-delete", json={"items": []})
    assert response.status_code == 422
    mock_service.bulk_delete.assert_not_called()


@pytest.mark.anyio
async def test_run_ingestion_now_starts_worker_in_background(mock_service):
    launcher = AsyncMock()
    app.dependency_overrides[get_ingestion_launcher] = lambda: launcher
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/data-sources/ingestion/run-now")
    assert response.status_code == 202
    assert response.json() == {"message": "待機中のデータソースの処理を開始しました。"}
    launcher.assert_awaited_once_with()


@pytest.mark.anyio
async def test_list_service_paging_and_serialization():
    repository = AsyncMock()
    repository.list.return_value = ([make_row()], 12, 2, 1024)
    result = await DataSourceService(repository).list(DataSourceFilters())
    assert result.total_count == 12
    assert result.total_pages == 2
    assert result.items[0].file.file_name == "sample.pdf"
    assert result.items[0].classifications[0].type_code == "TYPE_1"


@pytest.mark.anyio
async def test_service_rejects_out_of_range_page():
    repository = AsyncMock()
    repository.list.return_value = ([], 12, 2, 1024)
    with pytest.raises(PageNotFoundError):
        await DataSourceService(repository).list(DataSourceFilters(page=3))


@pytest.mark.anyio
async def test_toggle_returns_reloaded_complete_row_and_version():
    repository = AsyncMock()
    repository.get.side_effect = [make_row(), make_row(version=2, answer=False)]
    repository.update_toggle.return_value = True
    result = await DataSourceService(repository).update_answer_source(1, False, 1)
    assert result.answer_source_enabled is False
    assert result.version == 2
    assert result.file.file_name == "sample.pdf"


@pytest.mark.anyio
async def test_toggle_version_conflict():
    repository = AsyncMock()
    repository.get.return_value = make_row()
    repository.update_toggle.return_value = False
    with pytest.raises(DataSourceVersionConflictError):
        await DataSourceService(repository).update_reference_link(1, False, 99)


@pytest.mark.anyio
async def test_single_delete_uses_version():
    repository = AsyncMock()
    repository.get.return_value = make_row()
    repository.delete_one.return_value = True
    await DataSourceService(repository).delete(1, 1)
    repository.delete_one.assert_awaited_once_with(1, 1)


@pytest.mark.anyio
async def test_bulk_delete_passes_all_targets_as_one_repository_operation():
    repository = AsyncMock()
    repository.bulk_delete.return_value = 2
    payload = BulkDeleteRequest(items=[DeleteTarget(id=1, version=1), DeleteTarget(id=2, version=3)])
    assert await DataSourceService(repository).bulk_delete(payload) == 2
    repository.bulk_delete.assert_awaited_once_with(payload.items)


@pytest.mark.anyio
async def test_classification_value_must_belong_to_type():
    repository = AsyncMock()
    repository.classification_value_matches_type.return_value = False
    with pytest.raises(ClassificationMismatchError):
        await DataSourceService(repository).validate_classification_assignments([
            ClassificationAssignment(classification_type_id=1, classification_value_id=999)
        ])


def update_payload(**values):
    return FileDataSourceUpdateRequest(
        title=values.get("title", "更新タイトル"),
        category_id=values.get("category_id"),
        type_1_value_id=values.get("type_1_value_id", 1),
        type_2_value_id=values.get("type_2_value_id"),
        type_3_value_id=values.get("type_3_value_id"),
        priority=values.get("priority", "MEDIUM"),
        answer_source_enabled=values.get("answer_source_enabled", False),
        reference_link_visible=values.get("reference_link_visible", False),
        version=values.get("version", 1),
    )


@pytest.mark.anyio
async def test_file_detail_returns_complete_row_and_not_found():
    repository = AsyncMock()
    repository.get.side_effect = [make_row(), None]
    service = DataSourceService(repository)
    result = await service.get(1)
    assert result.file.file_name == "sample.pdf"
    assert result.size_bytes == 1024
    with pytest.raises(DataSourceNotFoundError):
        await service.get(999)


@pytest.mark.anyio
async def test_file_attribute_update_resolves_types_and_returns_new_version():
    repository = AsyncMock()
    before = make_row()
    after = make_row(version=2, answer=False, reference=False)
    after.title = "更新タイトル"
    after.category_id = 12
    after.priority = "MEDIUM"
    repository.get.side_effect = [before, after]
    repository.resolve_classification_value.return_value = (1, 1)
    repository.category_exists.return_value = True
    repository.list_categories.return_value = [
        SimpleNamespace(id=10, name="奨学金", parent_id=None),
        SimpleNamespace(id=12, name="給付", parent_id=10),
    ]
    repository.update_file_attributes.return_value = True
    payload = update_payload(category_id=12)
    result = await DataSourceService(repository).update_file_attributes(1, payload)
    assert result.version == 2
    assert result.status == "AVAILABLE"
    assert result.category_name == "奨学金/給付"
    assert result.file.file_name == "sample.pdf"
    repository.update_file_attributes.assert_awaited_once_with(1, payload, "更新タイトル", [(1, 1)])
    repository.category_exists.assert_awaited_once_with(12)


@pytest.mark.anyio
async def test_blank_title_falls_back_to_existing_file_name_and_classifications_can_clear():
    repository = AsyncMock()
    after = make_row(version=2)
    after.title = "sample.pdf"
    after.classification_links = []
    repository.get.side_effect = [make_row(), after]
    repository.update_file_attributes.return_value = True
    payload = update_payload(title="   ", type_1_value_id=None)
    result = await DataSourceService(repository).update_file_attributes(1, payload)
    assert result.title == "sample.pdf"
    repository.update_file_attributes.assert_awaited_once_with(1, payload, "sample.pdf", [])


@pytest.mark.anyio
async def test_file_update_rejects_web_invalid_classification_and_version_conflict():
    repository = AsyncMock()
    repository.get.return_value = make_row(source_type="WEB")
    with pytest.raises(FileDataSourceRequiredError):
        await DataSourceService(repository).update_file_attributes(1, update_payload())

    repository.get.return_value = make_row()
    repository.resolve_classification_value.return_value = None
    with pytest.raises(ClassificationMismatchError):
        await DataSourceService(repository).update_file_attributes(1, update_payload())

    repository.resolve_classification_value.return_value = (1, 1)
    repository.update_file_attributes.return_value = False
    with pytest.raises(DataSourceVersionConflictError):
        await DataSourceService(repository).update_file_attributes(1, update_payload(version=99))


@pytest.mark.anyio
async def test_file_update_failure_rolls_back():
    repository = AsyncMock()
    repository.get.return_value = make_row()
    repository.resolve_classification_value.return_value = (1, 1)
    repository.update_file_attributes.side_effect = RuntimeError("db failure")
    with pytest.raises(DataSourceUpdateError):
        await DataSourceService(repository).update_file_attributes(1, update_payload())
    repository.rollback.assert_awaited_once()


def test_file_update_title_length_boundary():
    assert len(FileDataSourceUpdateRequest(**{**update_payload().model_dump(), "title": "a" * 500}).title) == 500
    with pytest.raises(ValidationError):
        FileDataSourceUpdateRequest(**{**update_payload().model_dump(), "title": "a" * 501})


@pytest.mark.anyio
async def test_file_detail_and_update_api_errors(mock_service):
    mock_service.get.side_effect = DataSourceNotFoundError()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/data-sources/999")
        assert response.status_code == 404

        mock_service.update_file_attributes.side_effect = FileDataSourceRequiredError()
        response = await client.put("/api/v1/data-sources/1", json=update_payload().model_dump())
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "FILE_DATA_SOURCE_REQUIRED"

        mock_service.update_file_attributes.side_effect = DataSourceVersionConflictError()
        response = await client.put("/api/v1/data-sources/1", json=update_payload().model_dump())
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "VERSION_CONFLICT"


@pytest.mark.anyio
async def test_excel_uses_japanese_display_values_and_jst():
    repository = AsyncMock()
    formal = make_row(category_id=12)
    legacy = make_row(category_name="旧カテゴリ")
    legacy.id = 2
    empty = make_row()
    empty.id = 3
    repository.list.return_value = ([formal, legacy, empty], 3, 1, 3072)
    repository.list_categories.return_value = [
        SimpleNamespace(id=10, name="奨学金", parent_id=None),
        SimpleNamespace(id=11, name="給付", parent_id=10),
        SimpleNamespace(id=12, name="学部", parent_id=11),
    ]
    data = await DataSourceService(repository).export_excel(DataSourceFilters())
    worksheet = load_workbook(BytesIO(data)).active
    values = list(worksheet.values)
    assert values[1][1] == "ファイル"
    assert values[1][5] == "利用可"
    assert values[1][6] == "奨学金/給付/学部"
    assert values[2][6] == "旧カテゴリ"
    assert values[3][6] is None
    assert values[1][12:15] == ("有効", "高", "表示")
    assert values[1][15] == "2026/08/06 10:02"
