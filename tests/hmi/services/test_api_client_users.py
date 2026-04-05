"""Tests for APIClient user management methods."""
from __future__ import annotations

import httpx

from smart_pid_hmi.services.api_client import APIClient
from smart_pid_hmi.services.session import Session


def _mock_transport(status: int, json_body: dict | list) -> httpx.MockTransport:
    """Create a mock transport that always returns the given response."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body)
    return httpx.MockTransport(handler)


def _make_client(status: int = 200, json_body: dict | list | None = None) -> APIClient:
    transport = _mock_transport(status, json_body or {})
    session = Session()
    return APIClient(base_url="http://test:8000", session=session, transport=transport)


def test_list_users():
    data = [
        {"id": 1, "username": "admin", "role": "ADMIN", "active": True, "created_at": "2026-01-01"},
        {"id": 2, "username": "op1", "role": "OPERATOR",
         "active": True, "created_at": "2026-01-02"},
    ]
    client = _make_client(200, data)
    users = client.list_users()
    assert len(users) == 2
    assert users[0].username == "admin"
    assert users[1].role == "OPERATOR"


def test_create_user():
    data = {"id": 3, "username": "newuser", "role": "OPERATOR", "active": True, "created_at": ""}
    client = _make_client(201, data)
    user = client.create_user("newuser", "pass123", "OPERATOR")
    assert user.username == "newuser"
    assert user.role == "OPERATOR"


def test_update_user():
    data = {"id": 2, "username": "op1", "role": "SUPERVISOR", "active": True, "created_at": ""}
    client = _make_client(200, data)
    user = client.update_user(2, role="SUPERVISOR")
    assert user.role == "SUPERVISOR"


def test_deactivate_user():
    data = {"id": 2, "username": "op1", "role": "OPERATOR", "active": False, "created_at": ""}
    client = _make_client(200, data)
    user = client.deactivate_user(2)
    assert user.active is False
