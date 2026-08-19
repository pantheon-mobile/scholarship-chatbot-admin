from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import analytics as analytics_api
from app.api.v1 import dashboard as dashboard_api
from app.main import app
from app.services.analytics_service import AnalyticsError
from app.services.dashboard_service import DashboardError


@pytest.fixture
def analytics_service():
    service = AsyncMock()
    app.dependency_overrides[analytics_api.get_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_access_api_contract_and_plaintext_body_rejection(analytics_service):
    event_id, visitor_id = uuid4(), uuid4()
    now = datetime(2026, 8, 19, tzinfo=timezone.utc)
    analytics_service.record_access.return_value = SimpleNamespace(
        id=event_id, visitor_id=visitor_id, accessed_at=now, recorded_at=now,
    )
    payload = {
        "id": str(event_id),
        "identity": {"identity_kind": "ANONYMOUS", "identifier": str(uuid4())},
        "accessed_at": now.isoformat(),
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/analytics/accesses", json=payload)
        rejected = await client.post("/api/v1/analytics/accesses", json={**payload, "question": "保存禁止"})
    assert response.status_code == 201 and response.json()["id"] == str(event_id)
    assert rejected.status_code == 422


@pytest.mark.anyio
async def test_analytics_domain_error_codes(analytics_service):
    analytics_service.record_access.side_effect = AnalyticsError("IDEMPOTENCY_CONFLICT", "競合")
    payload = {
        "id": str(uuid4()),
        "identity": {"identity_kind": "ANONYMOUS", "identifier": str(uuid4())},
        "accessed_at": datetime(2026, 8, 19, tzinfo=timezone.utc).isoformat(),
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/analytics/accesses", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"


@pytest.mark.anyio
async def test_dashboard_invalid_date_range_api_contract():
    service = AsyncMock()
    service.get.side_effect = DashboardError("INVALID_DATE_RANGE", "開始日は終了日以前を指定してください。")
    app.dependency_overrides[dashboard_api.get_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/dashboard?from=2026-08-20&to=2026-08-19")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "INVALID_DATE_RANGE", "message": "開始日は終了日以前を指定してください。",
    }
    service.get.assert_awaited_once_with(date(2026, 8, 20), date(2026, 8, 19))
