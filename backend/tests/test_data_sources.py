from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook
from pydantic import ValidationError

from app.api.v1.data_sources import get_service
from app.main import app
from app.repositories.data_source import DataSourceRepository
from app.schemas.data_source import (
    BulkDeleteRequest,
    ClassificationAssignment,
    DataSourceFilters,
    DeleteTarget,
)
from app.services.data_source_service import (
    ClassificationMismatchError,
    DataSourceService,
    DataSourceVersionConflictError,
    PageNotFoundError,
)


def make_row(*, version: int = 1, answer: bool = True, reference: bool = True):
    type_row = SimpleNamespace(id=1, type_code="TYPE_1", display_label="対象者", display_order=1)
    value_row = SimpleNamespace(id=1, value_name="在学生")
    link = SimpleNamespace(
        classification_type_id=1,
        classification_value_id=1,
        classification_type=type_row,
        classification_value=value_row,
    )
    return SimpleNamespace(
        id=1, source_type="FILE", title="［サンプル］募集要項", format="pdf", status="AVAILABLE",
        category_name=None, size_bytes=1024, character_count=2000,
        answer_source_enabled=answer, priority="HIGH", reference_link_visible=reference,
        updated_at=datetime(2026, 8, 6, 1, 2, tzinfo=timezone.utc), version=version,
        file=SimpleNamespace(file_name="sample.pdf"), website=None, classification_links=[link],
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
        keyword="募集", format="pdf", status="AVAILABLE",
        type_1_value_id=1, type_2_value_id=5, type_3_value_id=9,
        answer_source_enabled=True, priority="HIGH", reference_link_visible=False,
    )
    conditions = DataSourceRepository._conditions(filters)
    assert len(conditions) == 9
    assert "lower(data_sources.title) LIKE lower" in str(conditions[0])
    assert "data_source_files.file_name" in str(conditions[0])
    assert "data_source_websites.url" in str(conditions[0])


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


@pytest.mark.anyio
async def test_excel_uses_japanese_display_values_and_jst():
    repository = AsyncMock()
    repository.list.return_value = ([make_row()], 1, 1, 1024)
    data = await DataSourceService(repository).export_excel(DataSourceFilters())
    worksheet = load_workbook(BytesIO(data)).active
    values = list(worksheet.values)
    assert values[1][1] == "ファイル"
    assert values[1][5] == "利用可"
    assert values[1][12:15] == ("有効", "高", "表示")
    assert values[1][15] == "2026/08/06 10:02"
