from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.auth import require_system_admin_session


@pytest.mark.anyio
async def test_system_admin_is_allowed():
    session = SimpleNamespace(role="admin")

    assert await require_system_admin_session(session) is session


@pytest.mark.anyio
async def test_staff_is_rejected_from_system_admin_api():
    with pytest.raises(HTTPException) as raised:
        await require_system_admin_session(SimpleNamespace(role="staff"))

    assert raised.value.status_code == 403
