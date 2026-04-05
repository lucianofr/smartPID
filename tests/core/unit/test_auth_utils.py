"""Tests for JWT and password utility functions."""
from __future__ import annotations

import jwt
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
        secret = "test-secret-key-minimum-32-bytes!"
        token = create_access_token(
            user_id=1, username="admin", role="admin",
            secret=secret, expiry_hours=1,
        )
        claims = decode_access_token(token, secret=secret)
        assert claims["sub"] == 1
        assert claims["username"] == "admin"
        assert claims["role"] == "admin"

    def test_decode_invalid_token(self) -> None:
        with pytest.raises(jwt.PyJWTError):
            decode_access_token(
                "not.a.token",
                secret="test-secret-key-minimum-32-bytes!",
            )

    def test_decode_wrong_secret(self) -> None:
        token = create_access_token(
            user_id=1, username="admin", role="admin",
            secret="correct-secret-key-min-32-bytes!", expiry_hours=1,
        )
        with pytest.raises(jwt.PyJWTError):
            decode_access_token(
                token, secret="wrong-secret-key-minimum-32-bytes!",
            )
