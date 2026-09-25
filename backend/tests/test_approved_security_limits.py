import asyncio
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED

import pytest
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.db import get_db
from app.db.base_class import Base
from app.main import app
from app.models.analytics import AnalyticsVisitor, ChatSession, ChatInteraction, ChatFeedback, AccessLog
from app.models.auth import AdminOperationLog
from app.api.v1.auth import require_authenticated_session
from app.repositories.analytics import AnalyticsRepository
from app.repositories.reporting import ReportingRepository
from app.services.analytics_service import AnalyticsService
from app.services.chat_admission import admit_chat, ChatRequestLimit
from app.services.chat_context_service import ChatContextService, ContextSessionNotFound
from app.services.excel_security import validate_excel_expansion
from app.services.resource_limits import ExcelExpansionLimitExceeded, ExportLimitExceeded


def zipped(*sizes):
    output = BytesIO()
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for index, size in enumerate(sizes):
            archive.writestr(f'part{index}.xml', b'x' * size)
    return output.getvalue()


def test_expanded_size_total_boundary_and_stream_position(monkeypatch):
    monkeypatch.setenv('EXCEL_EXPANDED_MAX_MB', '1')
    stream = BytesIO(zipped(512 * 1024, 512 * 1024))
    stream.seek(5)
    validate_excel_expansion(stream)
    assert stream.tell() == 5
    with pytest.raises(ExcelExpansionLimitExceeded, match='1MB'):
        validate_excel_expansion(zipped(512 * 1024, 512 * 1024 + 1))
    monkeypatch.setenv('EXCEL_EXPANDED_MAX_MB', '2')
    validate_excel_expansion(zipped(1024 * 1024 + 1))


@pytest.mark.anyio
@pytest.mark.parametrize('path,field', [
    ('/api/v1/faqs/import', 'file'),
    ('/api/v1/data-sources/import', 'file'),
    ('/api/v1/data-sources/websites/import', 'file'),
    ('/api/v1/data-sources/files', 'files'),
])
async def test_excel_limit_is_visible_before_any_database_write(path, field, monkeypatch, tmp_path):
    monkeypatch.setenv('EXCEL_EXPANDED_MAX_MB', '1')
    monkeypatch.setenv('UPLOAD_DIR', str(tmp_path))
    db = AsyncMock()
    old = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            result = await client.post(path, files={field: ('large.xlsx', zipped(1024 * 1024 + 1),
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
        assert result.status_code == 422, result.text
        assert '展開後サイズ' in result.json()['detail']
        assert '分割' in result.json()['detail']
        db.execute.assert_not_awaited()
        db.commit.assert_not_awaited()
    finally:
        app.dependency_overrides = old


@pytest.fixture
async def limit_engine():
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Requires disposable Postgres TEST_DATABASE_URL')
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db(limit_engine):
    async with limit_engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(connection, expire_on_commit=False, join_transaction_mode='create_savepoint') as session:
            yield session
        await transaction.rollback()


@pytest.mark.anyio
async def test_admission_shared_across_connections_and_cancel_releases_slot(limit_engine, monkeypatch):
    key = uuid4().hex
    monkeypatch.setenv('CHAT_REQUESTS_PER_MINUTE', '10')
    monkeypatch.setenv('CHAT_MAX_CONCURRENT_REQUESTS', '1')
    async with admit_chat(limit_engine, key):
        with pytest.raises(HTTPException) as error:
            async with admit_chat(limit_engine, key):
                pytest.fail('same user admitted twice')
        assert error.value.status_code == 429 and '他のタブ' in error.value.detail
        async with admit_chat(limit_engine, uuid4().hex):
            pass
    entered = asyncio.Event()
    async def pending():
        async with admit_chat(limit_engine, key):
            entered.set()
            await asyncio.Event().wait()
    task = asyncio.create_task(pending())
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with admit_chat(limit_engine, key):
        pass
    # Configuration may permit two simultaneous requests, still shared by all workers.
    monkeypatch.setenv('CHAT_MAX_CONCURRENT_REQUESTS', '2')
    async with admit_chat(limit_engine, key), admit_chat(limit_engine, key):
        with pytest.raises(HTTPException):
            async with admit_chat(limit_engine, key):
                pytest.fail('third request admitted')


@pytest.mark.anyio
async def test_rate_window_persists_after_failure_and_expires(limit_engine, monkeypatch):
    key = uuid4().hex
    monkeypatch.setenv('CHAT_REQUESTS_PER_MINUTE', '2')
    with pytest.raises(RuntimeError):
        async with admit_chat(limit_engine, key):
            raise RuntimeError('generation failed')
    async with admit_chat(limit_engine, key):
        pass
    with pytest.raises(HTTPException) as error:
        async with admit_chat(limit_engine, key):
            pytest.fail('rate limit bypassed')
    assert error.value.status_code == 429
    assert 1 <= int(error.value.headers['Retry-After']) <= 60
    async with AsyncSession(limit_engine) as session, session.begin():
        row = await session.get(ChatRequestLimit, key)
        assert len(row.accepted_at) == 2
        row.accepted_at = [value - 61 for value in row.accepted_at]
    async with admit_chat(limit_engine, key):
        pass


async def seed_chat(db, key, *, kind='GENERATED_AI', title='保存対象'):
    now = datetime.now(timezone.utc)
    visitor = AnalyticsVisitor(id=uuid4(), visitor_key=key, identity_kind='AUTHENTICATED',
        subject=key[:20], role='staff', site='faculty', created_at=now, last_seen_at=now)
    db.add(visitor)
    await db.flush()
    chat = ChatSession(id=uuid4(), visitor_id=visitor.id, title=title, started_at=now, recorded_at=now)
    db.add(chat)
    await db.flush()
    interaction = ChatInteraction(id=uuid4(), chat_session_id=chat.id, sequence_number=1,
        question_submitted_at=now, answer_displayed_at=now, processing_status='COMPLETED',
        answer_type=kind, question_text='申請期限の質問', answer_text='案内', created_at=now, updated_at=now)
    db.add(interaction)
    await db.flush()
    feedback = ChatFeedback(interaction_id=interaction.id, rating='BAD', comment='改善してください',
        reason='回答が違う', comment_text='改善してください', created_at=now, updated_at=now)
    db.add(feedback)
    await db.flush()
    return chat, interaction, visitor


@pytest.mark.anyio
async def test_user_delete_hides_every_user_path_but_retains_admin_exports(db, monkeypatch):
    monkeypatch.setenv('ANALYTICS_IDENTITY_SECRET', 'retention-test')
    user = SimpleNamespace(subject='retention-owner', site='faculty', role='staff', display_name='所有者')
    key = AnalyticsService(AnalyticsRepository(db)).visitor_key('AUTHENTICATED', 'faculty:retention-owner')
    chat, interaction, _ = await seed_chat(db, key)
    chat_id, interaction_id = chat.id, interaction.id
    old = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_authenticated_session] = lambda: user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            assert (await client.delete(f'/api/v1/chat/sessions/{chat_id}')).status_code == 204
            assert (await client.get('/api/v1/chat/sessions?search=申請期限')).json() == []
            assert (await client.get(f'/api/v1/chat/sessions/{chat_id}')).status_code == 404
            assert (await client.patch(f'/api/v1/chat/sessions/{chat_id}', json={'title': '復活'})).status_code == 404
            assert (await client.put(f'/api/v1/analytics/interactions/{interaction_id}/feedback', json={'rating':'GOOD'})).status_code == 404
            result = await client.post(f'/api/v1/analytics/chat-sessions/{chat_id}/interactions', json={
                'id':str(uuid4()), 'sequence_number':2, 'question_submitted_at':datetime.now(timezone.utc).isoformat(), 'question_text':'続き'})
            assert result.status_code == 404
            result = await client.post('/api/v1/analytics/chat-sessions', json={
                'id':str(chat_id), 'started_at':datetime.now(timezone.utc).isoformat(),
                'identity':{'identity_kind':'AUTHENTICATED','identifier':'ignored'}})
            assert result.status_code == 409
        await db.refresh(chat)
        assert chat.user_deleted
        assert (await db.get(ChatFeedback, interaction_id)).rating == 'BAD'
        repository = AnalyticsRepository(db)
        assert await repository.get_owned_interaction(interaction_id, key) is None
        context = ChatContextService(db, key)
        assert await context.recent_turns(chat_id) == []
        assert await context.other_chats(None, datetime.now(timezone.utc)) == []
        with pytest.raises(ContextSessionNotFound):
            await context.resolve('さっきの話', chat_id, True)
        report = ReportingRepository(db)
        start, end = datetime.now(timezone.utc)-timedelta(days=1), datetime.now(timezone.utc)+timedelta(days=1)
        from app.repositories.dashboard import DashboardRepository
        aggregate = await DashboardRepository(db).aggregate(start, end)
        assert aggregate['sessions']['chat_count'] == 1
        assert aggregate['interactions']['bad_count'] == 1
        admin_rows = await report.chat_history_export(start, end)
        assert any(row['interaction_id'] == interaction_id and row['rating'] == 'BAD' for row in admin_rows)
        assert await report.chat_history_export(start, end, visitor_key=key) == []
        assert (await report.chat_histories(start, end, visitor_key=None, limit=20, offset=0))[0] == 1
        assert (await report.chat_histories(start, end, visitor_key=key, limit=20, offset=0))[0] == 0
    finally:
        app.dependency_overrides = old


@pytest.mark.anyio
async def test_exports_limit_after_filters_never_truncate(db, monkeypatch):
    monkeypatch.setenv('REPORT_EXPORT_MAX_ROWS', '2')
    for index in range(3):
        _, _, visitor = await seed_chat(db, uuid4().hex, kind='NO_ANSWER' if index < 2 else 'GENERATED_AI')
        now = datetime.now(timezone.utc)
        db.add(AccessLog(id=uuid4(), visitor_id=visitor.id, surface='CHAT' if index < 2 else 'ADMIN', accessed_at=now, recorded_at=now))
        db.add(AdminOperationLog(id=uuid4(), operator_key=visitor.visitor_key, http_method='GET',
            request_path='/api/v1/chat-history/export.xlsx' if index < 2 else '/api/v1/health',
            surface='ADMIN', operator_role='admin', status_code=200, operated_at=now))
    await db.flush()
    report = ReportingRepository(db)
    start, end = datetime.now(timezone.utc)-timedelta(days=1), datetime.now(timezone.utc)+timedelta(days=1)
    for action in [report.chat_history_export, report.access_logs, report.operation_logs]:
        with pytest.raises(ExportLimitExceeded, match='2件'):
            await action(start, end)
    assert len(await report.chat_history_export(start, end, answer_type='NO_ANSWER')) == 2
    assert len(await report.access_logs(start, end, surface='CHAT')) == 2
    assert len(await report.operation_logs(start, end, operation_type='DOWNLOAD', surface='ADMIN')) == 2
    monkeypatch.setenv('REPORT_EXPORT_MAX_ROWS', '3')
    assert len(await report.chat_history_export(start, end)) == 3


@pytest.mark.anyio
async def test_rate_http_message_and_single_connection_pool(monkeypatch, limit_engine):
    # A guard must not exhaust the pool needed by rate recording or generation.
    engine = create_async_engine(limit_engine.url, pool_size=1, max_overflow=0, pool_timeout=1)
    key = uuid4().hex
    monkeypatch.setenv('CHAT_REQUESTS_PER_MINUTE', '10')
    try:
        for _ in range(10):
            async with AsyncSession(engine) as session:
                # Authentication has already checked out the query connection.
                assert await session.scalar(select(1)) == 1
                async with admit_chat(engine, key):
                    assert await session.scalar(select(1)) == 1
        with pytest.raises(HTTPException) as error:
            async with admit_chat(engine, key):
                pytest.fail('11th request accepted')
        assert '1分間に10回' in error.value.detail
        monkeypatch.setattr('app.api.v1.chat._visitor_key', lambda current: key)
        old = app.dependency_overrides.copy()
        async with AsyncSession(engine) as db:
            app.dependency_overrides[get_db] = lambda: db
            try:
                async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
                    response = await client.post('/api/v1/chat/messages', json={
                        'question':'申請方法', 'chat_session_id':str(uuid4()), 'interaction_id':str(uuid4())})
                assert response.status_code == 429
                assert '待って' in response.json()['detail']
                assert 'retry-after' in response.headers
            finally:
                app.dependency_overrides = old
    finally:
        await engine.dispose()


@pytest.mark.anyio
@pytest.mark.parametrize('endpoint,method', [
    ('/api/v1/chat-history/export.xlsx', 'chat_history_export'),
    ('/api/v1/usage/access-logs.csv', 'access_logs'),
    ('/api/v1/usage/operation-logs.csv', 'operation_logs'),
])
async def test_export_limit_http_message_is_not_a_truncated_file(endpoint, method):
    from app.api.v1.reporting import get_service
    old = app.dependency_overrides.copy()
    repository = SimpleNamespace(**{method: AsyncMock(side_effect=ExportLimitExceeded(10000))})
    app.dependency_overrides[get_service] = lambda: SimpleNamespace(repository=repository)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            response = await client.get(endpoint, params={'from':'2026-09-01', 'to':'2026-09-30'})
        assert response.status_code == 422
        assert '10,000件' in response.json()['detail']
        assert '検索条件' in response.json()['detail']
        assert 'content-disposition' not in response.headers
    finally:
        app.dependency_overrides = old
