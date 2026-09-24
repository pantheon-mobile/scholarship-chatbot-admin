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
async def test_access_api_contract_and_plaintext_body_rejection(analytics_service, signed_access):
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
        response = await client.post("/api/v1/analytics/accesses", **signed_access(payload))
        rejected = await client.post("/api/v1/analytics/accesses", **signed_access({**payload, "question": "保存禁止"}))
    assert response.status_code == 201 and response.json()["id"] == str(event_id)
    assert rejected.status_code == 422


@pytest.mark.anyio
async def test_analytics_domain_error_codes(analytics_service, signed_access):
    analytics_service.record_access.side_effect = AnalyticsError("IDEMPOTENCY_CONFLICT", "競合")
    payload = {
        "id": str(uuid4()),
        "identity": {"identity_kind": "ANONYMOUS", "identifier": str(uuid4())},
        "accessed_at": datetime(2026, 8, 19, tzinfo=timezone.utc).isoformat(),
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/analytics/accesses", **signed_access(payload))
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


@pytest.mark.anyio
async def test_access_requires_server_signature_and_derives_surface(analytics_service, signed_access):
    now = datetime.now(timezone.utc)
    payload = {'id': str(uuid4()), 'identity': {'identity_kind': 'AUTHENTICATED', 'identifier': 'forged'}, 'accessed_at': now.isoformat(), 'surface': 'ADMIN'}
    analytics_service.record_access.return_value = SimpleNamespace(id=uuid4(), visitor_id=uuid4(), accessed_at=now, recorded_at=now)
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.post('/api/v1/analytics/accesses', json=payload)).status_code == 403
        valid = signed_access(payload, '/chat')
        assert (await client.post('/api/v1/analytics/accesses', **valid)).status_code == 201
        assert analytics_service.record_access.call_args.args[0].surface == 'CHAT'
        assert analytics_service.record_access.call_args.args[0].identity.identifier == 'faculty:test-admin'
        altered = signed_access(payload, '/chat')
        altered['headers']['X-Access-Page'] = '/usage'
        assert (await client.post('/api/v1/analytics/accesses', **altered)).status_code == 403
        altered = signed_access(payload, '/chat')
        altered['headers']['Cookie'] = 'scholarship_session=another-session'
        assert (await client.post('/api/v1/analytics/accesses', **altered)).status_code == 403
        altered = signed_access(payload, '/chat')
        altered['content'] = altered['content'].replace(b'forged', b'changed')
        assert (await client.post('/api/v1/analytics/accesses', **altered)).status_code == 403
