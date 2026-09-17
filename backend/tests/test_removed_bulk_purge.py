import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.anyio
@pytest.mark.parametrize("method,path", [("POST", "/api/v1/maintenance/purge"), ("GET", "/api/v1/maintenance/capabilities")])
async def test_removed_bulk_purge_routes_return_404(method, path):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.request(method, path)
    assert response.status_code == 404
    assert path not in app.openapi()["paths"]
