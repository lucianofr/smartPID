"""JWT session management — stores token in memory, parses claims."""
from __future__ import annotations

import base64
import json
import time


class Session:
    """In-memory JWT session for the HMI client."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._username: str | None = None
        self._exp: float = 0.0

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None and time.time() < self._exp

    @property
    def token(self) -> str | None:
        if self.is_authenticated:
            return self._token
        return None

    @property
    def username(self) -> str | None:
        if self.is_authenticated:
            return self._username
        return None

    @property
    def auth_header(self) -> dict[str, str]:
        t = self.token
        if t is not None:
            return {"Authorization": f"Bearer {t}"}
        return {}

    def store_token(self, token: str) -> None:
        """Parse JWT payload (no verification — backend is trusted) and store."""
        try:
            payload_b64 = token.split(".")[1]
            # Add padding
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            self._token = token
            self._username = payload.get("username")
            self._exp = float(payload.get("exp", 0))
        except (IndexError, json.JSONDecodeError, ValueError):
            self._token = None
            self._username = None
            self._exp = 0.0

    def clear(self) -> None:
        self._token = None
        self._username = None
        self._exp = 0.0
