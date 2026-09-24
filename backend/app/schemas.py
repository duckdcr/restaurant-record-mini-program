from datetime import datetime

from pydantic import BaseModel, Field


class DevLoginRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)


class WechatLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)
    display_name: str = Field(default="微信用户", max_length=80)
    avatar_url: str = Field(default="", max_length=500)


class UserResponse(BaseModel):
    id: int
    display_name: str
    avatar_url: str


class LoginResponse(BaseModel):
    access_token: str
    user: UserResponse


class ApiErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict = {}

