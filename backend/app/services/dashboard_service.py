from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from app.repositories.dashboard import DashboardRepository
from app.schemas.dashboard import (
    AnswerTypeMetrics,
    BasicMetrics,
    DashboardPeriod,
    DashboardResponse,
    ResponseTimeMetrics,
    TimeBucket,
    WeekdayBucket,
)


JST = ZoneInfo("Asia/Tokyo")
TIME_BUCKETS = [
    ("9-12", "9時～12時"),
    ("12-15", "12時～15時"),
    ("15-18", "15時～18時"),
    ("18-21", "18時～21時"),
    ("21-0", "21時～0時"),
    ("0-3", "0時～3時"),
    ("3-6", "3時～6時"),
    ("6-9", "6時～9時"),
]
WEEKDAY_BUCKETS = [
    ("MONDAY", "月"), ("TUESDAY", "火"), ("WEDNESDAY", "水"), ("THURSDAY", "木"),
    ("FRIDAY", "金"), ("SATURDAY", "土"), ("SUNDAY", "日"),
]


class DashboardError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def rounded(value) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return rounded(Decimal(numerator) * Decimal(100) / Decimal(denominator))


def average(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return rounded(Decimal(numerator) / Decimal(denominator))


class DashboardService:
    def __init__(self, repository: DashboardRepository) -> None:
        self.repository = repository

    async def get(self, from_date: date, to_date: date) -> DashboardResponse:
        if from_date > to_date:
            raise DashboardError("INVALID_DATE_RANGE", "開始日は終了日以前を指定してください。")
        start_jst = datetime.combine(from_date, time.min, tzinfo=JST)
        end_jst = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=JST)
        data = await self.repository.aggregate(start_jst.astimezone(timezone.utc), end_jst.astimezone(timezone.utc))
        access = data["access"]
        sessions = data["sessions"]
        interactions = data["interactions"]
        access_count = int(access["access_count"] or 0)
        access_users = int(access["access_user_count"] or 0)
        chat_count = int(sessions["chat_count"] or 0)
        chat_users = int(sessions["chat_user_count"] or 0)
        response_count = int(interactions["response_count"] or 0)
        valid = int(interactions["valid_answer_count"] or 0)
        faq = int(interactions["faq_count"] or 0)
        ai = int(interactions["generated_ai_count"] or 0)
        no_answer = int(interactions["no_answer_count"] or 0)
        good = int(interactions["good_count"] or 0)
        bad = int(interactions["bad_count"] or 0)
        unrated = valid - good - bad
        days = (to_date - from_date).days + 1

        return DashboardResponse(
            period=DashboardPeriod(from_date=from_date, to_date=to_date, timezone="Asia/Tokyo"),
            basic_metrics=BasicMetrics(
                access_count=access_count,
                access_user_count=access_users,
                chat_count=chat_count,
                chat_user_count=chat_users,
                average_chats_per_day=average(chat_count, days),
                average_chats_per_user=average(chat_count, chat_users),
                response_count=response_count,
                average_responses_per_chat=average(response_count, chat_count),
                average_responses_per_user=average(response_count, chat_users),
                response_time=ResponseTimeMetrics(
                    average_seconds=rounded(interactions["response_time_average"]),
                    minimum_seconds=rounded(interactions["response_time_minimum"]),
                    maximum_seconds=rounded(interactions["response_time_maximum"]),
                ),
                valid_answer_count=valid,
                no_answer_count=no_answer,
                answer_rate=ratio(valid, response_count),
                good_count=good,
                bad_count=bad,
                unrated_count=unrated,
                satisfaction_rate=ratio(good, good + bad),
                comment_count=int(interactions["comment_count"] or 0),
                good_comment_count=int(interactions["good_comment_count"] or 0),
                bad_comment_count=int(interactions["bad_comment_count"] or 0),
            ),
            answer_types=AnswerTypeMetrics(
                total_count=response_count,
                faq_count=faq,
                faq_rate=ratio(faq, response_count),
                generated_ai_count=ai,
                generated_ai_rate=ratio(ai, response_count),
                no_answer_count=no_answer,
            ),
            time_buckets=[TimeBucket(
                key=key,
                label=label,
                chat_count=data["session_time"].get(index, 0),
                response_count=data["interaction_time"].get(index, 0),
            ) for index, (key, label) in enumerate(TIME_BUCKETS)],
            weekday_buckets=[WeekdayBucket(
                key=key,
                label=label,
                chat_count=data["session_weekdays"].get(index, 0),
                response_count=data["interaction_weekdays"].get(index, 0),
            ) for index, (key, label) in enumerate(WEEKDAY_BUCKETS, start=1)],
        )
