"""User and role shapes. Scaffolded now, used when logins land."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .enums import RoleCode


class UserBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    username: str = Field(min_length=2, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    email: str | None = None
    role_code: str = RoleCode.VIEWER.value
    entity_codes: list[str] = Field(default_factory=list)
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=256)


class User(UserBase):
    id: int
    created_at: str | None = None
    last_login_at: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str
