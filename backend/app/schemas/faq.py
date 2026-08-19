from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

FaqSortColumn = Literal["id", "updated_at"]
SortOrder = Literal["asc", "desc"]


class FaqFilters(BaseModel):
    keyword: str | None = None
    classification_1_value_id: int | None = Field(default=None, ge=1)
    classification_2_value_id: int | None = Field(default=None, ge=1)
    classification_3_value_id: int | None = Field(default=None, ge=1)
    classification_4_value_id: int | None = Field(default=None, ge=1)
    chat_enabled: bool | None = None
    sort: FaqSortColumn = "updated_at"
    order: SortOrder = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = 10

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: str | None) -> str | None:
        normalized = value.strip() if value is not None else ""
        return normalized or None

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, value: int) -> int:
        if value not in (10, 20, 50, 100):
            raise ValueError("表示件数は10、20、50、100のいずれかを指定してください。")
        return value


class FaqClassificationResponse(BaseModel):
    type_code: str
    classification_type_id: int
    classification_value_id: int
    display_label: str
    value_name: str


class FaqSimilarQuestionResponse(BaseModel):
    id: int
    question: str
    display_order: int


class FaqResponse(BaseModel):
    id: int
    question: str
    answer: str
    chat_enabled: bool
    updated_at: datetime
    version: int
    classifications: list[FaqClassificationResponse]


class FaqListResponse(BaseModel):
    items: list[FaqResponse]
    page: int
    page_size: int
    total_count: int
    total_pages: int
    sort: FaqSortColumn
    order: SortOrder


class FaqCreateRequest(BaseModel):
    question: str
    answer: str
    similar_questions: list[str] = Field(default_factory=list)
    classification_1_value_id: int | None = Field(default=None, ge=1)
    classification_2_value_id: int | None = Field(default=None, ge=1)
    classification_3_value_id: int | None = Field(default=None, ge=1)
    classification_4_value_id: int | None = Field(default=None, ge=1)
    chat_enabled: bool


class FaqUpdateRequest(FaqCreateRequest):
    version: int = Field(ge=1)


class FaqDetailResponse(FaqResponse):
    created_at: datetime
    similar_questions: list[FaqSimilarQuestionResponse]


class FaqDeleteTarget(BaseModel):
    id: int = Field(ge=1)
    version: int = Field(ge=1)


class FaqBulkDeleteRequest(BaseModel):
    items: list[FaqDeleteTarget] = Field(min_length=1)


class FaqBulkDeleteResponse(BaseModel):
    deleted_count: int


class FaqImportRowError(BaseModel):
    row: int
    column: str
    code: str
    message: str


class FaqImportResponse(BaseModel):
    created_count: int
    updated_count: int
    processed_count: int
