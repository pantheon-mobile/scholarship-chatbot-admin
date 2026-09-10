from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.maintenance_service import MaintenanceDisabledError, MaintenanceService, destructive_purge_enabled


def test_destructive_purge_requires_flag_and_safe_environment(monkeypatch):
    monkeypatch.setenv("ENABLE_DESTRUCTIVE_PURGE", "true")
    monkeypatch.setenv("APP_ENV", "production")
    assert destructive_purge_enabled() is False

    monkeypatch.setenv("APP_ENV", "stg01-demo")
    assert destructive_purge_enabled() is True

    monkeypatch.setenv("ENABLE_DESTRUCTIVE_PURGE", "false")
    assert destructive_purge_enabled() is False


@pytest.mark.anyio
async def test_purge_is_rejected_before_database_access_in_production(monkeypatch):
    monkeypatch.setenv("ENABLE_DESTRUCTIVE_PURGE", "true")
    monkeypatch.setenv("APP_ENV", "production")
    session = AsyncMock()

    with pytest.raises(MaintenanceDisabledError):
        await MaintenanceService(session, MagicMock()).purge()

    session.execute.assert_not_called()
