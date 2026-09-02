from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChatHistoryItem(BaseModel):
    session_id: UUID
    user_label: str
    started_at: datetime
    ended_at: datetime | None
    response_count: int
    completed_count: int
    failed_count: int
    faq_count: int
    generated_ai_count: int
    no_answer_count: int
    good_count: int
    bad_count: int


class ChatHistoryResponse(BaseModel):
    from_date: date
    to_date: date
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_count: int
    items: list[ChatHistoryItem]
