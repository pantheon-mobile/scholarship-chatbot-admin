from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


IdentityKind = Literal["AUTHENTICATED", "ANONYMOUS"]
ProcessingStatus = Literal["PROCESSING", "COMPLETED", "FAILED"]
AnswerType = Literal["FAQ", "GENERATED_AI", "NO_ANSWER"]
Rating = Literal["GOOD", "BAD"]


class VisitorIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_kind: IdentityKind
    identifier: str = Field(min_length=1, max_length=512)

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("利用者識別子を入力してください。")
        return normalized

    @model_validator(mode="after")
    def validate_anonymous_identifier(self):
        if self.identity_kind == "ANONYMOUS":
            try:
                UUID(self.identifier)
            except ValueError as error:
                raise ValueError("匿名利用者識別子にはUUIDを指定してください。") from error
        return self


def require_timezone(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("日時にはタイムゾーンを指定してください。")
    return value


class AccessCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    identity: VisitorIdentity
    accessed_at: datetime
    surface: Literal["CHAT", "ADMIN"] = "CHAT"

    _timezone = field_validator("accessed_at")(require_timezone)


class AccessResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    visitor_id: UUID
    accessed_at: datetime
    recorded_at: datetime


class ChatSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    identity: VisitorIdentity
    started_at: datetime
    ended_at: datetime | None = None

    _timezone = field_validator("started_at", "ended_at")(lambda value: require_timezone(value) if value else value)

    @model_validator(mode="after")
    def validate_period(self):
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("終了日時は開始日時以降を指定してください。")
        return self


class ChatSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    visitor_id: UUID
    started_at: datetime
    ended_at: datetime | None
    recorded_at: datetime


class InteractionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    sequence_number: int = Field(ge=1)
    question_submitted_at: datetime
    question_text: str = Field(min_length=1, max_length=2000)

    _timezone = field_validator("question_submitted_at")(require_timezone)


class InteractionCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    processing_status: Literal["COMPLETED", "FAILED"]
    answer_type: AnswerType | None = None
    answer_displayed_at: datetime | None = None
    faq_id: int | None = Field(default=None, ge=1)
    answer_text: str | None = Field(default=None, max_length=20000)
    citations: list[dict[str, str | None]] = Field(default_factory=list)

    _timezone = field_validator("answer_displayed_at")(lambda value: require_timezone(value) if value else value)

    @model_validator(mode="after")
    def validate_state(self):
        if self.processing_status == "FAILED":
            if self.answer_type is not None or self.answer_displayed_at is not None or self.faq_id is not None or self.answer_text is not None:
                raise ValueError("FAILEDでは回答種別、表示完了日時、FAQ IDを指定できません。")
            return self
        if self.answer_type is None or self.answer_displayed_at is None:
            raise ValueError("COMPLETEDでは回答種別と回答表示完了日時が必要です。")
        if self.answer_type == "FAQ" and self.faq_id is None:
            raise ValueError("FAQ回答ではFAQ IDが必要です。")
        if self.answer_type != "FAQ" and self.faq_id is not None:
            raise ValueError("FAQ回答以外ではFAQ IDを指定できません。")
        if self.answer_text is None:
            raise ValueError("COMPLETEDでは回答本文が必要です。")
        return self


class InteractionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chat_session_id: UUID
    sequence_number: int
    question_submitted_at: datetime
    answer_displayed_at: datetime | None
    processing_status: ProcessingStatus
    answer_type: AnswerType | None
    faq_id: int | None
    question_text: str | None
    answer_text: str | None
    citations: list[dict[str, str | None]] | None
    created_at: datetime
    updated_at: datetime


class FeedbackUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: Rating
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        normalized = value.strip() if value is not None else ""
        return normalized or None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    interaction_id: UUID
    rating: Rating
    comment: str | None
    created_at: datetime
    updated_at: datetime
