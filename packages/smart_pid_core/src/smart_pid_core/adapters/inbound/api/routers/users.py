"""User management router — admin only."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.auth import hash_password
from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    get_user_repo,
    require_admin,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository  # noqa: TC001
from smart_pid_core.adapters.outbound.user_repo import UserRepository  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims, UserCreate  # noqa: TC001
from smart_pid_domain.dtos.users import UserResponse, UserUpdate
from smart_pid_domain.enums import AuditAction

router = APIRouter()


@router.get("")
async def list_users(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> list[UserResponse]:
    users = await user_repo.list_all()
    return [
        UserResponse(
            id=u.id, username=u.username, role=u.role,
            active=u.active, created_at=u.created_at,
        )
        for u in users
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    existing = await user_repo.get_by_username(body.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )
    pw_hash = hash_password(body.password)
    user = await user_repo.create(body.username, pw_hash, body.role)
    await audit_repo.record(
        admin.user_id, admin.username, AuditAction.CREATE_USER,
        f"user:{user.id}", f'{{"username": "{user.username}", "role": "{user.role}"}}',
    )
    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        active=user.active, created_at=user.created_at,
    )


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    _admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> UserResponse:
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        active=user.active, created_at=user.created_at,
    )


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    pw_hash = hash_password(body.password) if body.password else None
    user = await user_repo.update(
        user_id, role=body.role, password_hash=pw_hash, active=body.active,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await audit_repo.record(
        admin.user_id, admin.username, AuditAction.UPDATE_USER,
        f"user:{user_id}", f'{{"role": "{user.role}"}}',
    )
    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        active=user.active, created_at=user.created_at,
    )


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: int,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    user = await user_repo.deactivate(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await audit_repo.record(
        admin.user_id, admin.username, AuditAction.DEACTIVATE_USER,
        f"user:{user_id}", None,
    )
    return UserResponse(
        id=user.id, username=user.username, role=user.role,
        active=user.active, created_at=user.created_at,
    )
