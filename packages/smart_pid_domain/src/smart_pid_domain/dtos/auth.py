"""Auth-related DTOs for login, registration, and JWT claims."""
from __future__ import annotations

from pydantic import BaseModel, Field

from smart_pid_domain.enums import UserRole  # noqa: TC001


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    """Create-user request body for ``POST /users``.

    Spec §9.3 refers to this DTO as "RegisterRequest"; in this codebase the
    symbol has always been ``UserCreate`` (kept — not renamed). Dead code in
    the single-admin deployment, reactivated by the users router.
    """

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    role: UserRole = UserRole.USER


class UserClaims(BaseModel):
    user_id: int
    username: str
    role: UserRole
