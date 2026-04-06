"""Tests for CoreSettings.users_db_path."""
from __future__ import annotations

from pathlib import Path

import pytest

from smart_pid_core.config import CoreSettings


class TestUsersDbPath:
    def test_default_users_db_path(self) -> None:
        settings = CoreSettings(jwt_secret="test-secret-key-minimum-32-bytes!")
        expected = Path.home() / ".config" / "smart-pid" / "users.db"
        assert settings.users_db_path == expected

    def test_custom_users_db_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPID_USERS_DB_PATH", "/tmp/custom_users.db")
        settings = CoreSettings(jwt_secret="test-secret-key-minimum-32-bytes!")
        assert settings.users_db_path == Path("/tmp/custom_users.db")
