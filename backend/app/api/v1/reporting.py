import csv
from datetime import date, datetime
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import require_authenticated_session, require_system_admin_session
from app.core.db import get_db
from app.models.auth import AuthSession
from app.repositories.reporting import ReportingRepository
from app.schemas.reporting import ChatHistoryResponse
from app.services.reporting_service import ReportingError, ReportingService, utc_period


router = APIRouter(tags=["reporting"])


def operation_description(method: str, path: str) -> str:
    if path.endswith("/ingestion/run"):
        return "データ取り込み処理を今すぐ実行"
    resources = [
        ("/faq-classifications", "FAQ区分"),
        ("/faqs", "FAQ"),
        ("/data-source-types", "データソース区分"),
        ("/data-sources", "データソース"),
        ("/categories", "カテゴリ"),
        ("/usage/users.csv", "ユーザーリスト"),
        ("/usage/access-logs.csv", "アクセスログ"),
        ("/usage/operation-logs.csv", "操作ログ"),
    ]
    resource = next((label for prefix, label in resources if path.startswith(f"/api/v1{prefix}")), "管理データ")
    if path.endswith(".csv") or path.endswith("/export"):
        return f"{resource}をダウンロード"
    if path.endswith("/import"):
        return f"{resource}を一括登録・更新"
    if path.endswith("/bulk-delete"):
        return f"{resource}を一括削除"
    if path.endswith("/order"):
        return f"{resource}の表示順を変更"
    action = {"POST": "登録", "PUT": "更新", "PATCH": "更新", "DELETE": "削除"}.get(method, "操作")
    return f"{resource}を{action}"


def get_service(session: AsyncSession = Depends(get_db)) -> ReportingService:
    return ReportingService(ReportingRepository(session))


def csv_response(filename: str, headers: list[str], rows: list[list[object]]) -> Response:
    output = StringIO()
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/chat-history", response_model=ChatHistoryResponse)
async def chat_history(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current: AuthSession = Depends(require_authenticated_session),
    service: ReportingService = Depends(get_service),
):
    try:
        return await service.chat_histories(from_date, to_date, page, page_size, current)
    except ReportingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.get("/usage/users.csv")
async def usage_users_csv(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    _: AuthSession = Depends(require_system_admin_session),
    service: ReportingService = Depends(get_service),
):
    try:
        start_at, end_at = utc_period(from_date, to_date)
    except ReportingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    rows = await service.repository.usage_users(start_at, end_at)
    return csv_response(
        f"usage_users_{from_date:%Y%m%d}_{to_date:%Y%m%d}.csv",
        ["利用者ID", "利用者氏名", "ロール", "サイト", "認証種別", "初回記録日時", "最終記録日時", "アクセス数", "チャット数"],
        [[
            row.get("subject") or f"利用者-{row['visitor_key'][:12]}",
            row.get("display_name") or "",
            row.get("role") or "",
            row.get("site") or "",
            row["identity_kind"], row["created_at"], row["last_seen_at"],
            row["access_count"], row["chat_count"],
        ] for row in rows],
    )


@router.get("/usage/access-logs.csv")
async def access_logs_csv(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    _: AuthSession = Depends(require_system_admin_session),
    service: ReportingService = Depends(get_service),
):
    try:
        start_at, end_at = utc_period(from_date, to_date)
    except ReportingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    rows = await service.repository.access_logs(start_at, end_at)
    return csv_response(
        f"access_logs_{from_date:%Y%m%d}_{to_date:%Y%m%d}.csv",
        ["アクセスID", "利用者ID", "利用者氏名", "ロール", "サイト", "認証種別", "アクセス日時", "記録日時"],
        [[
            row["id"], row.get("subject") or f"利用者-{row['visitor_key'][:12]}",
            row.get("display_name") or "", row.get("role") or "", row.get("site") or "",
            row["identity_kind"], row["accessed_at"], row["recorded_at"],
        ] for row in rows],
    )


@router.get("/usage/operation-logs.csv")
async def operation_logs_csv(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    _: AuthSession = Depends(require_system_admin_session),
    service: ReportingService = Depends(get_service),
):
    try:
        start_at, end_at = utc_period(from_date, to_date)
    except ReportingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    rows = await service.repository.operation_logs(start_at, end_at)
    return csv_response(
        f"operation_logs_{from_date:%Y%m%d}_{to_date:%Y%m%d}.csv",
        ["操作ID", "操作者ID", "操作者氏名", "ロール", "サイト", "操作内容", "HTTPメソッド", "操作先", "結果コード", "操作日時"],
        [[
            row["id"], row.get("operator_subject") or f"利用者-{row['operator_key'][:12]}",
            row.get("operator_display_name") or "", row["operator_role"], row.get("operator_site") or "",
            operation_description(row["http_method"], row["request_path"]),
            row["http_method"], row["request_path"], row["status_code"], row["operated_at"],
        ] for row in rows],
    )
