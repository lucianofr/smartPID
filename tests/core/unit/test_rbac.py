"""Tests for the two-role authorization gates (Phase 0 spec §9).

Roles are lowercase ``admin`` | ``user``. ``require_user`` accepts any authenticated
principal; ``require_admin`` accepts only ``admin`` and rejects ``user`` with 403.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from smart_pid_core.adapters.inbound.api.dependencies import (
    require_admin,
    require_user,
)
from smart_pid_domain.dtos.auth import UserClaims


def _u(role: str, uid: int = 1) -> UserClaims:
    return UserClaims(user_id=uid, username=role, role=role)  # type: ignore[arg-type]


def test_require_user_admin():
    assert require_user(_u("admin")) is not None


def test_require_user_user():
    assert require_user(_u("user")) is not None


def test_require_admin_admin():
    assert require_admin(_u("admin")) is not None


def test_require_admin_user_rejected():
    with pytest.raises(HTTPException) as exc:
        require_admin(_u("user"))
    assert exc.value.status_code == 403
