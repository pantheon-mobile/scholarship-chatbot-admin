from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClassificationValueBase(BaseModel):
    value_name: str = Field(..., max_length=200)

    @field_validator("value_name")
    @classmethod
    def strip_value_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("種別値を入力してください。")
        return trimmed


class ClassificationValueCreate(ClassificationValueBase):
    pass


class ClassificationValueUpdate(ClassificationValueBase):
    version: int


class ClassificationValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    value_name: str
    display_order: int
    version: int

class ClassificationTypeBase(BaseModel):
    display_label: str = Field(..., max_length=100)

    @field_validator("display_label")
    @classmethod
    def strip_display_label(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("種別ラベルを入力してください。")
        return trimmed


class ClassificationTypeUpdate(ClassificationTypeBase):
    version: int


class ClassificationTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type_code: str
    fixed_name: str
    display_label: str
    display_order: int
    version: int
    values: List[ClassificationValueResponse]
