import json
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.services.dashboard_settings import METRIC_IDS, visible_basic_metrics
from app.services.dashboard_service import DashboardService, DashboardError
from test_dashboard import aggregate_data


def test_defaults_and_hidden_selection(monkeypatch):
    monkeypatch.delenv('DASHBOARD_BASIC_METRICS', raising=False)
    assert visible_basic_metrics() == list(METRIC_IDS)
    monkeypatch.setenv('DASHBOARD_BASIC_METRICS', json.dumps({'chat_count': {'name': '説明用の名前', 'visible': 0}}))
    assert 'chat_count' not in visible_basic_metrics()
    assert len(visible_basic_metrics()) == 20


@pytest.mark.parametrize('raw', ['null', '[]', '{', '{"unknown":{"name":"不明","visible":1}}', '{"chat_count":{"name":"数","visible":true}}', '{"chat_count":{"name":"数","visible":"0"}}', '{"chat_count":{"name":"数","visible":2}}', '{"chat_count":{"visible":1}}'])
def test_reject_invalid_settings(monkeypatch, raw):
    monkeypatch.setenv('DASHBOARD_BASIC_METRICS', raw)
    with pytest.raises(ValueError):
        visible_basic_metrics()


@pytest.mark.asyncio
async def test_visibility_does_not_change_aggregates(monkeypatch):
    repo = AsyncMock()
    repo.aggregate.return_value = aggregate_data()
    service = DashboardService(repo)
    monkeypatch.delenv('DASHBOARD_BASIC_METRICS', raising=False)
    before = await service.get(date(2026,8,1), date(2026,8,19))
    monkeypatch.setenv('DASHBOARD_BASIC_METRICS', json.dumps({k: {'name': k, 'visible': 0} for k in METRIC_IDS}))
    after = await service.get(date(2026,8,1), date(2026,8,19))
    assert after.visible_basic_metrics == []
    assert before.model_dump(exclude={'visible_basic_metrics'}) == after.model_dump(exclude={'visible_basic_metrics'})


@pytest.mark.asyncio
async def test_invalid_config_reported_before_query(monkeypatch):
    monkeypatch.setenv('DASHBOARD_BASIC_METRICS', '[]')
    repo = AsyncMock()
    with pytest.raises(DashboardError) as err:
        await DashboardService(repo).get(date(2026,8,1), date(2026,8,19))
    assert err.value.code == 'INVALID_DASHBOARD_SETTINGS'
    repo.aggregate.assert_not_called()
