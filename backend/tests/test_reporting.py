import csv
from datetime import date, datetime, timezone
from io import StringIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.analytics_service import AnalyticsService
from app.services.reporting_service import ReportingError, ReportingService, utc_period
from app.api.v1.reporting import access_logs_csv, operation_description, operation_logs_csv, usage_users_csv


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


def decoded_csv(response):
    return list(csv.reader(StringIO(response.body.decode("utf-8-sig"))))


@pytest.mark.anyio
async def test_usage_user_export_contains_cpf_identity():
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    repository = SimpleNamespace(usage_users=AsyncMock(return_value=[{
        "visitor_key": "a" * 64, "identity_kind": "AUTHENTICATED", "subject": "F0000003",
        "display_name": "理科大 職員", "role": "staff", "site": "faculty",
        "created_at": now, "last_seen_at": now, "access_count": 3, "chat_count": 2,
    }]))

    response = await usage_users_csv(
        date(2026, 9, 4), date(2026, 9, 4), _=SimpleNamespace(),
        service=SimpleNamespace(repository=repository),
    )

    rows = decoded_csv(response)
    assert rows[0][:5] == ["利用者ID", "利用者氏名", "ロール", "サイト", "認証種別"]
    assert rows[1][:4] == ["F0000003", "理科大 職員", "staff", "faculty"]


@pytest.mark.anyio
async def test_access_and_operation_exports_contain_readable_identity_and_action():
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    repository = SimpleNamespace(
        access_logs=AsyncMock(return_value=[{
            "id": "access-1", "visitor_key": "b" * 64, "identity_kind": "AUTHENTICATED",
            "subject": "F0000003", "display_name": "理科大 職員", "role": "staff", "site": "faculty",
            "accessed_at": now, "recorded_at": now,
        }]),
        operation_logs=AsyncMock(return_value=[{
            "id": "operation-1", "operator_key": "c" * 64, "operator_subject": "F0000009",
            "operator_display_name": "理科大 管理者", "operator_role": "admin", "operator_site": "faculty",
            "http_method": "POST", "request_path": "/api/v1/faqs", "status_code": 201, "operated_at": now,
        }]),
    )
    service = SimpleNamespace(repository=repository)

    access_rows = decoded_csv(await access_logs_csv(
        date(2026, 9, 4), date(2026, 9, 4), _=SimpleNamespace(), service=service,
    ))
    operation_rows = decoded_csv(await operation_logs_csv(
        date(2026, 9, 4), date(2026, 9, 4), _=SimpleNamespace(), service=service,
    ))

    assert access_rows[1][1:5] == ["F0000003", "理科大 職員", "staff", "faculty"]
    assert operation_rows[1][1:6] == ["F0000009", "理科大 管理者", "admin", "faculty", "FAQを登録"]


def test_operation_description_explains_special_operations():
    assert operation_description("POST", "/api/v1/data-sources/ingestion/run") == "データ取り込み処理を今すぐ実行"
    assert operation_description("GET", "/api/v1/usage/users.csv") == "ユーザーリストをダウンロード"
