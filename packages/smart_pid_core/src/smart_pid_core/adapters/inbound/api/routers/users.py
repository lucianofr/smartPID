"""User management router — admin-gated (spec §9.3).

New surface introduced by the two-role model: list / create / update role /
change password / deactivate. Every route requires ``require_admin``; the
frontend management panel arrives in phase 10.
"""

from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.auth import hash_password
from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    get_user_repo,
    require_admin,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository  # noqa: TC001
from smart_pid_core.adapters.outbound.user_repo import User, UserRepository  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims, UserCreate  # noqa: TC001
from smart_pid_domain.dtos.users import UserResponse, UserUpdate  # noqa: TC001
from smart_pid_domain.enums import AuditAction, UserRole

router = APIRouter()


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        role=UserRole(user.role),
        active=user.active,
        created_at=user.created_at,
    )


async def _reject_if_last_active_admin(
    user_repo: UserRepository, user_id: int
) -> None:
    """Reject changes that would leave the deployment without an active admin."""
    target = await user_repo.get_by_id(user_id)
    if target is None or not target.active or target.role != UserRole.ADMIN:
        return
    admins = [
        user
        for user in await user_repo.list_all()
        if user.active and user.role == UserRole.ADMIN
    ]
    if len(admins) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot demote or deactivate the last active admin",
        )


@router.get("", response_model=list[UserResponse])
async def list_users(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> list[UserResponse]:
    return [_to_response(user) for user in await user_repo.list_all()]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    try:
        created = await user_repo.create(
            body.username, hash_password(body.password), body.role.value
        )
    except aiosqlite.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from None
    await audit_repo.record(
        admin.user_id,
        admin.username,
        AuditAction.CREATE_USER,
        body.username,
        f"role={body.role.value}",
    )
    return _to_response(created)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdate,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    if await user_repo.get_by_id(user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if body.role == UserRole.USER or body.active is False:
        await _reject_if_last_active_admin(user_repo, user_id)
    updated = await user_repo.update(
        user_id,
        role=body.role.value if body.role is not None else None,
        password_hash=(
            hash_password(body.password) if body.password is not None else None
        ),
        active=body.active,
    )
    if updated is None:  # pragma: no cover — guarded by the 404 above
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    changed = [
        name
        for name, value in (
            ("role", body.role),
            ("password", body.password),
            ("active", body.active),
        )
        if value is not None
    ]
    await audit_repo.record(
        admin.user_id,
        admin.username,
        AuditAction.UPDATE_USER,
        updated.username,
        f"changed={','.join(changed) or 'nothing'}",
    )
    return _to_response(updated)


@router.delete("/{user_id}", response_model=UserResponse)
async def deactivate_user(
    user_id: int,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    if await user_repo.get_by_id(user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    await _reject_if_last_active_admin(user_repo, user_id)
    updated = await user_repo.deactivate(user_id)
    if updated is None:  # pragma: no cover — guarded by the 404 above
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    await audit_repo.record(
        admin.user_id,
        admin.username,
        AuditAction.DEACTIVATE_USER,
        updated.username,
        None,
    )
    return _to_response(updated)
