from io import BytesIO
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook

from app.api.v1.data_source_types import get_service
from app.main import app
from app.services.classification_service import ClassificationService, DuplicateLabelError, DuplicateValueError


@pytest.fixture
def classification_type():
    value = type(
        "Value",
        (),
        {"id": 1, "value_name": "在学生", "display_order": 1, "version": 1},
    )()
    return type(
        "ClassificationType",
        (),
        {
            "id": 1,
            "type_code": "TYPE_1",
            "fixed_name": "種別1",
            "display_label": "対象者",
            "display_order": 1,
            "version": 1,
            "values": [value],
        },
    )()


@pytest.fixture
def service():
    mock = AsyncMock()
    app.dependency_overrides[get_service] = lambda: mock
    yield mock
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_list_data_source_types(service, classification_type):
    service.list_types.return_value = [classification_type]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/data-source-types")

    assert response.status_code == 200
    assert response.json()[0]["display_label"] == "対象者"


@pytest.mark.anyio
async def test_update_type_label(service, classification_type):
    service.update_type_label.return_value = classification_type

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/data-source-types/1",
            json={"display_label": "対象者", "version": 1},
        )

    assert response.status_code == 200
    service.update_type_label.assert_awaited_once()


@pytest.mark.anyio
async def test_duplicate_type_label_is_rejected_with_clear_message(service):
    service.update_type_label.side_effect = DuplicateLabelError()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/data-source-types/1",
            json={"display_label": "対象者", "version": 1},
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "同じラベル名が他の種別に既に設定されています。"


@pytest.mark.anyio
async def test_type_label_duplicate_is_checked_excluding_current_type():
    repository = AsyncMock()
    repository.get_type.return_value = type("Type", (), {"id": 1})()
    repository.display_label_exists.return_value = True
    with pytest.raises(DuplicateLabelError):
        await ClassificationService(repository).update_type_label(
            1, type("Payload", (), {"display_label": "対象者", "version": 1})()
        )
    repository.display_label_exists.assert_awaited_once_with("対象者", exclude_id=1)
    repository.update_type_label.assert_not_awaited()


@pytest.mark.anyio
async def test_duplicate_value_returns_422(service):
    service.add_value.side_effect = DuplicateValueError()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/data-source-types/1/values",
            json={"value_name": "在学生"},
        )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_duplicate_value_update_returns_clear_422_message(service):
    service.update_value.side_effect = DuplicateValueError()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch(
            "/api/v1/data-source-types/1/values/10",
            json={"value_name": "在学生", "version": 1},
        )
    assert response.status_code == 422
    assert response.json()["detail"] == "同じ種別内に同じ値が既に存在します。"


@pytest.mark.anyio
async def test_excel_uses_classification_label_name_header(classification_type):
    repository = AsyncMock()
    repository.list_types.return_value = [classification_type]

    content = await ClassificationService(repository).export_excel()
    rows = list(load_workbook(BytesIO(content)).active.values)

    assert rows == [
        ("種別", "種別ラベル名", "種別値"),
        ("種別1", "対象者", "在学生"),
    ]


@pytest.mark.anyio
async def test_export_route_is_not_captured_as_type_id(service):
    service.export_excel.return_value = b"xlsx"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/data-source-types/export")

    assert response.status_code == 200
    assert response.content == b"xlsx"
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
