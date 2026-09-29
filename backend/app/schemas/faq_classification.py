from typing import Annotated
from pydantic import BeforeValidator
from app.services.resource_limits import validate_faq_label, validate_faq_value, validate_reorder_items
from pydantic import BaseModel, ConfigDict, Field


class FaqClassificationLabelUpdate(BaseModel):
    display_label: Annotated[str, BeforeValidator(validate_faq_label), Field(max_length=100)]
    version: int = Field(ge=1)


class FaqClassificationValueCreate(BaseModel):
    value_name: Annotated[str, BeforeValidator(validate_faq_value), Field(max_length=200)]


class FaqClassificationValueUpdate(BaseModel):
    value_name: Annotated[str, BeforeValidator(validate_faq_value), Field(max_length=200)]
    version: int = Field(ge=1)


class FaqClassificationOrderItem(BaseModel):
    id: int = Field(ge=1)
    version: int = Field(ge=1)


class FaqClassificationOrderUpdate(BaseModel):
    items: Annotated[list[FaqClassificationOrderItem], BeforeValidator(validate_reorder_items)] = Field(min_length=1)


class FaqClassificationValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    value_name: str
    display_order: int
    version: int


class FaqClassificationTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type_code: str
    fixed_name: str
    display_label: str
    display_order: int
    version: int
    values: list[FaqClassificationValueResponse]


class FaqClassificationListResponse(BaseModel):
    items: list[FaqClassificationTypeResponse]
