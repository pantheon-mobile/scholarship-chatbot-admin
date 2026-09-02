from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CpfTokenExchangeRequest(BaseModel):
    token: str = Field(min_length=1, max_length=16384)


class DevelopmentCpfTokenRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=500)
    display_name: str = Field(min_length=1, max_length=500)
    role: Literal["admin", "staff"]


class DevelopmentCpfTokenResponse(BaseModel):
    token: str


class AuthenticatedUserResponse(BaseModel):
    subject: str
    display_name: str
    role: Literal["admin", "staff", "student"]
    site: Literal["student", "faculty"]
