from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import quote

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.db import get_db
from app.api.v1.auth import require_authenticated_session
from app.api.v1.data_sources import get_storage
from app.schemas.chat import ChatCitation
from app.services.chat_service import ChatService
from app.services.chat_citation_service import resolve_chat_citations
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


def source(**kwargs):
    values = dict(id=7, source_type="FILE", title="第一種奨学金の返還案内", reference_link_visible=True,
                  answer_source_enabled=True, file=SimpleNamespace(storage_key="original.pdf", file_name="返還案内.pdf"), website=None)
    return SimpleNamespace(**(values | kwargs))


def db_for(*rows):
    session = AsyncMock()
    result = Mock()
    result.scalars.return_value.all.return_value = list(rows)
    result.scalar_one_or_none.return_value = rows[0] if rows else None
    session.execute.return_value = result
    return session


@pytest.mark.anyio
async def test_resolve_current_title_original_file_and_unique_sources():
    result = await resolve_chat_citations(db_for(source()), [
        ChatCitation(title="旧タイトル", data_source_id=7, uri="s3://bucket/chunk1.md"),
        ChatCitation(title="旧タイトル", data_source_id=7, uri="s3://bucket/chunk2.md"),
    ])
    assert len(result) == 1
    assert result[0].title == "第一種奨学金の返還案内"
    assert result[0].uri == "/api/v1/chat/sources/7/download"


@pytest.mark.anyio
@pytest.mark.parametrize("rows", [[], [source(reference_link_visible=False)], [source(answer_source_enabled=False)]])
async def test_resolve_omits_unavailable_sources(rows):
    assert await resolve_chat_citations(db_for(*rows), [ChatCitation(title="旧", data_source_id=7)]) == []


@pytest.mark.anyio
async def test_web_citation_uses_cited_page_and_current_title():
    row = source(source_type="WEB", file=None, website=SimpleNamespace(url="https://example.com/"))
    result = await resolve_chat_citations(db_for(row), [ChatCitation(title="旧", data_source_id=7, uri="https://example.com/guide")])
    assert result[0].uri == "https://example.com/guide"
    assert result[0].title == row.title


def test_managed_source_uses_db_visibility_even_when_metadata_is_stale():
    result = ChatService._citations({"citations": [{"retrievedReferences": [{
        "location": {"s3Location": {"uri": "s3://bucket/chunk.md"}},
        "metadata": {"datasource_id": "7", "reference_link_visible": False, "source_url": "https://example.com/guide"},
    }]}]})
    assert result[0].data_source_id == 7
    assert result[0].uri == "https://example.com/guide"


@pytest.mark.anyio
@pytest.mark.parametrize("uri", ["javascript:alert(1)", "s3://bucket/key", "file:///etc/passwd", "//example.com/file"])
async def test_legacy_citations_do_not_expose_unsafe_uris(uri):
    result = await resolve_chat_citations(db_for(), [ChatCitation(title="資料", uri=uri)])
    assert result[0].uri is None


@pytest.fixture
def download_setup(tmp_path):
    storage = LocalStorage(tmp_path)
    (tmp_path / "original.pdf").write_bytes(b"%PDF-1.7 original bytes")
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_db] = lambda: db_for(source())
    yield storage
    app.dependency_overrides.pop(get_storage, None)
    app.dependency_overrides.pop(get_db, None)


@pytest.mark.anyio
async def test_staff_download_gets_original_bytes_and_japanese_filename(download_setup):
    app.dependency_overrides[require_authenticated_session] = lambda: SimpleNamespace(role="staff", subject="staff", site="faculty")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/chat/sources/7/download")
    assert response.status_code == 200
    assert response.content == b"%PDF-1.7 original bytes"
    assert response.headers["content-disposition"] == "attachment; filename*=UTF-8''" + quote("返還案内.pdf", safe="")
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.anyio
async def test_download_requires_authentication(download_setup):
    app.dependency_overrides.pop(require_authenticated_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/chat/sources/7/download")
    assert response.status_code == 401


@pytest.mark.anyio
@pytest.mark.parametrize("row", [None, source(reference_link_visible=False), source(answer_source_enabled=False), source(file=None)])
async def test_download_rejects_unavailable_sources(download_setup, row):
    app.dependency_overrides[get_db] = lambda: db_for(*([row] if row else []))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/chat/sources/7/download")
    assert response.status_code == 404


@pytest.mark.anyio
async def test_missing_original_returns_404(download_setup, tmp_path):
    (tmp_path / "original.pdf").unlink()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/chat/sources/7/download")
    assert response.status_code == 404


def test_s3_download_streams_and_closes_body():
    storage = object.__new__(S3Storage)
    storage.bucket = "bucket"
    storage.prefix = "originals/"
    storage.client = Mock()
    body = Mock()
    body.iter_chunks.return_value = iter([b"one", b"two"])
    storage.client.get_object.return_value = {"Body": body}
    assert b"".join(storage.iter_read("originals/guide.pdf")) == b"onetwo"
    storage.client.get_object.assert_called_once_with(Bucket="bucket", Key="originals/guide.pdf")
    body.close.assert_called_once()


@pytest.mark.anyio
async def test_original_from_another_storage_backend_returns_404(download_setup):
    row = source(file=SimpleNamespace(storage_key="documents/admin/originals/source.pdf", file_name="source.pdf"))
    app.dependency_overrides[get_db] = lambda: db_for(row)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/chat/sources/7/download")
    assert response.status_code == 404


def test_public_citations_remain_compatible_with_history_completion_schema():
    from app.schemas.chat import ChatMessageResponse
    from app.schemas.analytics import InteractionCompletionRequest
    response = ChatMessageResponse(answer="回答", answer_type="GENERATED_AI", citations=[
        ChatCitation(title="返還案内", data_source_id=7, uri="/api/v1/chat/sources/7/download"),
    ])
    public_citations = response.model_dump()["citations"]
    assert "data_source_id" not in public_citations[0]
    payload = InteractionCompletionRequest.model_validate({
        "processing_status": "COMPLETED", "answer_type": "GENERATED_AI",
        "answer_displayed_at": "2026-09-15T12:00:00Z", "answer_text": response.answer,
        "citations": public_citations,
    })
    assert payload.citations[0]["uri"] == "/api/v1/chat/sources/7/download"

@pytest.mark.anyio
@pytest.mark.parametrize("status", ["AVAILABLE", "PREPARING", "TRAINING", "ERROR"])
async def test_admin_original_download_independent_of_chat_flags(download_setup, status):
    app.dependency_overrides[get_db] = lambda: db_for(source(
        status=status, reference_link_visible=False, answer_source_enabled=False))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/data-sources/7/download")
    assert response.status_code == 200
    assert response.content == b"%PDF-1.7 original bytes"
    assert response.headers["content-disposition"] == "attachment; filename*=UTF-8''" + quote("返還案内.pdf", safe="")


@pytest.mark.anyio
@pytest.mark.parametrize("role,expected", [("staff", 403), (None, 401)])
async def test_admin_original_download_requires_admin(download_setup, role, expected):
    if role:
        app.dependency_overrides[require_authenticated_session] = lambda: SimpleNamespace(role=role, subject="staff", site="faculty")
    else:
        app.dependency_overrides.pop(require_authenticated_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/data-sources/7/download")
    assert response.status_code == expected


@pytest.mark.anyio
async def test_admin_original_missing_returns_404(download_setup, tmp_path):
    (tmp_path / "original.pdf").unlink()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/data-sources/7/download")
    assert response.status_code == 404
