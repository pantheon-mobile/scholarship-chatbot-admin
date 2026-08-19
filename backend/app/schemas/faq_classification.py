from pydantic import BaseModel, ConfigDict, Field


class FaqClassificationLabelUpdate(BaseModel):
    display_label: str
    version: int = Field(ge=1)


class FaqClassificationValueCreate(BaseModel):
    value_name: str


class FaqClassificationValueUpdate(BaseModel):
    value_name: str
    version: int = Field(ge=1)


class FaqClassificationOrderItem(BaseModel):
    id: int = Field(ge=1)
    version: int = Field(ge=1)


class FaqClassificationOrderUpdate(BaseModel):
    items: list[FaqClassificationOrderItem] = Field(min_length=1)


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
