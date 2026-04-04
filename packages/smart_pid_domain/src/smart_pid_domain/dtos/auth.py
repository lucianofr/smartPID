"""Auth-related DTOs for login, registration, and JWT claims."""
from __future__ import annotations

from pydantic import BaseModel

from smart_pid_domain.enums import UserRole  # noqa: TC001


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole = UserRole.OPERATOR


class UserClaims(BaseModel):
    user_id: int
    username: str
    role: UserRole
