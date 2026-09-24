"""Verify HTTP ownership against PostgreSQL, including row locks and replays."""
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.v1 import analytics as api
from app.api.v1.auth import require_authenticated_session
from app.db.base_class import Base
from app.main import app
from app.models.analytics import AnalyticsVisitor, ChatFeedback, ChatInteraction
from app.repositories.analytics import AnalyticsRepository
from app.services.analytics_service import AnalyticsService


@pytest.fixture
async def analytics_db():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires disposable Postgres TEST_DATABASE_URL")
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as session:
            yield session
        await transaction.rollback()
    await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize("answer_type", ["GENERATED_AI", "NO_ANSWER"])
@pytest.mark.parametrize("identity_kind", ["AUTHENTICATED", "ANONYMOUS"])
@pytest.mark.parametrize("other_subject,other_site,other_role", [
    ("other-user", "faculty", "staff"), ("other-admin", "faculty", "admin"),
    ("owner", "student", "admin"),
])
async def test_http_ownership_and_normal_recording(analytics_db, other_subject, other_site, other_role, identity_kind, answer_type, monkeypatch):
    monkeypatch.setenv("ANALYTICS_IDENTITY_SECRET", "ownership-test-secret")
    db = analytics_db
    service = AnalyticsService(AnalyticsRepository(db), identity_secret="ownership-test-secret")
    owner = SimpleNamespace(subject="owner", site="faculty", role="staff", display_name="所有者")
    other = SimpleNamespace(subject=other_subject, site=other_site, role=other_role, display_name="別人")
    current = owner
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[require_authenticated_session] = lambda: current
    app.dependency_overrides[api.get_service] = lambda: service
    from app.api.v1 import chat as chat_api
    from app.core.db import get_db
    from app.schemas.chat import ChatMessageResponse
    from app.services.chat_context_service import ChatContextService, ContextResult
    chat_service = Mock()
    chat_service.answer_from_faq.return_value = None
    chat_service.answer = AsyncMock(return_value=ChatMessageResponse(answer="案内をご確認ください。", answer_type=answer_type, citations=[]))
    monkeypatch.setattr(ChatContextService, "resolve", AsyncMock(return_value=ContextResult("申請期限は？")))
    app.dependency_overrides[chat_api.get_service] = lambda: chat_service
    app.dependency_overrides[get_db] = lambda: db
    now = datetime.now(timezone.utc)
    session_id, interaction_id, access_id = uuid4(), uuid4(), uuid4()
    forged = {"identity_kind": identity_kind, "identifier": "faculty:victim" if identity_kind == "AUTHENTICATED" else str(uuid4())}
    session_payload = {"id": str(session_id), "identity": forged, "started_at": now.isoformat()}
    access_payload = {"id": str(access_id), "identity": forged, "accessed_at": now.isoformat()}
    question = {"id": str(interaction_id), "sequence_number": 1,
                "question_submitted_at": now.isoformat(), "question_text": "申請期限は？"}
    completed = {"processing_status": "COMPLETED", "answer_type": answer_type,
                 "answer_displayed_at": (now + timedelta(seconds=1)).isoformat(), "answer_text": "案内をご確認ください。"}
    base = "/api/v1/analytics"
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            access = await client.post(f"{base}/accesses", json=access_payload)
            started = await client.post(f"{base}/chat-sessions", json=session_payload)
            assert access.status_code == started.status_code == 201
            assert access.json()["visitor_id"] == started.json()["visitor_id"]
            visitor = (await db.execute(select(AnalyticsVisitor))).scalar_one()
            assert visitor.visitor_key == service.visitor_key("AUTHENTICATED", "faculty:owner")
            assert visitor.subject == "owner" and visitor.site == "faculty"
            assert visitor.identity_kind == "AUTHENTICATED"
            assert (await client.post(f"{base}/chat-sessions", json=session_payload)).status_code == 201
            for _ in range(2):
                assert (await client.post(f"{base}/chat-sessions/{session_id}/interactions", json=question)).status_code == 201
            current = other
            denied = await client.post(f"{base}/chat-sessions/{session_id}/interactions", json=question)
            assert denied.status_code == 404 and denied.json()["detail"]["code"] == "CHAT_SESSION_NOT_FOUND"
            for target in [interaction_id, uuid4()]:
                denied = await client.patch(f"{base}/interactions/{target}/completion", json=completed)
                assert denied.status_code == 404 and denied.json()["detail"]["code"] == "INTERACTION_NOT_FOUND"
                denied = await client.put(f"{base}/interactions/{target}/feedback", json={"rating": "BAD"})
                assert denied.status_code == 404 and denied.json()["detail"]["code"] == "INTERACTION_NOT_FOUND"
            # A forged identity cannot claim/replay an existing session or access event.
            assert (await client.post(f"{base}/chat-sessions", json=session_payload)).status_code == 409
            assert (await client.post(f"{base}/accesses", json=access_payload)).status_code == 409
            row = await db.get(ChatInteraction, interaction_id)
            assert row.processing_status == "PROCESSING" and row.answer_text is None
            assert await db.scalar(select(func.count()).select_from(ChatFeedback)) == 0
            assert await db.scalar(select(func.count()).select_from(ChatInteraction)) == 1
            current = owner
            # The browser cannot fabricate a successful response before generation.
            assert (await client.patch(f"{base}/interactions/{interaction_id}/completion", json=completed)).status_code == 409
            generated = await client.post('/api/v1/chat/messages', json={
                'interaction_id': str(interaction_id), 'chat_session_id': str(session_id), 'question': question['question_text']})
            assert generated.status_code == 200, generated.text
            await db.refresh(row)
            assert row.processing_status == 'COMPLETED' and row.answer_text == completed['answer_text']
            assert (await client.patch(f"{base}/interactions/{interaction_id}/completion", json={**completed, 'answer_text': 'forged'})).status_code == 409
            assert (await client.patch(f"{base}/interactions/{interaction_id}/completion", json={'processing_status': 'FAILED'})).status_code == 200
            await db.refresh(row)
            assert row.processing_status == 'COMPLETED'
            for _ in range(2):
                assert (await client.patch(f"{base}/interactions/{interaction_id}/completion", json=completed)).status_code == 200
            for rating in ["GOOD", "BAD"]:
                result = await client.put(f"{base}/interactions/{interaction_id}/feedback", json={"rating": rating, "comment": "評価", "reason": "保存時の理由"})
                assert result.status_code == 200 and result.json()["rating"] == rating
            from app.api.v1.chat import get_chat_session_history
            await db.refresh(await db.get(ChatFeedback, interaction_id))
            history = await get_chat_session_history(session_id, current_user=owner, session=db)
            assert history.messages[-1].feedback_reason == "保存時の理由"
            assert history.messages[-1].feedback_comment == "評価"
            current = other
            assert (await client.patch(f"{base}/interactions/{interaction_id}/completion", json=completed)).status_code == 404
            assert (await client.put(f"{base}/interactions/{interaction_id}/feedback", json={"rating": "GOOD"})).status_code == 404
            feedback = await db.get(ChatFeedback, interaction_id)
            assert feedback.rating == "BAD" and feedback.comment == "保存時の理由：評価"
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
