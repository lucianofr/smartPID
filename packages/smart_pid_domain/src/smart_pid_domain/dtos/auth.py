"""Auth-related DTOs for login, registration, and JWT claims."""
from __future__ import annotations

from pydantic import BaseModel, Field

from smart_pid_domain.enums import UserRole  # noqa: TC001


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=200)


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
    # Chosen HMI palette, filled in by ``GET /auth/me`` from the user row.
    # Absent from the JWT on purpose: the token is minted at login and the
    # operator can change palette at any point in the session, so carrying
    # it in the claims would serve a stale value until the next login.
    theme: str | None = None
