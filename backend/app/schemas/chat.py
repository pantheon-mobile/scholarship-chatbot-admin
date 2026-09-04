from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    bedrock_session_id: str | None = Field(default=None, max_length=2048)


class ChatCitation(BaseModel):
    title: str
    uri: str | None = None
    excerpt: str | None = None


class ChatMessageResponse(BaseModel):
    answer: str
    answer_type: str
    faq_id: int | None = None
    bedrock_session_id: str | None = None
    citations: list[ChatCitation]


class ChatUiConfigResponse(BaseModel):
    title: str
    initial_message: str
    input_placeholder: str
    question_max_length: int
    frame_color: str
    bot_icon_url: str | None
    history_enabled: bool
    maintenance_enabled: bool
    maintenance_message: str
    good_message: str
    bad_message: str
    good_options: list[str]
    bad_options: list[str]


class ChatHistorySummary(BaseModel):
    id: UUID
    title: str
    started_at: datetime
    updated_at: datetime


class ChatHistoryMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    sent_at: datetime
    citations: list[ChatCitation] = Field(default_factory=list)
    interaction_id: UUID | None = None
    rating: Literal["GOOD", "BAD"] | None = None
    answer_type: Literal["FAQ", "GENERATED_AI", "NO_ANSWER"] | None = None


class ChatHistoryDetail(BaseModel):
    id: UUID
    title: str
    messages: list[ChatHistoryMessage]


class ChatHistoryTitleUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
