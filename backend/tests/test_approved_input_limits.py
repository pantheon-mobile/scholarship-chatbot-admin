from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.v1 import categories, data_sources, data_source_types, faqs, faq_classifications
from app.schemas.category import CategoryBulkDeleteRequest, CategoryOrderRequest
from app.schemas.data_source import BulkDeleteRequest
from app.schemas.faq import FaqBulkDeleteRequest
from app.schemas.faq_classification import (
    FaqClassificationLabelUpdate, FaqClassificationValueCreate,
    FaqClassificationValueUpdate, FaqClassificationTypeResponse, FaqClassificationOrderUpdate,
)
from app.services.resource_limits import InputLimitExceeded
from app.services.client_ip import client_ip


@pytest.mark.parametrize('schema', [CategoryBulkDeleteRequest, CategoryOrderRequest, BulkDeleteRequest, FaqBulkDeleteRequest, FaqClassificationOrderUpdate])
def test_item_limit_boundary_and_configuration(schema, monkeypatch):
    monkeypatch.setenv('BULK_DELETE_MAX_ITEMS', '1000')
    monkeypatch.setenv('REORDER_MAX_ITEMS', '1000')
    items = [{'id': i + 1, 'version': 1} for i in range(1001)]
    assert len(schema(items=items[:1000]).items) == 1000
    with pytest.raises(InputLimitExceeded, match='1,000'):
        schema(items=items)
    monkeypatch.setenv('BULK_DELETE_MAX_ITEMS', '1001')
    monkeypatch.setenv('REORDER_MAX_ITEMS', '1001')
    assert len(schema(items=items).items) == 1001


@pytest.mark.parametrize('schema,field,limit', [
    (FaqClassificationLabelUpdate, 'display_label', 100),
    (FaqClassificationValueCreate, 'value_name', 200),
    (FaqClassificationValueUpdate, 'value_name', 200),
])
def test_faq_classification_text_boundaries(schema, field, limit):
    value = 'あ' * limit
    assert getattr(schema(**{field: value, 'version': 1}), field) == value
    with pytest.raises(InputLimitExceeded, match=str(limit)):
        schema(**{field: value + 'あ', 'version': 1})


def test_existing_long_classification_values_remain_readable():
    result = FaqClassificationTypeResponse(
        id=1, type_code='FAQ_TYPE_1', fixed_name='区分1', display_label='あ' * 101,
        display_order=1, version=1,
        values=[dict(id=1, value_name='あ' * 201, display_order=1, version=1)],
    )
    assert len(result.display_label) == 101
    assert len(result.values[0].value_name) == 201


CASES = [
    (data_sources, 'POST', '/api/v1/data-sources/bulk-delete', 'bulk_delete'),
    (faqs, 'POST', '/api/v1/faqs/bulk-delete', 'bulk_delete'),
    (categories, 'POST', '/api/v1/categories/bulk-delete', 'bulk_delete'),
    (categories, 'PATCH', '/api/v1/categories/order', 'reorder'),
    (faq_classifications, 'PATCH', '/api/v1/faq-classifications/1/values/order', 'reorder_values'),
    (data_source_types, 'PUT', '/api/v1/data-source-types/1/values/order', 'reorder_values'),
]


@pytest.mark.anyio
@pytest.mark.parametrize('module,method,path,operation', CASES)
async def test_over_limit_api_rejects_before_mutation(module, method, path, operation, monkeypatch):
    monkeypatch.setenv('BULK_DELETE_MAX_ITEMS', '2')
    monkeypatch.setenv('REORDER_MAX_ITEMS', '2')
    service = AsyncMock()
    app.dependency_overrides[module.get_service] = lambda: service
    body = [1, 2, 3] if module is data_source_types else {'items': [{'id': i, 'version': 1} for i in [1, 2, 3]]}
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            response = await client.request(method, path, json=body)
        assert response.status_code == 422, response.text
        assert '2件まで' in response.json()['detail']
        getattr(service, operation).assert_not_awaited()
    finally:
        app.dependency_overrides.pop(module.get_service, None)


@pytest.mark.anyio
async def test_type_reorder_accepts_exact_configured_limit(monkeypatch):
    monkeypatch.setenv('REORDER_MAX_ITEMS', '2')
    service = AsyncMock()
    app.dependency_overrides[data_source_types.get_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            response = await client.put('/api/v1/data-source-types/1/values/order', json=[1, 2])
        assert response.status_code == 204
        service.reorder_values.assert_awaited_once_with(1, [1, 2])
    finally:
        app.dependency_overrides.pop(data_source_types.get_service, None)


@pytest.mark.anyio
@pytest.mark.parametrize('method,path,body,expected', [
    ('PATCH', '/api/v1/faq-classifications/1', {'display_label': 'あ' * 101, 'version': 1}, '100文字'),
    ('POST', '/api/v1/faq-classifications/1/values', {'value_name': 'あ' * 201}, '200文字'),
    ('PUT', '/api/v1/faq-classifications/1/values/1', {'value_name': 'あ' * 201, 'version': 1}, '200文字'),
])
async def test_text_limit_errors_are_displayable(method, path, body, expected):
    service = AsyncMock()
    app.dependency_overrides[faq_classifications.get_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            response = await client.request(method, path, json=body)
        assert response.status_code == 422
        assert expected in response.json()['detail']
        assert not service.mock_calls
    finally:
        app.dependency_overrides.pop(faq_classifications.get_service, None)


def test_direct_alb_private_caller_cannot_spoof_leftmost_ip(monkeypatch):
    monkeypatch.setenv('TRUSTED_PROXY_CIDRS', '10.0.0.0/16')
    request = SimpleNamespace(client=SimpleNamespace(host='10.0.1.2'), headers={'x-forwarded-for': '8.8.8.8, 10.0.2.3'})
    assert client_ip(request) == '10.0.2.3'
    # Signed frontend forwarding uses the original request's ALB-added value.
    assert client_ip(request, forwarded_for='1.1.1.1, 10.0.3.4') == '10.0.3.4'
