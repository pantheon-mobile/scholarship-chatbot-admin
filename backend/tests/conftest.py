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
