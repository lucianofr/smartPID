"""Tests for JWT and password utility functions."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.inbound.api.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordUtils:
    def test_hash_and_verify(self) -> None:
        pw_hash = hash_password("mysecret")
        assert pw_hash != "mysecret"
        assert verify_password("mysecret", pw_hash) is True

    def test_verify_wrong_password(self) -> None:
        pw_hash = hash_password("mysecret")
        assert verify_password("wrong", pw_hash) is False


class TestJWT:
    def test_create_and_decode_token(self) -> None:
        token = create_access_token(
            user_id=1, username="admin", role="admin",
            secret="testsecret", expiry_hours=1,
        )
        claims = decode_access_token(token, secret="testsecret")
        assert claims["sub"] == 1
        assert claims["username"] == "admin"
        assert claims["role"] == "admin"

    def test_decode_invalid_token(self) -> None:
        with pytest.raises(Exception):
            decode_access_token("not.a.token", secret="testsecret")

    def test_decode_wrong_secret(self) -> None:
        token = create_access_token(
            user_id=1, username="admin", role="admin",
            secret="correct", expiry_hours=1,
        )
        with pytest.raises(Exception):
            decode_access_token(token, secret="wrong")
