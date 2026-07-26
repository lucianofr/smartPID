"""Tests for the single-admin authentication gate.

This deployment is single-user: there are no role tiers. ``require_authenticated_admin``
simply returns the authenticated user; the 401 path lives in ``get_current_user``.
"""
from __future__ import annotations

from smart_pid_core.adapters.inbound.api.dependencies import (
    require_authenticated_admin,
)
from smart_pid_domain.dtos.auth import UserClaims


def test_authenticated_user_passes():
    user = UserClaims(user_id=1, username="admin", role="admin")
    result = require_authenticated_admin(user)
    assert result.username == "admin"


def test_returns_same_user_unchanged():
    user = UserClaims(user_id=7, username="admin", role="admin")
    assert require_authenticated_admin(user) is user
