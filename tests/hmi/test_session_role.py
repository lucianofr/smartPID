"""Tests for Session role extraction from JWT."""
from __future__ import annotations

import base64
import json
import time

from smart_pid_hmi.services.session import Session


def _make_token(role: str = "OPERATOR") -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload_data = {"sub": 1, "username": "testuser", "role": role, "exp": time.time() + 3600}
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"fake-sig").rstrip(b"=").decode()
    return f"{header}.{payload}.{sig}"


def test_role_extracted():
    session = Session()
    session.store_token(_make_token("SUPERVISOR"))
    assert session.role == "SUPERVISOR"


def test_role_none_when_not_authenticated():
    session = Session()
    assert session.role is None


def test_role_cleared():
    session = Session()
    session.store_token(_make_token("ADMIN"))
    assert session.role == "ADMIN"
    session.clear()
    assert session.role is None
