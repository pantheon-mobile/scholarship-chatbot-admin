from typing import Annotated
from pydantic import BeforeValidator
from app.services.resource_limits import validate_bulk_delete_items, validate_reorder_items
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


class CategoryCreateRequest(BaseModel):
    name: str
    parent_id: int | None = None


class CategoryUpdateRequest(CategoryCreateRequest):
    version: int = Field(ge=1)


class CategoryDeleteTarget(BaseModel):
    id: int
    version: int = Field(ge=1)


class CategoryBulkDeleteRequest(BaseModel):
    items: Annotated[list[CategoryDeleteTarget], BeforeValidator(validate_bulk_delete_items)]


class CategoryBulkDeleteResponse(BaseModel):
    deleted_count: int


class CategoryOrderRequest(BaseModel):
    parent_id: int | None = None
    items: Annotated[list[CategoryDeleteTarget], BeforeValidator(validate_reorder_items)]
