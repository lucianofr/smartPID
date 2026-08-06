"""Auth-related DTOs for login, registration, and JWT claims."""
from __future__ import annotations

from datetime import datetime

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


class ActiveSessionResponse(BaseModel):
    """One live session in ``GET /auth/sessions`` (admin-only).

    A row is one (user, source IP) pair, so an operator with three tabs open
    appears once. ``online`` means at least one realtime socket is open right
    now; a row without it is still within the idle window of its last request.
    """

    user_id: int
    username: str
    role: UserRole
    ip: str
    since: datetime
    last_seen: datetime
    online: bool


class AccessLogEntry(BaseModel):
    """One row of ``GET /auth/access-log`` (admin-only).

    ``event`` is an ``AuditAction`` value (``LOGIN`` / ``LOGOUT``) but stays a
    plain string: the log is append-only history, and a row written by an
    older build must never fail to deserialize because the enum moved on.
    """

    id: int
    user_id: int
    username: str
    event: str
    ip: str
    timestamp: datetime
