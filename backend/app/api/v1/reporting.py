from datetime import date, datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
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
        ("/usage/users.xlsx", "ユーザーリスト"),
        ("/usage/access-logs.xlsx", "アクセスログ"),
        ("/usage/operation-logs.xlsx", "操作ログ"),
    ]
    resource = next((label for prefix, label in resources if path.startswith(f"/api/v1{prefix}")), "管理データ")
    if path.endswith((".csv", ".xlsx", "/export", "/import-template")):
        return f"{resource}をダウンロード"
    if path.endswith("/import"):
        return f"{resource}を一括登録・更新"
    if path.endswith("/bulk-delete"):
        return f"{resource}を一括削除"
    if path.endswith("/order"):
        return f"{resource}の表示順を変更"
    action = {"POST": "登録", "PUT": "更新", "PATCH": "更新", "DELETE": "削除"}.get(method, "操作")
    return f"{resource}を{action}"


def operation_kind(method: str, path: str) -> str:
    if path.endswith((".csv", ".xlsx", "/export", "/import-template")):
        return "DOWNLOAD"
    if path.endswith("/import") or "/files" in path:
        return "UPLOAD"
    return {"POST": "CREATE", "PUT": "UPDATE", "PATCH": "UPDATE", "DELETE": "DELETE"}.get(method, "OTHER")


def parsed_user_ids(value: str | None) -> list[str] | None:
    if not isinstance(value, str) or not value:
        return None
    result = list(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))
    return result or None


def get_service(session: AsyncSession = Depends(get_db)) -> ReportingService:
    return ReportingService(ReportingRepository(session))


ROLE_LABELS = {"staff": "職員", "admin": "システム管理者", "student": "学生"}
SURFACE_LABELS = {"CHAT": "チャット", "ADMIN": "管理サイト"}
ANSWER_TYPE_LABELS = {"FAQ": "FAQ", "GENERATED_AI": "生成AI", "NO_ANSWER": "回答なし"}
RATING_LABELS = {"GOOD": "Good", "BAD": "Bad"}


def display_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S")


def xlsx_response(filename: str, sheet_name: str, headers: list[str], rows: list[list[object]]) -> Response:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
    for column in sheet.columns:
        values = [str(cell.value or "") for cell in column]
        width = min(max(max((len(value) for value in values), default=0) + 2, 12), 64)
        sheet.column_dimensions[column[0].column_letter].width = width
        for cell in column[1:]:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    sheet.freeze_panes = "A2"
    output = BytesIO()
    workbook.save(output)
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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


@router.get("/chat-history/export.xlsx")
async def chat_history_export(
    from_date: date = Query(..., alias="from"), to_date: date = Query(..., alias="to"),
    answer_type: str | None = Query(None, pattern="^(FAQ|GENERATED_AI)$"),
    rating: str | None = Query(None, pattern="^(RATED|GOOD|BAD|NONE)$"),
    comment: str | None = Query(None, pattern="^(WITH|WITHOUT)$"),
    role: str | None = Query(None, pattern="^(staff|admin)$"), user_ids: str | None = Query(None, max_length=5000),
    current: AuthSession = Depends(require_authenticated_session), service: ReportingService = Depends(get_service),
):
    try: start_at, end_at = utc_period(from_date, to_date)
    except ReportingError as error: raise HTTPException(status_code=422, detail=str(error)) from None
    own_key = None
    if current.role == "staff":
        from app.services.analytics_service import AnalyticsService
        own_key = AnalyticsService(service.repository).visitor_key("AUTHENTICATED", f"{current.site}:{current.subject}")
        role, user_ids = None, None
    rows = await service.repository.chat_history_export(start_at, end_at, visitor_key=own_key, answer_type=answer_type if isinstance(answer_type, str) else None, rating=rating if isinstance(rating, str) else None, comment=comment if isinstance(comment, str) else None, role=role if isinstance(role, str) else None, user_ids=parsed_user_ids(user_ids))
    return xlsx_response(
        f"chathistory{datetime.now(ZoneInfo('Asia/Tokyo')):%Y%m%d%H%M}.xlsx",
        "チャット履歴",
        ["チャットID", "ユーザID", "ユーザ種別", "応答ID", "応答No", "質問", "回答", "回答種別", "評価", "コメント", "質問受付日時", "回答完了日時"],
        [[
            str(row["session_id"]), row.get("subject") or "", ROLE_LABELS.get(row.get("role"), row.get("role") or ""),
            str(row["interaction_id"]), row["sequence_number"], row.get("question_text") or "", row.get("answer_text") or "",
            ANSWER_TYPE_LABELS.get(row.get("answer_type"), row.get("answer_type") or ""),
            RATING_LABELS.get(row.get("rating"), row.get("rating") or ""), row.get("comment") or "",
            display_datetime(row.get("question_submitted_at")), display_datetime(row.get("answer_displayed_at")),
        ] for row in rows],
    )


@router.get("/usage/users.xlsx")
async def usage_users_xlsx(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    role: str | None = Query(None, pattern="^(staff|admin)$"),
    _: AuthSession = Depends(require_system_admin_session),
    service: ReportingService = Depends(get_service),
):
    try:
        start_at, end_at = utc_period(from_date, to_date)
    except ReportingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    role = role if isinstance(role, str) else None
    rows = await service.repository.usage_users(start_at, end_at, role=role)
    return xlsx_response(
        f"userlist{datetime.now(ZoneInfo('Asia/Tokyo')):%Y%m%d%H%M}.xlsx", "ユーザリスト",
        ["ユーザID", "ユーザ種別", "ユーザ名", "最終アクセス日時"],
        [[
            row.get("subject") or f"利用者-{row['visitor_key'][:12]}",
            ROLE_LABELS.get(row.get("role"), row.get("role") or ""), row.get("display_name") or "",
            display_datetime(row.get("last_seen_at")),
        ] for row in rows],
    )


@router.get("/usage/access-logs.xlsx")
async def access_logs_xlsx(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    surface: str | None = Query(None, pattern="^(CHAT|ADMIN)$"),
    role: str | None = Query(None, pattern="^(staff|admin)$"),
    user_ids: str | None = Query(None, max_length=5000),
    _: AuthSession = Depends(require_system_admin_session),
    service: ReportingService = Depends(get_service),
):
    try:
        start_at, end_at = utc_period(from_date, to_date)
    except ReportingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    surface = surface if isinstance(surface, str) else None
    role = role if isinstance(role, str) else None
    rows = await service.repository.access_logs(
        start_at, end_at, surface=surface, role=role, user_ids=parsed_user_ids(user_ids)
    )
    return xlsx_response(
        f"accesslog{datetime.now(ZoneInfo('Asia/Tokyo')):%Y%m%d%H%M}.xlsx", "アクセスログ",
        ["アクセス日時", "ユーザID", "ユーザ種別", "サイト", "アクセス元（IP）", "デバイス/UA"],
        [[
            display_datetime(row.get("accessed_at")), row.get("subject") or f"利用者-{row['visitor_key'][:12]}",
            ROLE_LABELS.get(row.get("role"), row.get("role") or ""),
            SURFACE_LABELS.get(row.get("surface"), row.get("surface") or ""),
            row.get("ip_address") or "", row.get("user_agent") or "",
        ] for row in rows],
    )


@router.get("/usage/operation-logs.xlsx")
async def operation_logs_xlsx(
    from_date: date = Query(..., alias="from"),
    to_date: date = Query(..., alias="to"),
    surface: str | None = Query(None, pattern="^(CHAT|ADMIN)$"),
    operation_type: str | None = Query(None, pattern="^(CREATE|UPDATE|DELETE|DOWNLOAD|UPLOAD)$"),
    role: str | None = Query(None, pattern="^(staff|admin)$"),
    user_ids: str | None = Query(None, max_length=5000),
    _: AuthSession = Depends(require_system_admin_session),
    service: ReportingService = Depends(get_service),
):
    try:
        start_at, end_at = utc_period(from_date, to_date)
    except ReportingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    surface = surface if isinstance(surface, str) else None
    operation_type = operation_type if isinstance(operation_type, str) else None
    role = role if isinstance(role, str) else None
    rows = await service.repository.operation_logs(
        start_at, end_at, role=role, user_ids=parsed_user_ids(user_ids)
    )
    if surface:
        rows = [row for row in rows if row.get("surface") == surface]
    if operation_type:
        rows = [row for row in rows if operation_kind(row["http_method"], row["request_path"]) == operation_type]
    return xlsx_response(
        f"operationlog{datetime.now(ZoneInfo('Asia/Tokyo')):%Y%m%d%H%M}.xlsx", "操作ログ",
        ["操作日時", "ユーザID", "ユーザ種別", "操作種別", "サイト", "アクセス元（IP）", "デバイス/UA"],
        [[
            display_datetime(row.get("operated_at")), row.get("operator_subject") or f"利用者-{row['operator_key'][:12]}",
            ROLE_LABELS.get(row.get("operator_role"), row.get("operator_role") or ""),
            operation_description(row["http_method"], row["request_path"]),
            SURFACE_LABELS.get(row.get("surface"), row.get("surface") or ""),
            row.get("ip_address") or "", row.get("user_agent") or "",
        ] for row in rows],
    )
