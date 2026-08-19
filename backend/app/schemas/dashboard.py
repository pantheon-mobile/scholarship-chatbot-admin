from datetime import date

from pydantic import BaseModel


class ResponseTimeMetrics(BaseModel):
    average_seconds: float | None
    minimum_seconds: float | None
    maximum_seconds: float | None


class BasicMetrics(BaseModel):
    access_count: int
    access_user_count: int
    chat_count: int
    chat_user_count: int
    average_chats_per_day: float | None
    average_chats_per_user: float | None
    response_count: int
    average_responses_per_chat: float | None
    average_responses_per_user: float | None
    response_time: ResponseTimeMetrics
    valid_answer_count: int
    no_answer_count: int
    answer_rate: float | None
    good_count: int
    bad_count: int
    unrated_count: int
    satisfaction_rate: float | None
    comment_count: int
    good_comment_count: int
    bad_comment_count: int


class AnswerTypeMetrics(BaseModel):
    total_count: int
    faq_count: int
    faq_rate: float | None
    generated_ai_count: int
    generated_ai_rate: float | None
    no_answer_count: int


class TimeBucket(BaseModel):
    key: str
    label: str
    chat_count: int
    response_count: int


class WeekdayBucket(BaseModel):
    key: str
    label: str
    chat_count: int
    response_count: int


class DashboardPeriod(BaseModel):
    from_date: date
    to_date: date
    timezone: str


class DashboardResponse(BaseModel):
    period: DashboardPeriod
    basic_metrics: BasicMetrics
    answer_types: AnswerTypeMetrics
    time_buckets: list[TimeBucket]
    weekday_buckets: list[WeekdayBucket]
