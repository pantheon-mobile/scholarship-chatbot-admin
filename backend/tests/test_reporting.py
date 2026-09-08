from datetime import date, datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from openpyxl import load_workbook

from app.services.analytics_service import AnalyticsService
from app.services.reporting_service import ReportingError, ReportingService, utc_period
from app.api.v1.reporting import chat_history_export, access_logs_xlsx, operation_description, operation_logs_xlsx, usage_users_xlsx


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
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    repository = SimpleNamespace(chat_histories=AsyncMock(return_value=(1, [{
        "session_id": "6bb51b07-3ad5-434c-84d8-cf79fa3df274",
        "visitor_key": "a" * 64,
        "subject": "F0000003", "display_name": "理科大 職員", "role": "staff", "site": "faculty",
        "started_at": now, "ended_at": None, "response_count": 1, "completed_count": 1,
        "failed_count": 0, "faq_count": 1, "generated_ai_count": 0, "no_answer_count": 0,
        "good_count": 1, "bad_count": 0,
    }])))
    current = SimpleNamespace(role="admin", site="faculty", subject="admin-001")

    result = await ReportingService(repository).chat_histories(date(2026, 9, 1), date(2026, 9, 4), 1, 20, current)

    assert repository.chat_histories.await_args.kwargs["visitor_key"] is None
    assert result.items[0].user_name == "理科大 職員"
    assert result.items[0].user_id == "F0000003"
    assert result.items[0].user_role == "staff"
    assert result.items[0].user_site == "faculty"


def decoded_xlsx(response):
    return list(load_workbook(BytesIO(response.body), data_only=True).active.values)


@pytest.mark.anyio
async def test_chat_history_export_matches_specified_filename_and_columns():
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    repository = SimpleNamespace(chat_history_export=AsyncMock(return_value=[{
        "session_id": "session-1", "interaction_id": "interaction-1", "sequence_number": 1,
        "subject": "F0000003", "role": "staff", "question_submitted_at": now,
        "answer_displayed_at": now, "answer_type": "GENERATED_AI", "question_text": "質問",
        "answer_text": "回答", "rating": "GOOD", "comment": "参考になった",
    }]))
    response = await chat_history_export(
        date(2026, 9, 4), date(2026, 9, 4), answer_type=None, rating=None, comment=None,
        role=None, user_ids=None, current=SimpleNamespace(role="admin"),
        service=SimpleNamespace(repository=repository),
    )
    rows = decoded_xlsx(response)
    assert rows[0] == (
        "チャットID", "ユーザID", "ユーザ種別", "応答ID", "応答No", "質問", "回答",
        "回答種別", "評価", "コメント", "質問受付日時", "回答完了日時",
    )
    assert rows[1][:10] == (
        "session-1", "F0000003", "職員", "interaction-1", 1, "質問", "回答",
        "生成AI", "Good", "参考になった",
    )
    assert response.headers["content-disposition"].startswith('attachment; filename="chathistory')


@pytest.mark.anyio
async def test_usage_user_export_contains_cpf_identity():
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    repository = SimpleNamespace(usage_users=AsyncMock(return_value=[{
        "visitor_key": "a" * 64, "identity_kind": "AUTHENTICATED", "subject": "F0000003",
        "display_name": "理科大 職員", "role": "staff", "site": "faculty",
        "created_at": now, "last_seen_at": now, "access_count": 3, "chat_count": 2,
    }]))

    response = await usage_users_xlsx(
        date(2026, 9, 4), date(2026, 9, 4), _=SimpleNamespace(),
        service=SimpleNamespace(repository=repository),
    )

    rows = decoded_xlsx(response)
    assert rows[0] == ("ユーザID", "ユーザ種別", "ユーザ名", "最終アクセス日時")
    assert rows[1][:3] == ("F0000003", "職員", "理科大 職員")
    assert response.headers["content-disposition"].startswith('attachment; filename="userlist')


@pytest.mark.anyio
async def test_access_and_operation_exports_contain_readable_identity_and_action():
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    repository = SimpleNamespace(
        access_logs=AsyncMock(return_value=[{
            "id": "access-1", "visitor_key": "b" * 64, "identity_kind": "AUTHENTICATED",
            "subject": "F0000003", "display_name": "理科大 職員", "role": "staff", "site": "faculty",
            "surface": "ADMIN", "ip_address": "192.0.2.1", "user_agent": "Test Browser",
            "accessed_at": now, "recorded_at": now,
        }]),
        operation_logs=AsyncMock(return_value=[{
            "id": "operation-1", "operator_key": "c" * 64, "operator_subject": "F0000009",
            "operator_display_name": "理科大 管理者", "operator_role": "admin", "operator_site": "faculty",
            "surface": "ADMIN", "ip_address": "192.0.2.2", "user_agent": "Test Browser",
            "http_method": "POST", "request_path": "/api/v1/faqs", "status_code": 201, "operated_at": now,
        }]),
    )
    service = SimpleNamespace(repository=repository)

    access_rows = decoded_xlsx(await access_logs_xlsx(
        date(2026, 9, 4), date(2026, 9, 4), _=SimpleNamespace(), service=service,
    ))
    operation_rows = decoded_xlsx(await operation_logs_xlsx(
        date(2026, 9, 4), date(2026, 9, 4), _=SimpleNamespace(), service=service,
    ))

    assert access_rows[0] == ("アクセス日時", "ユーザID", "ユーザ種別", "サイト", "アクセス元（IP）", "デバイス/UA")
    assert access_rows[1][1:] == ("F0000003", "職員", "管理サイト", "192.0.2.1", "Test Browser")
    assert operation_rows[0] == ("操作日時", "ユーザID", "ユーザ種別", "操作種別", "サイト", "アクセス元（IP）", "デバイス/UA")
    assert operation_rows[1][1:] == ("F0000009", "システム管理者", "FAQを登録", "管理サイト", "192.0.2.2", "Test Browser")


def test_operation_description_explains_special_operations():
    assert operation_description("POST", "/api/v1/data-sources/ingestion/run") == "データ取り込み処理を今すぐ実行"
    assert operation_description("GET", "/api/v1/usage/users.xlsx") == "ユーザーリストをダウンロード"
