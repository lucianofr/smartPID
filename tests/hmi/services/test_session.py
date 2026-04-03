"""Tests for JWT session management."""
import base64
import json
import time

from smart_pid_hmi.services.session import Session


def _make_fake_token(username: str = "operator", exp_offset: int = 3600) -> str:
    """Create a fake JWT token (header.payload.signature) for testing."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    payload_data = {
        "sub": "1",
        "username": username,
        "role": "operator",
        "exp": int(time.time()) + exp_offset,
    }
    payload = base64.urlsafe_b64encode(
        json.dumps(payload_data).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


def test_initial_state():
    session = Session()
    assert session.is_authenticated is False
    assert session.token is None
    assert session.username is None


def test_store_token():
    session = Session()
    token = _make_fake_token("admin_user")
    session.store_token(token)
    assert session.is_authenticated is True
    assert session.token == token
    assert session.username == "admin_user"


def test_clear():
    session = Session()
    session.store_token(_make_fake_token())
    session.clear()
    assert session.is_authenticated is False
    assert session.token is None


def test_expired_token():
    session = Session()
    token = _make_fake_token(exp_offset=-10)  # already expired
    session.store_token(token)
    assert session.is_authenticated is False


def test_auth_header():
    session = Session()
    token = _make_fake_token()
    session.store_token(token)
    assert session.auth_header == {"Authorization": f"Bearer {token}"}


def test_auth_header_none_when_unauthenticated():
    session = Session()
    assert session.auth_header == {}
