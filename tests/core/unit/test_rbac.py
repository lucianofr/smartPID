"""Tests for RBAC FastAPI dependencies."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from smart_pid_core.adapters.inbound.api.dependencies import (
    require_admin,
    require_operator,
    require_supervisor,
)
from smart_pid_domain.dtos.auth import UserClaims


def test_require_operator_allows_operator():
    user = UserClaims(user_id=1, username="op1", role="OPERATOR")
    result = require_operator(user)
    assert result.username == "op1"


def test_require_operator_allows_supervisor():
    user = UserClaims(user_id=1, username="sup1", role="SUPERVISOR")
    result = require_operator(user)
    assert result.username == "sup1"


def test_require_operator_allows_admin():
    user = UserClaims(user_id=1, username="admin", role="ADMIN")
    result = require_operator(user)
    assert result.username == "admin"


def test_require_supervisor_allows_supervisor():
    user = UserClaims(user_id=1, username="sup1", role="SUPERVISOR")
    result = require_supervisor(user)
    assert result.username == "sup1"


def test_require_supervisor_allows_admin():
    user = UserClaims(user_id=1, username="admin", role="ADMIN")
    result = require_supervisor(user)
    assert result.username == "admin"


def test_require_supervisor_rejects_operator():
    user = UserClaims(user_id=1, username="op1", role="OPERATOR")
    with pytest.raises(HTTPException) as exc_info:
        require_supervisor(user)
    assert exc_info.value.status_code == 403


def test_require_admin_rejects_supervisor():
    user = UserClaims(user_id=1, username="sup1", role="SUPERVISOR")
    with pytest.raises(HTTPException) as exc_info:
        require_admin(user)
    assert exc_info.value.status_code == 403


def test_require_admin_rejects_operator():
    user = UserClaims(user_id=1, username="op1", role="OPERATOR")
    with pytest.raises(HTTPException) as exc_info:
        require_admin(user)
    assert exc_info.value.status_code == 403
