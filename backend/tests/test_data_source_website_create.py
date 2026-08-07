from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.data_sources import get_service
from app.main import app
from app.schemas.data_source import WebsiteDataSourceCreateRequest
from app.services.data_source_service import DataSourceService, WebsiteDataSourceCreateError


def website_row(*, data_source_id: int = 1, url: str = "https://example.com", title: str = "案内"):
    return SimpleNamespace(
        id=data_source_id, source_type="WEB", title=title, format="Web", status="PREPARING",
        category_name=None, size_bytes=None, character_count=None,
        answer_source_enabled=True, priority="MEDIUM", reference_link_visible=True,
        updated_at=datetime.now(timezone.utc), version=1, file=None,
        website=SimpleNamespace(url=url, last_fetched_at=None), classification_links=[],
    )


def payload(**values):
    return WebsiteDataSourceCreateRequest(
        url=values.get("url", "https://example.com/scholarship"),
        title=values.get("title", "奨学金案内"),
        type_1_value_id=values.get("type_1_value_id"),
        type_2_value_id=values.get("type_2_value_id"),
        type_3_value_id=values.get("type_3_value_id"),
        priority=values.get("priority", "MEDIUM"),
        answer_source_enabled=values.get("answer_source_enabled", True),
        reference_link_visible=values.get("reference_link_visible", True),
    )


@pytest.mark.anyio
async def test_create_website_source_with_all_settings_and_classifications():
    repository = AsyncMock()
    repository.resolve_classification_value.side_effect = [(1, 10), (2, 20), (3, 30)]
    repository.create_website_source.return_value = 7
    row = website_row(data_source_id=7, url="https://example.com/scholarship", title="奨学金案内")
    row.answer_source_enabled = False
    row.priority = "HIGH"
    row.reference_link_visible = False
    repository.get.return_value = row
    request = payload(
        type_1_value_id=10, type_2_value_id=20, type_3_value_id=30,
        priority="HIGH", answer_source_enabled=False, reference_link_visible=False,
    )
    result = await DataSourceService(repository).create_website_source(request)
    assert result.source_type == "WEB"
    assert result.status == "PREPARING"
    assert result.category_name is None
    assert result.size_bytes is None
    assert result.character_count is None
    assert result.website.url == "https://example.com/scholarship"
    assert result.version == 1
    repository.create_website_source.assert_awaited_once_with(
        url="https://example.com/scholarship", title="奨学金案内", priority="HIGH",
        answer_source_enabled=False, reference_link_visible=False,
        classifications=[(1, 10), (2, 20), (3, 30)],
    )
    repository.commit.assert_awaited_once()


@pytest.mark.parametrize("url", ["http://example.com", "https://example.com/path?q=1#part"])
@pytest.mark.anyio
async def test_http_and_https_are_allowed(url):
    repository = AsyncMock()
    repository.create_website_source.return_value = 1
    repository.get.return_value = website_row(url=url, title=url)
    result = await DataSourceService(repository).create_website_source(payload(url=f"  {url}  ", title="   "))
    assert result.website.url == url
    repository.create_website_source.assert_awaited_once_with(
        url=url, title=url, priority="MEDIUM", answer_source_enabled=True,
        reference_link_visible=True, classifications=[],
    )


@pytest.mark.parametrize("url", [
    "", "   ", "ftp://example.com", "file:///tmp/a", "javascript:alert(1)",
    "data:text/plain,a", "mailto:test@example.com", "/relative/path", "https:///missing-host",
    "https://exa mple.com", "https://example.com:invalid",
])
@pytest.mark.anyio
async def test_invalid_urls_are_rejected(url):
    repository = AsyncMock()
    with pytest.raises(WebsiteDataSourceCreateError) as exc:
        await DataSourceService(repository).create_website_source(payload(url=url))
    assert exc.value.code == ("URL_REQUIRED" if not url.strip() else "INVALID_URL")
    repository.create_website_source.assert_not_awaited()


@pytest.mark.anyio
async def test_title_boundary_and_fallback_to_url():
    repository = AsyncMock()
    repository.create_website_source.return_value = 1
    row = website_row(title="a" * 500)
    repository.get.return_value = row
    await DataSourceService(repository).create_website_source(payload(title="a" * 500))
    assert repository.create_website_source.await_args.kwargs["title"] == "a" * 500
    with pytest.raises(WebsiteDataSourceCreateError) as exc:
        await DataSourceService(repository).create_website_source(payload(title="a" * 501))
    assert exc.value.code == "TITLE_TOO_LONG"


@pytest.mark.anyio
async def test_invalid_priority_and_classification_are_rejected():
    repository = AsyncMock()
    with pytest.raises(WebsiteDataSourceCreateError) as exc:
        await DataSourceService(repository).create_website_source(payload(priority="URGENT"))
    assert exc.value.code == "INVALID_PRIORITY"
    repository.resolve_classification_value.return_value = None
    with pytest.raises(WebsiteDataSourceCreateError) as exc:
        await DataSourceService(repository).create_website_source(payload(type_1_value_id=999))
    assert exc.value.code == "INVALID_CLASSIFICATION"


@pytest.mark.anyio
async def test_duplicate_url_is_registered_as_another_data_source():
    repository = AsyncMock()
    repository.create_website_source.side_effect = [1, 2]
    repository.get.side_effect = [website_row(data_source_id=1), website_row(data_source_id=2)]
    service = DataSourceService(repository)
    await service.create_website_source(payload())
    await service.create_website_source(payload())
    assert repository.create_website_source.await_count == 2


@pytest.mark.anyio
async def test_create_failure_rolls_back():
    repository = AsyncMock()
    repository.create_website_source.side_effect = RuntimeError("db failure")
    with pytest.raises(WebsiteDataSourceCreateError) as exc:
        await DataSourceService(repository).create_website_source(payload())
    assert exc.value.code == "WEB_DATA_SOURCE_CREATE_FAILED"
    repository.rollback.assert_awaited_once()
    repository.commit.assert_not_awaited()


@pytest.mark.anyio
async def test_api_returns_machine_readable_errors():
    service = AsyncMock()
    service.create_website_source.side_effect = WebsiteDataSourceCreateError("INVALID_URL", "正しいURLを入力してください。")
    app.dependency_overrides[get_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/data-sources/websites", json=payload().model_dump())
        assert response.status_code == 422
        assert response.json()["detail"] == {"code": "INVALID_URL", "message": "正しいURLを入力してください。"}

        service.create_website_source.side_effect = WebsiteDataSourceCreateError("WEB_DATA_SOURCE_CREATE_FAILED", "Webサイトの追加に失敗しました。")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/data-sources/websites", json=payload().model_dump())
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_api_missing_url_uses_url_required_code():
    service = DataSourceService(AsyncMock())
    app.dependency_overrides[get_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/v1/data-sources/websites", json={})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert response.json()["detail"] == {"code": "URL_REQUIRED", "message": "URLを入力してください。"}
