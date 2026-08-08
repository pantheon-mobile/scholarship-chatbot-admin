from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.data_sources import get_service
from app.main import app
from app.schemas.data_source import WebsiteDataSourceUpdateRequest
from app.services.data_source_service import (
    DataSourceNotFoundError,
    DataSourceService,
    DataSourceVersionConflictError,
    WebsiteDataSourceRequiredError,
    WebsiteDataSourceUpdateError,
)


def website_row(*, version=2, url="https://old.example.com", title="奨学金情報"):
    type_row = SimpleNamespace(id=1, type_code="TYPE_1", display_label="対象者", display_order=1)
    value_row = SimpleNamespace(id=10, value_name="在学生")
    link = SimpleNamespace(
        classification_type_id=1, classification_value_id=10,
        classification_type=type_row, classification_value=value_row,
    )
    return SimpleNamespace(
        id=1, source_type="WEB", title=title, format="Web", status="AVAILABLE",
        category_name="既存カテゴリ", size_bytes=None, character_count=4321,
        answer_source_enabled=True, priority="LOW", reference_link_visible=True,
        updated_at=datetime(2026, 8, 6, tzinfo=timezone.utc), version=version, file=None,
        website=SimpleNamespace(url=url, last_fetched_at=datetime(2026, 8, 5, tzinfo=timezone.utc)),
        classification_links=[link],
    )


def file_row():
    row = website_row()
    row.source_type = "FILE"
    row.website = None
    row.file = SimpleNamespace(file_name="guide.pdf")
    return row


def payload(**values):
    return WebsiteDataSourceUpdateRequest(
        url=values.get("url", "https://new.example.com"),
        title=values.get("title", "更新タイトル"),
        type_1_value_id=values.get("type_1_value_id", 10),
        type_2_value_id=values.get("type_2_value_id"),
        type_3_value_id=values.get("type_3_value_id"),
        priority=values.get("priority", "HIGH"),
        answer_source_enabled=values.get("answer_source_enabled", False),
        reference_link_visible=values.get("reference_link_visible", False),
        version=values.get("version", 2),
    )


@pytest.mark.anyio
async def test_web_detail_and_attribute_update_return_complete_new_row():
    repository = AsyncMock()
    before = website_row()
    after = website_row(version=3, url="https://new.example.com", title="更新タイトル")
    after.priority = "HIGH"
    after.answer_source_enabled = False
    after.reference_link_visible = False
    repository.get.side_effect = [before, after]
    repository.resolve_classification_value.return_value = (1, 10)
    repository.update_website_attributes.return_value = True
    request = payload()
    result = await DataSourceService(repository).update_website_attributes(1, request)
    assert result.website.url == "https://new.example.com"
    assert result.title == "更新タイトル"
    assert result.version == 3
    assert result.status == "AVAILABLE"
    assert result.category_name == "既存カテゴリ"
    assert result.character_count == 4321
    repository.update_website_attributes.assert_awaited_once_with(
        1, request, url="https://new.example.com", title="更新タイトル", classifications=[(1, 10)]
    )


@pytest.mark.parametrize("url", ["http://example.com", "https://example.com/path"])
@pytest.mark.anyio
async def test_http_https_and_trim_are_allowed(url):
    repository = AsyncMock()
    repository.get.side_effect = [website_row(), website_row(version=3, url=url)]
    repository.resolve_classification_value.return_value = (1, 10)
    repository.update_website_attributes.return_value = True
    await DataSourceService(repository).update_website_attributes(1, payload(url=f"  {url}  "))
    assert repository.update_website_attributes.await_args.kwargs["url"] == url


@pytest.mark.parametrize("url", [
    "", "   ", "ftp://example.com", "file:///tmp/a", "javascript:alert(1)",
    "data:text/plain,a", "mailto:test@example.com", "/relative", "https:///missing-host",
])
@pytest.mark.anyio
async def test_invalid_urls_are_rejected(url):
    repository = AsyncMock()
    repository.get.return_value = website_row()
    with pytest.raises(WebsiteDataSourceUpdateError) as exc:
        await DataSourceService(repository).update_website_attributes(1, payload(url=url))
    assert exc.value.code == ("URL_REQUIRED" if not url.strip() else "INVALID_URL")


@pytest.mark.anyio
async def test_title_fallback_boundary_and_classification_clear():
    repository = AsyncMock()
    after = website_row(version=3, url="https://new.example.com", title="https://new.example.com")
    after.classification_links = []
    repository.get.side_effect = [website_row(), after]
    repository.update_website_attributes.return_value = True
    request = payload(title="   ", type_1_value_id=None)
    result = await DataSourceService(repository).update_website_attributes(1, request)
    assert result.title == "https://new.example.com"
    repository.update_website_attributes.assert_awaited_once_with(
        1, request, url="https://new.example.com", title="https://new.example.com", classifications=[]
    )

    repository.get.return_value = website_row()
    repository.get.side_effect = None
    repository.resolve_classification_value.return_value = (1, 10)
    repository.update_website_attributes.return_value = True
    await DataSourceService(repository).update_website_attributes(1, payload(title="a" * 500))
    with pytest.raises(WebsiteDataSourceUpdateError) as exc:
        await DataSourceService(repository).update_website_attributes(1, payload(title="a" * 501))
    assert exc.value.code == "TITLE_TOO_LONG"


@pytest.mark.anyio
async def test_priority_classification_file_and_not_found_errors():
    repository = AsyncMock()
    repository.get.return_value = website_row()
    with pytest.raises(WebsiteDataSourceUpdateError) as exc:
        await DataSourceService(repository).update_website_attributes(1, payload(priority="URGENT"))
    assert exc.value.code == "INVALID_PRIORITY"
    repository.resolve_classification_value.return_value = None
    with pytest.raises(WebsiteDataSourceUpdateError) as exc:
        await DataSourceService(repository).update_website_attributes(1, payload(type_1_value_id=999))
    assert exc.value.code == "INVALID_CLASSIFICATION"
    repository.get.return_value = file_row()
    with pytest.raises(WebsiteDataSourceRequiredError):
        await DataSourceService(repository).update_website_attributes(1, payload())
    repository.get.return_value = None
    with pytest.raises(DataSourceNotFoundError):
        await DataSourceService(repository).update_website_attributes(999, payload())


@pytest.mark.anyio
async def test_version_conflict_and_update_failure_rollback():
    repository = AsyncMock()
    repository.get.return_value = website_row()
    repository.resolve_classification_value.return_value = (1, 10)
    repository.update_website_attributes.return_value = False
    with pytest.raises(DataSourceVersionConflictError):
        await DataSourceService(repository).update_website_attributes(1, payload(version=99))
    repository.update_website_attributes.side_effect = RuntimeError("db failure")
    with pytest.raises(WebsiteDataSourceUpdateError) as exc:
        await DataSourceService(repository).update_website_attributes(1, payload())
    assert exc.value.code == "WEB_DATA_SOURCE_UPDATE_FAILED"
    repository.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_update_api_error_codes():
    service = AsyncMock()
    app.dependency_overrides[get_service] = lambda: service
    body = payload().model_dump()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            service.update_website_attributes.side_effect = WebsiteDataSourceRequiredError()
            response = await client.put("/api/v1/data-sources/1", json=body)
            assert response.status_code == 422
            assert response.json()["detail"]["code"] == "WEB_DATA_SOURCE_REQUIRED"
            service.update_website_attributes.side_effect = DataSourceVersionConflictError()
            response = await client.put("/api/v1/data-sources/1", json=body)
            assert response.status_code == 409
            assert response.json()["detail"]["code"] == "VERSION_CONFLICT"
            service.update_website_attributes.side_effect = WebsiteDataSourceUpdateError("INVALID_URL", "正しいURLを入力してください。")
            response = await client.put("/api/v1/data-sources/1", json=body)
            assert response.status_code == 422
            assert response.json()["detail"]["code"] == "INVALID_URL"
    finally:
        app.dependency_overrides.clear()
