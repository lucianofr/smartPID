"""Auth router — login and token refresh (single-admin deployment)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.auth import (
    create_access_token,
    verify_password,
)
from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    get_settings,
    get_user_repo,
    require_user,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.config import CoreSettings
from smart_pid_domain.dtos.auth import (
    LoginRequest,
    TokenResponse,
    UserClaims,
)
from smart_pid_domain.enums import AuditAction

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> TokenResponse:
    user = await user_repo.get_by_username(body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        secret=settings.jwt_secret,
        expiry_hours=settings.jwt_expiry_hours,
    )
    await audit_repo.record(user.id, user.username, AuditAction.LOGIN, None, None)
    return TokenResponse(access_token=token)


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
) -> UserClaims:
    """Return the authenticated principal's claims.

    The SPA populates its AuthContext from this route after login and
    refetches it whenever a 403 arrives (spec §11) — a role changed
    mid-session is discovered here, not by decoding the JWT client-side.
    """
    return current_user
