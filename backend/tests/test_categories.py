from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook

from app.api.v1.categories import get_service
from app.main import app
from app.schemas.category import CategoryDeleteTarget, CategoryOrderRequest
from app.services.category_service import (
    CategoryNotFoundError,
    CategoryService,
    CategoryVersionConflictError,
    CrossParentReorderError,
    DuplicateCategoryNameError,
    InvalidCategoryOrderError,
)


NOW = datetime(2026, 8, 18, 1, 0, tzinfo=timezone.utc)


def category(category_id: int, name: str, parent_id: int | None, order: int, version: int = 1):
    return SimpleNamespace(
        id=category_id,
        name=name,
        parent_id=parent_id,
        display_order=order,
        version=version,
        created_at=NOW,
        updated_at=NOW,
    )


TREE = [
    category(1, "全般", None, 1),
    category(2, "給付", None, 2),
    category(3, "申請", 1, 1),
    category(4, "継続", 1, 2),
    category(5, "新規", 3, 1),
]


@pytest.mark.anyio
async def test_empty_and_tree_list_has_children_without_n_plus_one():
    repository = AsyncMock()
    repository.list_all.side_effect = [[], TREE]
    service = CategoryService(repository)
    assert await service.list_categories() == []
    result = await service.list_categories()
    assert [(row.id, row.has_children) for row in result] == [(1, True), (2, False), (3, True), (4, False), (5, False)]
    assert repository.list_all.await_count == 2


@pytest.mark.anyio
async def test_service_trims_name_and_rejects_duplicate_within_same_parent():
    repository = AsyncMock()
    repository.name_exists.side_effect = [False, True]
    service = CategoryService(repository)
    assert await service.validate_name_available(" 申請 ", 1) == "申請"
    repository.name_exists.assert_awaited_with(1, "申請", exclude_id=None)
    with pytest.raises(DuplicateCategoryNameError):
        await service.validate_name_available("申請", 1)
    with pytest.raises(ValueError, match="invalid_category_name"):
        service.normalize_name(" " * 3)


@pytest.mark.anyio
async def test_delete_leaf_and_descendants_are_one_transaction():
    repository = AsyncMock()
    repository.list_all.return_value = TREE
    service = CategoryService(repository)
    await service.delete(2, 1)
    repository.delete_ids.assert_awaited_once_with({2})
    await service.delete(1, 1)
    repository.delete_ids.assert_awaited_with({1, 3, 4, 5})
    assert repository.commit.await_count == 2


@pytest.mark.anyio
async def test_delete_not_found_and_version_conflict_roll_back():
    repository = AsyncMock()
    repository.list_all.return_value = TREE
    service = CategoryService(repository)
    with pytest.raises(CategoryNotFoundError):
        await service.delete(999, 1)
    with pytest.raises(CategoryVersionConflictError):
        await service.delete(1, 99)
    assert repository.rollback.await_count == 2
    repository.delete_ids.assert_not_awaited()


@pytest.mark.anyio
async def test_bulk_delete_deduplicates_parent_and_child_and_counts_descendants():
    repository = AsyncMock()
    repository.list_all.return_value = TREE
    result = await CategoryService(repository).bulk_delete([
        CategoryDeleteTarget(id=1, version=1),
        CategoryDeleteTarget(id=3, version=1),
    ])
    assert result == 4
    repository.delete_ids.assert_awaited_once_with({1, 3, 4, 5})
    repository.commit.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.parametrize("targets,error_type", [
    ([CategoryDeleteTarget(id=999, version=1)], CategoryNotFoundError),
    ([CategoryDeleteTarget(id=1, version=9)], CategoryVersionConflictError),
])
async def test_bulk_delete_failure_rolls_back_all(targets, error_type):
    repository = AsyncMock()
    repository.list_all.return_value = TREE
    with pytest.raises(error_type):
        await CategoryService(repository).bulk_delete(targets)
    repository.rollback.assert_awaited_once()
    repository.delete_ids.assert_not_awaited()
    repository.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_reorder_same_parent_and_root_return_updated_siblings():
    updated_children = [category(4, "継続", 1, 1, 2), category(3, "申請", 1, 2, 2)]
    repository = AsyncMock()
    repository.list_all.side_effect = [TREE, [*TREE[:2], *updated_children, TREE[4]]]
    result = await CategoryService(repository).reorder(CategoryOrderRequest(
        parent_id=1,
        items=[CategoryDeleteTarget(id=4, version=1), CategoryDeleteTarget(id=3, version=1)],
    ))
    repository.reorder.assert_awaited_once()
    repository.commit.assert_awaited_once()
    assert [(row.id, row.display_order, row.version) for row in result] == [(4, 1, 2), (3, 2, 2)]


@pytest.mark.anyio
async def test_root_reorder_response_keeps_has_children_from_full_tree():
    updated = [category(2, "給付", None, 1, 2), category(1, "全般", None, 2, 2), *TREE[2:]]
    repository = AsyncMock()
    repository.list_all.side_effect = [TREE, updated]
    result = await CategoryService(repository).reorder(CategoryOrderRequest(
        parent_id=None,
        items=[CategoryDeleteTarget(id=2, version=1), CategoryDeleteTarget(id=1, version=1)],
    ))
    assert [(row.id, row.has_children) for row in result] == [(2, False), (1, True)]


@pytest.mark.anyio
async def test_reorder_rejects_cross_parent_invalid_set_and_version():
    repository = AsyncMock()
    repository.list_all.return_value = TREE
    service = CategoryService(repository)
    with pytest.raises(CrossParentReorderError):
        await service.reorder(CategoryOrderRequest(parent_id=1, items=[
            CategoryDeleteTarget(id=3, version=1), CategoryDeleteTarget(id=2, version=1),
        ]))
    with pytest.raises(InvalidCategoryOrderError):
        await service.reorder(CategoryOrderRequest(parent_id=1, items=[CategoryDeleteTarget(id=3, version=1)]))
    with pytest.raises(CategoryVersionConflictError):
        await service.reorder(CategoryOrderRequest(parent_id=1, items=[
            CategoryDeleteTarget(id=3, version=9), CategoryDeleteTarget(id=4, version=1),
        ]))
    assert repository.rollback.await_count == 3


def test_cycle_validation_rejects_self_and_descendant_parent():
    with pytest.raises(ValueError, match="category_cycle"):
        CategoryService.validate_parent_change(1, 1, TREE)
    with pytest.raises(ValueError, match="category_cycle"):
        CategoryService.validate_parent_change(1, 5, TREE)
    CategoryService.validate_parent_change(3, 2, TREE)


@pytest.mark.anyio
async def test_excel_uses_tree_order_and_variable_depth():
    repository = AsyncMock()
    repository.list_all.return_value = TREE
    content = await CategoryService(repository).export_excel()
    worksheet = load_workbook(BytesIO(content)).active
    assert list(worksheet.values) == [
        ("ID", "カテゴリ1", "カテゴリ2", "カテゴリ3"),
        (1, "全般", None, None),
        (3, "全般", "申請", None),
        (5, "全般", "申請", "新規"),
        (4, "全般", "継続", None),
        (2, "給付", None, None),
    ]


@pytest.fixture
def api_service():
    service = AsyncMock()
    app.dependency_overrides[get_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_api_list_and_empty_bulk_delete(api_service):
    api_service.list_categories.return_value = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/categories")
        empty = await client.post("/api/v1/categories/bulk-delete", json={"items": []})
    assert response.json() == {"items": []}
    assert empty.status_code == 422
    assert empty.json()["detail"]["code"] == "EMPTY_CATEGORY_SELECTION"


@pytest.mark.anyio
async def test_api_delete_error_codes(api_service):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        api_service.delete.side_effect = CategoryNotFoundError()
        missing = await client.delete("/api/v1/categories/1?version=1")
        api_service.delete.side_effect = CategoryVersionConflictError()
        conflict = await client.delete("/api/v1/categories/1?version=1")
    assert (missing.status_code, missing.json()["detail"]["code"]) == (404, "CATEGORY_NOT_FOUND")
    assert (conflict.status_code, conflict.json()["detail"]["code"]) == (409, "CATEGORY_VERSION_CONFLICT")


@pytest.mark.anyio
async def test_api_reorder_error_codes(api_service):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        api_service.reorder.side_effect = InvalidCategoryOrderError()
        invalid = await client.patch("/api/v1/categories/order", json={"parent_id": None, "items": [{"id": 1, "version": 1}]})
        api_service.reorder.side_effect = CrossParentReorderError()
        cross = await client.patch("/api/v1/categories/order", json={"parent_id": None, "items": [{"id": 1, "version": 1}]})
    assert invalid.json()["detail"]["code"] == "INVALID_CATEGORY_ORDER"
    assert cross.json()["detail"]["code"] == "CROSS_PARENT_REORDER_NOT_ALLOWED"


@pytest.mark.anyio
async def test_export_filename_uses_category_timestamp(api_service):
    api_service.export_excel.return_value = b"xlsx"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/categories/export")
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment; filename=category")
    assert disposition.endswith(".xlsx")
