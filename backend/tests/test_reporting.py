from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.analytics_service import AnalyticsService
from app.services.reporting_service import ReportingError, ReportingService, utc_period


def test_utc_period_rejects_reversed_dates():
    with pytest.raises(ReportingError):
        utc_period(date(2026, 9, 2), date(2026, 9, 1))


@pytest.mark.anyio
async def test_staff_chat_history_is_limited_to_own_hmac(monkeypatch):
    monkeypatch.setenv("ANALYTICS_IDENTITY_SECRET", "test-secret")
    repository = SimpleNamespace(chat_histories=AsyncMock(return_value=(0, [])))
    current = SimpleNamespace(role="staff", site="faculty", subject="staff-001")

    await ReportingService(repository).chat_histories(date(2026, 9, 1), date(2026, 9, 1), 1, 20, current)

    expected = AnalyticsService(repository).visitor_key("AUTHENTICATED", "faculty:staff-001")
    assert repository.chat_histories.await_args.kwargs["visitor_key"] == expected


@pytest.mark.anyio
async def test_admin_chat_history_can_read_all_users():
    repository = SimpleNamespace(chat_histories=AsyncMock(return_value=(0, [])))
    current = SimpleNamespace(role="admin", site="faculty", subject="admin-001")

    await ReportingService(repository).chat_histories(date(2026, 9, 1), date(2026, 9, 1), 1, 20, current)

    assert repository.chat_histories.await_args.kwargs["visitor_key"] is None
