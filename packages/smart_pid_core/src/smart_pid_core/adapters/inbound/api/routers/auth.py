"""Auth router — login, token refresh, and the live session view."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from smart_pid_core.adapters.inbound.api.auth import (
    create_access_token,
    verify_password,
)
from smart_pid_core.adapters.inbound.api.dependencies import (
    client_ip,
    get_audit_repo,
    get_session_registry,
    get_settings,
    get_user_repo,
    require_admin,
    require_user,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.session_registry import SessionRegistry
from smart_pid_core.config import CoreSettings
from smart_pid_domain.dtos.auth import (
    AccessLogEntry,
    ActiveSessionResponse,
    LoginRequest,
    TokenResponse,
    UserClaims,
)
from smart_pid_domain.enums import AuditAction, UserRole

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger()

router = APIRouter()

_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW_SECONDS = 60.0


class LoginRateLimiter:
    """In-memory sliding-window login throttle, keyed by client IP.

    5 attempts per 60s per IP; a successful login clears that IP's budget
    so legitimate repeated logins (multiple tabs, a retried client) never
    get penalized. Deliberately per-IP, not per-username — counting by
    username would let a caller learn which usernames exist by watching
    which ones lock out.

    ponytail: single-process dict, no cross-worker/cross-restart state —
    a daemon restart or a second uvicorn worker resets/duplicates the
    budget. Acceptable for this single-process control-plane daemon; move
    to a shared store (Redis) only if the deployment ever scales past one
    process.
    """

    def __init__(
        self,
        *,
        max_attempts: int = _LOGIN_MAX_ATTEMPTS,
        window_seconds: float = _LOGIN_WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._clock = clock
        self._attempts: dict[str, list[float]] = {}

    def check(self, ip: str) -> None:
        """Record this attempt; raise 429 once `ip` is over budget."""
        now = self._clock()
        cutoff = now - self._window_seconds
        recent = [t for t in self._attempts.get(ip, []) if t > cutoff]
        recent.append(now)
        self._attempts[ip] = recent
        if len(recent) > self._max_attempts:
            logger.warning("login_rate_limited", client_ip=ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts, try again later",
            )

    def record_success(self, ip: str) -> None:
        """Clear the budget for `ip` after a successful login."""
        self._attempts.pop(ip, None)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    registry: Annotated[SessionRegistry, Depends(get_session_registry)],
) -> TokenResponse:
    source_ip = client_ip(request, trusted_proxies=settings.trusted_proxies)
    limiter = request.app.state.login_rate_limiter
    limiter.check(source_ip)
    user = await user_repo.get_by_username(body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    limiter.record_success(source_ip)
    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        secret=settings.jwt_secret,
        expiry_hours=settings.jwt_expiry_hours,
    )
    registry.record_login(
        user_id=user.id, username=user.username, role=user.role, ip=source_ip,
    )
    await user_repo.record_access(
        user_id=user.id,
        username=user.username,
        event=str(AuditAction.LOGIN),
        ip=source_ip,
    )
    await audit_repo.record(user.id, user.username, AuditAction.LOGIN, None, None)
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    current_user: Annotated[UserClaims, Depends(require_user)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
    registry: Annotated[SessionRegistry, Depends(get_session_registry)],
) -> None:
    """End the caller's session in the live view and log the sign-out.

    The token is NOT revoked — it stays valid until it expires, exactly as
    before this route existed. What it ends is the *session listing*: without
    it, a browser that pressed Sair kept showing as connected until its idle
    window closed, which is a claim the security panel must not make.
    """
    source_ip = client_ip(request, trusted_proxies=settings.trusted_proxies)
    registry.drop(user_id=current_user.user_id, ip=source_ip)
    await user_repo.record_access(
        user_id=current_user.user_id,
        username=current_user.username,
        event=str(AuditAction.LOGOUT),
        ip=source_ip,
    )
    await audit_repo.record(
        current_user.user_id, current_user.username, AuditAction.LOGOUT, None, None,
    )


@router.get("/sessions")
async def list_sessions(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    registry: Annotated[SessionRegistry, Depends(get_session_registry)],
) -> list[ActiveSessionResponse]:
    """Who is signed in right now, and from which source IP (admin-only).

    Read from process memory, not from a table: see ``SessionRegistry``.
    """
    return [
        ActiveSessionResponse(
            user_id=session.user_id,
            username=session.username,
            role=UserRole(session.role),
            ip=session.ip,
            since=session.since,
            last_seen=session.last_seen,
            online=session.sockets > 0,
        )
        for session in registry.list_active()
    ]


@router.get("/access-log")
async def access_log(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    limit: int = Query(50, ge=1, le=500),
) -> list[AccessLogEntry]:
    """Recent sign-ins / sign-outs of every account, newest first (admin-only).

    Sourced from ``users.db``, so it survives a project switch and is not
    carried off the platform by a ``.spid`` export.
    """
    return [AccessLogEntry(**row) for row in await user_repo.list_access(limit)]


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: Annotated[UserClaims, Depends(require_user)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
) -> TokenResponse:
    """Issue a fresh access token for an authenticated user."""
    token = create_access_token(
        user_id=current_user.user_id,
        username=current_user.username,
        role=current_user.role,
        secret=settings.jwt_secret,
        expiry_hours=settings.jwt_expiry_hours,
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserClaims)
async def me(
    current_user: Annotated[UserClaims, Depends(require_user)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> UserClaims:
    """Return the authenticated principal's claims.

    The SPA populates its AuthContext from this route after login and
    refetches it whenever a 403 arrives (spec §11) — a role changed
    mid-session is discovered here, not by decoding the JWT client-side.

    ``theme`` is read from the user row rather than the token: the palette
    belongs to the operator, not to the browser profile, and it is what
    makes the choice survive signing in somewhere else.
    """
    stored = await user_repo.get_by_id(current_user.user_id)
    if stored is None:
        return current_user
    return current_user.model_copy(update={"theme": stored.theme})
