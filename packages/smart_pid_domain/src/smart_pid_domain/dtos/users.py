"""User management DTOs."""
from __future__ import annotations

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    active: bool = True
    created_at: str = ""


class UserUpdate(BaseModel):
    role: str | None = None
    password: str | None = None
