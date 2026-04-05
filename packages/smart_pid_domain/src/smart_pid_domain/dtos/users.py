"""User management DTOs."""
from __future__ import annotations

from pydantic import BaseModel

from smart_pid_domain.enums import UserRole  # noqa: TC001


class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    active: bool = True
    created_at: str = ""


class UserUpdate(BaseModel):
    role: UserRole | None = None
    password: str | None = None
    active: bool | None = None
