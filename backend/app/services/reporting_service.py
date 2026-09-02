from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models.auth import AuthSession
from app.repositories.reporting import ReportingRepository
from app.schemas.reporting import ChatHistoryItem, ChatHistoryResponse
from app.services.analytics_service import AnalyticsService


JST = ZoneInfo("Asia/Tokyo")


class ReportingError(Exception):
    pass


def utc_period(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    if from_date > to_date:
        raise ReportingError("開始日は終了日以前を指定してください。")
    start = datetime.combine(from_date, time.min, tzinfo=JST)
    end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=JST)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


class ReportingService:
    def __init__(self, repository: ReportingRepository) -> None:
        self.repository = repository

    async def chat_histories(
        self,
        from_date: date,
        to_date: date,
        page: int,
        page_size: int,
        current: AuthSession,
    ) -> ChatHistoryResponse:
        start_at, end_at = utc_period(from_date, to_date)
        own_key = None
        if current.role == "staff":
            own_key = AnalyticsService(self.repository).visitor_key(
                "AUTHENTICATED", f"{current.site}:{current.subject}"
            )
        total, rows = await self.repository.chat_histories(
            start_at, end_at,
            visitor_key=own_key,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return ChatHistoryResponse(
            from_date=from_date,
            to_date=to_date,
            page=page,
            page_size=page_size,
            total_count=total,
            items=[ChatHistoryItem(
                **{key: value for key, value in row.items() if key != "visitor_key"},
                user_label="自分" if current.role == "staff" else f"利用者-{row['visitor_key'][:12]}",
            ) for row in rows],
        )
