"""Auth router — login and user registration."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.auth import (
    create_access_token,
    hash_password,
    verify_password,
)
from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    get_settings,
    get_user_repo,
    require_admin,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.config import CoreSettings
from smart_pid_domain.dtos.auth import (
    LoginRequest,
    TokenResponse,
    UserClaims,
    UserCreate,
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


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: UserCreate,
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    _admin: Annotated[UserClaims, Depends(require_admin)],
) -> dict:
    existing = await user_repo.get_by_username(body.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' already exists",
        )
    pw_hash = hash_password(body.password)
    user = await user_repo.create(body.username, pw_hash, body.role)
    return {"id": user.id, "username": user.username, "role": user.role}
