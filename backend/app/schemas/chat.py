from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatMessageRequest(BaseModel):
    interaction_id: UUID
    question: str = Field(min_length=1, max_length=5000)
    # Legacy field accepted for older clients; never trusted as conversation ownership.
    bedrock_session_id: str | None = Field(default=None, max_length=2048)
    chat_session_id: UUID | None = None


class ChatCitation(BaseModel):
    @field_validator("uri")
    @classmethod
    def safe_uri(cls, value):
        from app.services.citation_validation import safe_citation_uri
        return safe_citation_uri(value)

    title: str
    # Internal lookup only; preserve the string-only citation history contract.
    data_source_id: int | None = Field(default=None, exclude=True)
    uri: str | None = None
    excerpt: str | None = None


class ChatMessageResponse(BaseModel):
    answer: str
    answer_type: str
    context_reference: str | None = None
    faq_id: int | None = None
    bedrock_session_id: str | None = None
    citations: list[ChatCitation]


class ChatUiConfigResponse(BaseModel):
    title: str
    admin_title: str
    header_icon_url: str | None
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
    feedback_reason: str | None = None
    feedback_comment: str | None = None
    answer_type: Literal["FAQ", "GENERATED_AI", "NO_ANSWER"] | None = None


class ChatHistoryDetail(BaseModel):
    id: UUID
    title: str
    messages: list[ChatHistoryMessage]
    next_sequence_number: int = 1


class ChatHistoryTitleUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
