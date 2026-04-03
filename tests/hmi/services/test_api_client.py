"""Tests for REST API client using httpx mock transport."""
from unittest.mock import MagicMock

import httpx

from smart_pid_hmi.services.api_client import APIClient
from smart_pid_hmi.services.session import Session


def _mock_transport(status: int, json_body: dict | list) -> httpx.MockTransport:
    """Create a mock transport that always returns the given response."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body)
    return httpx.MockTransport(handler)


def test_login_success():
    transport = _mock_transport(200, {"access_token": "tok123", "token_type": "bearer"})
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    resp = client.login("admin", "pass")
    assert resp.access_token == "tok123"


def test_list_controllers():
    data = [
        {
            "id": 1, "name": "FIC-101", "description": "Flow",
            "mode": "AUTO", "pv": 45.0, "sp": 50.0, "co": 62.0,
        },
    ]
    transport = _mock_transport(200, data)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    controllers = client.list_controllers()
    assert len(controllers) == 1
    assert controllers[0].name == "FIC-101"


def test_set_setpoint():
    transport = _mock_transport(200, {"ok": True, "controller_id": 1, "detail": "SP set to 55.0"})
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    resp = client.set_setpoint(1, 55.0)
    assert resp.ok is True


def test_set_mode():
    transport = _mock_transport(
        200, {"ok": True, "controller_id": 1, "detail": "Mode set to MAN"},
    )
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    resp = client.set_mode(1, "MAN")
    assert resp.ok is True


def test_set_output():
    transport = _mock_transport(
        200, {"ok": True, "controller_id": 1, "detail": "Output set to 30.0"},
    )
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    resp = client.set_output(1, 30.0)
    assert resp.ok is True


def test_get_history():
    from datetime import datetime, timezone

    data = {
        "controller_id": 1,
        "frames": [
            {"timestamp": "2026-04-03T10:00:00Z", "pv": 45.0, "sp": 50.0,
             "co": 62.0, "mode": "AUTO", "status": "GOOD"},
        ],
        "count": 1,
    }
    transport = _mock_transport(200, data)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    resp = client.get_history(
        1, datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 3, 11, 0, tzinfo=timezone.utc),
    )
    assert resp.count == 1
    assert resp.frames[0].pv == 45.0


def test_auth_header_injected():
    """Verify that session auth header is sent with requests."""
    received_headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received_headers.update(dict(request.headers))
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    session = MagicMock()
    session.auth_header = {"Authorization": "Bearer mytoken"}
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    client.list_controllers()
    assert "authorization" in received_headers
    assert received_headers["authorization"] == "Bearer mytoken"
