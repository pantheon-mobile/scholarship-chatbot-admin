from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook
from pydantic import ValidationError

from app.api.v1.faqs import get_service
from app.main import app
from app.repositories.faq import FaqRepository
from app.schemas.faq import FaqBulkDeleteRequest, FaqDeleteTarget, FaqFilters
from app.services.faq_service import FaqError, FaqService


def make_assignment(index: int, value_name: str):
    type_row = SimpleNamespace(id=index, type_code=f"FAQ_TYPE_{index}", display_label=f"区分{index}", display_order=index)
    value_row = SimpleNamespace(id=index * 10, value_name=value_name)
    return SimpleNamespace(
        classification_type_id=index, classification_value_id=index * 10,
        classification_type=type_row, classification_value=value_row,
    )


def make_faq(faq_id: int = 1, *, question: str = "申請期限は？", answer: str = "8月末です。", chat_enabled: bool = True, version: int = 1):
    return SimpleNamespace(
        id=faq_id, question=question, answer=answer, chat_enabled=chat_enabled, version=version,
        created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, faq_id, 1, 2, tzinfo=timezone.utc),
        classification_assignments=[make_assignment(1, "奨学金"), make_assignment(4, "神楽坂")],
    )


@pytest.fixture
def mock_service():
    service = AsyncMock()
    app.dependency_overrides[get_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


def test_faq_filters_defaults_and_validation():
    filters = FaqFilters(keyword=" 期限 ")
    assert (filters.keyword, filters.sort, filters.order, filters.page, filters.page_size) == ("期限", "updated_at", "desc", 1, 10)
    assert FaqFilters(keyword="  ").keyword is None
    for size in (10, 20, 50, 100):
        assert FaqFilters(page_size=size).page_size == size
    for values in ({"sort": "question"}, {"order": "sideways"}, {"page_size": 5}):
        with pytest.raises(ValidationError):
            FaqFilters(**values)


def test_keyword_or_and_all_other_filters_are_and_conditions():
    filters = FaqFilters(
        keyword="申請", classification_1_value_id=10, classification_2_value_id=20,
        classification_3_value_id=30, classification_4_value_id=40, chat_enabled=True,
    )
    conditions = FaqRepository.conditions(filters, {f"FAQ_TYPE_{i}": i for i in range(1, 5)})
    assert len(conditions) == 6
    assert "faqs.question" in str(conditions[0]) and "faqs.answer" in str(conditions[0]) and " OR " in str(conditions[0])
    assert all("faq_similar_questions" not in str(condition) for condition in conditions)


@pytest.mark.anyio
async def test_list_serializes_dynamic_classifications_and_paging():
    repository = AsyncMock()
    repository.list.return_value = ([make_faq(2), make_faq(1)], 12, 2)
    result = await FaqService(repository).list(FaqFilters())
    assert result.total_count == 12 and result.total_pages == 2
    assert result.items[0].classifications[0].display_label == "区分1"
    assert result.items[0].classifications[1].value_name == "神楽坂"
    assert {item.type_code for item in result.items[0].classifications} == {"FAQ_TYPE_1", "FAQ_TYPE_4"}


@pytest.mark.anyio
async def test_zero_rows_and_page_not_found():
    repository = AsyncMock()
    repository.list.side_effect = [([], 0, 0), ([], 11, 2)]
    service = FaqService(repository)
    assert (await service.list(FaqFilters())).items == []
    with pytest.raises(FaqError, match="ページがありません") as error:
        await service.list(FaqFilters(page=3))
    assert error.value.code == "PAGE_NOT_FOUND"


@pytest.mark.anyio
async def test_each_classification_filter_is_validated_against_its_type():
    repository = AsyncMock()
    repository.resolve_value_type.side_effect = [1, 2, 3, 4]
    repository.list.return_value = ([], 0, 0)
    filters = FaqFilters(
        classification_1_value_id=10, classification_2_value_id=20,
        classification_3_value_id=30, classification_4_value_id=40,
    )
    await FaqService(repository).list(filters)
    assert repository.resolve_value_type.await_args_list[0].args == ("FAQ_TYPE_1", 10)
    assert repository.resolve_value_type.await_args_list[3].args == ("FAQ_TYPE_4", 40)


@pytest.mark.anyio
async def test_wrong_classification_value_is_422_domain_error():
    repository = AsyncMock()
    repository.resolve_value_type.return_value = None
    with pytest.raises(FaqError) as error:
        await FaqService(repository).list(FaqFilters(classification_1_value_id=999))
    assert error.value.code == "INVALID_FAQ_CLASSIFICATION"


@pytest.mark.anyio
async def test_single_delete_not_found_and_version_conflict():
    repository = AsyncMock()
    repository.get.side_effect = [None, make_faq()]
    repository.delete_one.return_value = False
    service = FaqService(repository)
    with pytest.raises(FaqError) as missing:
        await service.delete(99, 1)
    assert missing.value.code == "FAQ_NOT_FOUND"
    with pytest.raises(FaqError) as conflict:
        await service.delete(1, 9)
    assert conflict.value.code == "FAQ_VERSION_CONFLICT"


@pytest.mark.anyio
async def test_single_and_bulk_delete_delegate_atomic_repository_operations():
    repository = AsyncMock()
    repository.get.return_value = make_faq()
    repository.delete_one.return_value = True
    repository.bulk_delete.return_value = 2
    service = FaqService(repository)
    await service.delete(1, 1)
    payload = FaqBulkDeleteRequest(items=[FaqDeleteTarget(id=1, version=1), FaqDeleteTarget(id=2, version=2)])
    assert await service.bulk_delete(payload) == 2
    repository.bulk_delete.assert_awaited_once_with(payload.items)


@pytest.mark.anyio
@pytest.mark.parametrize("failure,code", [(LookupError("not_found"), "FAQ_NOT_FOUND"), (ValueError("version_mismatch"), "FAQ_VERSION_CONFLICT")])
async def test_bulk_delete_failure_is_reported_without_partial_success(failure, code):
    repository = AsyncMock()
    repository.bulk_delete.side_effect = failure
    payload = FaqBulkDeleteRequest(items=[FaqDeleteTarget(id=1, version=1)])
    with pytest.raises(FaqError) as error:
        await FaqService(repository).bulk_delete(payload)
    assert error.value.code == code


@pytest.mark.anyio
async def test_excel_uses_dynamic_labels_japanese_values_and_jst():
    repository = AsyncMock()
    repository.list.return_value = ([make_faq(chat_enabled=True), make_faq(2, chat_enabled=False)], 2, 1)
    content = await FaqService(repository).export_excel(FaqFilters(), {f"FAQ_TYPE_{i}": f"表示区分{i}" for i in range(1, 5)})
    sheet = load_workbook(BytesIO(content)).active
    assert [cell.value for cell in sheet[1]] == ["ID", "質問", "回答", "表示区分1", "表示区分2", "表示区分3", "表示区分4", "チャット利用", "更新日時"]
    assert sheet.cell(2, 4).value == "奨学金" and sheet.cell(2, 5).value is None
    assert sheet.cell(2, 8).value == "公開" and sheet.cell(3, 8).value == "非公開"
    assert sheet.cell(2, 9).value == "2026/08/01 10:02"


@pytest.mark.anyio
async def test_api_page_not_found_and_invalid_classification_codes(mock_service):
    for code in ("PAGE_NOT_FOUND", "INVALID_FAQ_CLASSIFICATION"):
        mock_service.list.side_effect = FaqError(code, "エラー")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/faqs")
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == code


@pytest.mark.anyio
async def test_api_delete_codes_and_empty_bulk_delete(mock_service):
    mock_service.delete.side_effect = FaqError("FAQ_VERSION_CONFLICT", "競合")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        conflict = await client.delete("/api/v1/faqs/1?version=1")
        empty = await client.post("/api/v1/faqs/bulk-delete", json={"items": []})
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "FAQ_VERSION_CONFLICT"
    assert empty.status_code == 422
    mock_service.bulk_delete.assert_not_awaited()


@pytest.mark.anyio
async def test_export_filename(mock_service):
    mock_service.repository.list_type_labels.return_value = {}
    mock_service.export_excel.return_value = b"xlsx"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/faqs/export")
    assert response.status_code == 200
    assert "faq" in response.headers["content-disposition"] and response.headers["content-disposition"].endswith(".xlsx")


def test_repository_uses_fixed_count_eager_loading_not_per_row_queries():
    source = FaqRepository.list.__code__.co_names
    assert "selectinload" in source
