import os
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/source_mutation_tests")

from types import SimpleNamespace

import pytest

from app.api.v1.auth import require_authenticated_session
from app.main import app


@pytest.fixture(autouse=True)
def authenticated_admin_for_existing_api_tests():
    app.dependency_overrides[require_authenticated_session] = lambda: SimpleNamespace(
        subject="test-admin", display_name="テスト管理者", role="admin", site="faculty"
    )
    yield
    app.dependency_overrides.pop(require_authenticated_session, None)


@pytest.fixture
def signed_access(monkeypatch):
    import hashlib
    import hmac
    import json
    monkeypatch.setenv('ACCESS_LOG_SIGNING_SECRET', 'server-access-test-secret')
    monkeypatch.setenv('CORS_ALLOWED_ORIGINS', 'http://test')
    def sign(payload, path='/chat'):
        body = json.dumps(payload).encode()
        signature = hmac.new(b'server-access-test-secret', b'v1\ntest-session\n' + path.encode() + b'\n' + body, hashlib.sha256).hexdigest()
        return {'content': body, 'headers': {'Content-Type': 'application/json', 'Origin': 'http://test', 'Cookie': 'scholarship_session=test-session', 'X-Access-Page': path, 'X-Access-Signature': signature}}
    return sign
