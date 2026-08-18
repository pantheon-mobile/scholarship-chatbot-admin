from datetime import datetime

from pydantic import BaseModel, Field


class CategoryResponse(BaseModel):
    id: int
    name: str
    parent_id: int | None
    display_order: int
    version: int
    has_children: bool
    created_at: datetime
    updated_at: datetime


class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]


class CategoryDeleteTarget(BaseModel):
    id: int
    version: int = Field(ge=1)


class CategoryBulkDeleteRequest(BaseModel):
    items: list[CategoryDeleteTarget]


class CategoryBulkDeleteResponse(BaseModel):
    deleted_count: int


class CategoryOrderRequest(BaseModel):
    parent_id: int | None = None
    items: list[CategoryDeleteTarget]
