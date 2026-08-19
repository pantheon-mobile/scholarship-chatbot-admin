from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook

from app.api.v1.faq_classifications import get_service
from app.main import app
from app.schemas.faq_classification import (
    FaqClassificationLabelUpdate,
    FaqClassificationOrderItem,
    FaqClassificationOrderUpdate,
    FaqClassificationValueCreate,
    FaqClassificationValueUpdate,
)
from app.services.faq_classification_service import FaqClassificationError, FaqClassificationService


def value(value_id: int, type_id: int, name: str, order: int, version: int = 1):
    return SimpleNamespace(
        id=value_id,
        classification_type_id=type_id,
        value_name=name,
        display_order=order,
        version=version,
    )


def classification_type(type_id: int, values=None, version: int = 1):
    return SimpleNamespace(
        id=type_id,
        type_code=f"FAQ_TYPE_{type_id}",
        fixed_name=f"区分{type_id}",
        display_label=f"区分{type_id}",
        display_order=type_id,
        version=version,
        values=values or [],
    )


@pytest.mark.anyio
async def test_four_fixed_types_can_have_zero_values():
    repository = AsyncMock()
    repository.list_types.return_value = [classification_type(index) for index in range(1, 5)]
    result = await FaqClassificationService(repository).list_types()
    assert [item.type_code for item in result] == ["FAQ_TYPE_1", "FAQ_TYPE_2", "FAQ_TYPE_3", "FAQ_TYPE_4"]
    assert [item.display_order for item in result] == [1, 2, 3, 4]
    assert all(item.values == [] for item in result)


@pytest.mark.anyio
async def test_label_update_trims_and_uses_version():
    repository = AsyncMock()
    repository.get_type.side_effect = [classification_type(1), classification_type(1, version=2)]
    repository.update_label.return_value = True
    result = await FaqClassificationService(repository).update_label(
        1, FaqClassificationLabelUpdate(display_label="  問合せ区分  ", version=1)
    )
    assert result.version == 2
    repository.update_label.assert_awaited_once_with(1, "問合せ区分", 1)
    repository.commit.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.parametrize(("label", "code"), [("  ", "FAQ_CLASSIFICATION_LABEL_REQUIRED")])
async def test_label_validation(label, code):
    repository = AsyncMock()
    repository.get_type.return_value = classification_type(1)
    with pytest.raises(FaqClassificationError) as caught:
        await FaqClassificationService(repository).update_label(
            1, FaqClassificationLabelUpdate(display_label=label, version=1)
        )
    assert caught.value.code == code
    repository.update_label.assert_not_awaited()


@pytest.mark.anyio
async def test_label_version_conflict_rolls_back():
    repository = AsyncMock()
    repository.get_type.return_value = classification_type(1)
    repository.update_label.return_value = False
    with pytest.raises(FaqClassificationError) as caught:
        await FaqClassificationService(repository).update_label(
            1, FaqClassificationLabelUpdate(display_label="問合せ区分", version=9)
        )
    assert caught.value.code == "FAQ_CLASSIFICATION_VERSION_CONFLICT"
    repository.rollback.assert_awaited_once()
    repository.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_value_add_trims_and_appends_to_type():
    repository = AsyncMock()
    repository.get_type.side_effect = [classification_type(1), classification_type(1, [value(10, 1, "奨学金", 1)])]
    repository.value_name_exists.return_value = False
    result = await FaqClassificationService(repository).add_value(
        1, FaqClassificationValueCreate(value_name="  奨学金  ")
    )
    assert result.values[0].display_order == 1
    repository.add_value.assert_awaited_once_with(1, "奨学金")
    repository.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_empty_and_same_type_duplicate_values_are_rejected():
    repository = AsyncMock()
    repository.get_type.return_value = classification_type(1)
    service = FaqClassificationService(repository)
    with pytest.raises(FaqClassificationError) as empty:
        await service.add_value(1, FaqClassificationValueCreate(value_name=" "))
    assert empty.value.code == "FAQ_CLASSIFICATION_VALUE_REQUIRED"
    repository.value_name_exists.return_value = True
    with pytest.raises(FaqClassificationError) as duplicate:
        await service.add_value(1, FaqClassificationValueCreate(value_name="同名"))
    assert duplicate.value.code == "FAQ_CLASSIFICATION_VALUE_DUPLICATE"


@pytest.mark.anyio
async def test_same_name_in_different_types_is_allowed():
    repository = AsyncMock()
    repository.get_type.side_effect = [classification_type(2), classification_type(2, [value(20, 2, "同名", 1)])]
    repository.value_name_exists.return_value = False
    await FaqClassificationService(repository).add_value(2, FaqClassificationValueCreate(value_name="同名"))
    repository.value_name_exists.assert_awaited_once_with(2, "同名")


@pytest.mark.anyio
async def test_value_update_and_delete_use_version():
    row = value(10, 1, "旧", 1)
    repository = AsyncMock()
    repository.get_type.return_value = classification_type(1, [row])
    repository.get_value.return_value = row
    repository.value_name_exists.return_value = False
    repository.update_value.return_value = True
    await FaqClassificationService(repository).update_value(
        1, 10, FaqClassificationValueUpdate(value_name=" 新 ", version=2)
    )
    repository.update_value.assert_awaited_once_with(1, 10, "新", 2)

    repository.delete_value.return_value = True
    await FaqClassificationService(repository).delete_value(1, 10, 3)
    repository.delete_value.assert_awaited_once_with(1, 10, 3)


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["update", "delete"])
async def test_value_version_conflict_rolls_back(operation):
    row = value(10, 1, "値", 1)
    repository = AsyncMock()
    repository.get_type.return_value = classification_type(1, [row])
    repository.get_value.return_value = row
    repository.value_name_exists.return_value = False
    setattr(repository, f"{operation}_value", AsyncMock(return_value=False))
    service = FaqClassificationService(repository)
    with pytest.raises(FaqClassificationError) as caught:
        if operation == "update":
            await service.update_value(1, 10, FaqClassificationValueUpdate(value_name="更新", version=9))
        else:
            await service.delete_value(1, 10, 9)
    assert caught.value.code == "FAQ_CLASSIFICATION_VALUE_VERSION_CONFLICT"
    repository.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_value_from_another_type_is_not_found():
    repository = AsyncMock()
    repository.get_type.return_value = classification_type(1)
    repository.get_value.return_value = value(20, 2, "別区分", 1)
    with pytest.raises(FaqClassificationError) as caught:
        await FaqClassificationService(repository).delete_value(1, 20, 1)
    assert caught.value.code == "FAQ_CLASSIFICATION_VALUE_NOT_FOUND"


@pytest.mark.anyio
@pytest.mark.parametrize(("repository_result", "code"), [
    (None, None),
    ("invalid_order", "INVALID_FAQ_CLASSIFICATION_ORDER"),
    ("cross_type", "CROSS_FAQ_CLASSIFICATION_REORDER_NOT_ALLOWED"),
    ("version_mismatch", "FAQ_CLASSIFICATION_VALUE_VERSION_CONFLICT"),
])
async def test_reorder_is_atomic_and_returns_defined_errors(repository_result, code):
    repository = AsyncMock()
    repository.get_type.return_value = classification_type(1, [value(10, 1, "A", 1), value(11, 1, "B", 1)])
    repository.reorder_values.return_value = repository_result
    payload = FaqClassificationOrderUpdate(items=[
        FaqClassificationOrderItem(id=11, version=1),
        FaqClassificationOrderItem(id=10, version=1),
    ])
    if code:
        with pytest.raises(FaqClassificationError) as caught:
            await FaqClassificationService(repository).reorder_values(1, payload)
        assert caught.value.code == code
        repository.rollback.assert_awaited_once()
        repository.commit.assert_not_awaited()
    else:
        await FaqClassificationService(repository).reorder_values(1, payload)
        repository.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_database_failure_rolls_back():
    repository = AsyncMock()
    repository.get_type.return_value = classification_type(1)
    repository.update_label.side_effect = RuntimeError("db error")
    with pytest.raises(RuntimeError):
        await FaqClassificationService(repository).update_label(
            1, FaqClassificationLabelUpdate(display_label="区分", version=1)
        )
    repository.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_excel_contains_empty_and_registered_types():
    repository = AsyncMock()
    repository.list_types.return_value = [
        classification_type(1),
        classification_type(2, [value(20, 2, "申請", 1)]),
    ]
    content = await FaqClassificationService(repository).export_excel()
    rows = list(load_workbook(BytesIO(content)).active.values)
    assert rows == [
        ("区分", "区分タイトル名", "区分値"),
        ("区分1", "区分1", None),
        ("区分2", "区分2", "申請"),
    ]


@pytest.mark.anyio
async def test_api_uses_machine_readable_error_and_export_filename():
    service = AsyncMock()
    app.dependency_overrides[get_service] = lambda: service
    try:
        service.update_label.side_effect = FaqClassificationError(
            "FAQ_CLASSIFICATION_VERSION_CONFLICT", "他の操作で情報が更新されています。再読み込みしてください。"
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.patch("/api/v1/faq-classifications/1", json={"display_label": "区分", "version": 1})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "FAQ_CLASSIFICATION_VERSION_CONFLICT"

        service.export_excel.return_value = b"xlsx"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/faq-classifications/export")
        assert response.status_code == 200
        assert response.headers["content-disposition"].startswith("attachment; filename=classification")
    finally:
        app.dependency_overrides.clear()
