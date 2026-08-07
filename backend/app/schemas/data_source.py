from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


SourceType = Literal["FILE", "WEB"]
DataSourceStatus = Literal["PREPARING", "TRAINING", "AVAILABLE", "ERROR"]
Priority = Literal["HIGH", "MEDIUM", "LOW"]
SortColumn = Literal["id", "title", "updated_at"]
SortOrder = Literal["asc", "desc"]


class DataSourceFileResponse(BaseModel):
    file_name: str


class DataSourceWebsiteResponse(BaseModel):
    url: str


class DataSourceClassificationResponse(BaseModel):
    type_code: str
    classification_type_id: int
    classification_value_id: int
    display_label: str
    value_name: str


class DataSourceResponse(BaseModel):
    id: int
    source_type: SourceType
    title: str
    format: str
    status: DataSourceStatus
    category_name: str | None
    size_bytes: int | None
    character_count: int | None
    answer_source_enabled: bool
    priority: Priority
    reference_link_visible: bool
    updated_at: datetime
    version: int
    file: DataSourceFileResponse | None
    website: DataSourceWebsiteResponse | None
    classifications: list[DataSourceClassificationResponse]


class DataSourceListResponse(BaseModel):
    items: list[DataSourceResponse]
    page: int
    page_size: int
    total_count: int
    total_pages: int
    total_size_bytes: int
    sort: SortColumn
    order: SortOrder


class DataSourceFilters(BaseModel):
    keyword: str | None = None
    format: str | None = None
    status: DataSourceStatus | None = None
    type_1_value_id: int | None = None
    type_2_value_id: int | None = None
    type_3_value_id: int | None = None
    answer_source_enabled: bool | None = None
    priority: Priority | None = None
    reference_link_visible: bool | None = None
    sort: SortColumn = "updated_at"
    order: SortOrder = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = 10

    @field_validator("keyword")
    @classmethod
    def normalize_keyword(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, value: int) -> int:
        if value not in (10, 20, 50, 100):
            raise ValueError("表示件数は10、20、50、100のいずれかを指定してください。")
        return value


class ToggleAnswerSourceRequest(BaseModel):
    enabled: bool
    version: int = Field(ge=1)


class ToggleReferenceLinkRequest(BaseModel):
    visible: bool
    version: int = Field(ge=1)


class DeleteTarget(BaseModel):
    id: int
    version: int = Field(ge=1)


class BulkDeleteRequest(BaseModel):
    items: list[DeleteTarget] = Field(min_length=1)


class BulkDeleteResponse(BaseModel):
    deleted_count: int


class ClassificationAssignment(BaseModel):
    classification_type_id: int
    classification_value_id: int


class FileUploadResponse(BaseModel):
    items: list[DataSourceResponse]
    created_count: int


class FileDataSourceUpdateRequest(BaseModel):
    title: str = Field(max_length=500)
    type_1_value_id: int | None = Field(default=None, ge=1)
    type_2_value_id: int | None = Field(default=None, ge=1)
    type_3_value_id: int | None = Field(default=None, ge=1)
    priority: Priority
    answer_source_enabled: bool
    reference_link_visible: bool
    version: int = Field(ge=1)
