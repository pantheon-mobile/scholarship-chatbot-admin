from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.anyio
async def test_health_endpoint():
    async_mock = AsyncMock()
    async_mock.__aenter__.return_value.execute = AsyncMock()

    with patch("app.api.v1.health.engine.connect", return_value=async_mock):
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
