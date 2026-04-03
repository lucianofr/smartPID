"""JWT token and password hashing utilities."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(
    *,
    user_id: int,
    username: str,
    role: str,
    secret: str,
    expiry_hours: int = 8,
) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.now(tz=UTC) + timedelta(hours=expiry_hours),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str, *, secret: str) -> dict:
    """Decode and validate a JWT access token. Raises jwt.PyJWTError on failure."""
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    payload["sub"] = int(payload["sub"])
    return payload
