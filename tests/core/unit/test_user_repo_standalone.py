"""Tests for standalone UserRepository with its own DB file."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from smart_pid_core.adapters.outbound.user_repo import UserRepository


class TestUserRepoStandalone:
    @pytest.mark.asyncio
    async def test_initialize_creates_usuarios_table(self, tmp_path) -> None:
        db_path = tmp_path / "users.db"
        repo = UserRepository(db_path)
        await repo.initialize()
        users = await repo.list_all()
        assert users == []
        await repo.close()

    @pytest.mark.asyncio
    async def test_create_and_retrieve_user(self, tmp_path) -> None:
        db_path = tmp_path / "users.db"
        repo = UserRepository(db_path)
        await repo.initialize()
        user = await repo.create("admin", "hash123", "admin")
        assert user.username == "admin"
        assert user.role == "admin"
        fetched = await repo.get_by_username("admin")
        assert fetched is not None
        assert fetched.id == user.id
        await repo.close()

    @pytest.mark.asyncio
    async def test_close_and_reopen(self, tmp_path) -> None:
        db_path = tmp_path / "users.db"
        repo = UserRepository(db_path)
        await repo.initialize()
        await repo.create("admin", "hash123", "admin")
        await repo.close()
        repo2 = UserRepository(db_path)
        await repo2.initialize()
        users = await repo2.list_all()
        assert len(users) == 1
        assert users[0].username == "admin"
        await repo2.close()


class TestAccessLog:
    """Sign-in history lives in users.db so it survives a project switch."""

    @pytest.mark.asyncio
    async def test_records_events_newest_first(self, tmp_path) -> None:
        repo = UserRepository(tmp_path / "users.db")
        await repo.initialize()
        await repo.record_access(user_id=1, username="admin", event="LOGIN", ip="10.0.0.1")
        await repo.record_access(user_id=1, username="admin", event="LOGOUT", ip="10.0.0.1")

        rows = await repo.list_access()
        assert [r["event"] for r in rows] == ["LOGOUT", "LOGIN"]
        assert rows[0]["username"] == "admin"
        assert rows[0]["ip"] == "10.0.0.1"
        await repo.close()

    @pytest.mark.asyncio
    async def test_survives_deleting_the_account(self, tmp_path) -> None:
        # The username is stored on the row, not joined from Usuarios, so the
        # history stays readable after the account is gone.
        repo = UserRepository(tmp_path / "users.db")
        await repo.initialize()
        user = await repo.create("gone", "hash", "user")
        await repo.record_access(
            user_id=user.id, username=user.username, event="LOGIN", ip="10.0.0.2"
        )
        await repo.db.execute("DELETE FROM Usuarios WHERE id = ?", (user.id,))
        await repo.db.commit()

        assert (await repo.list_access())[0]["username"] == "gone"
        await repo.close()

    @pytest.mark.asyncio
    async def test_expired_rows_are_dropped_on_write(self, tmp_path) -> None:
        # main._retention_cleanup sweeps the .spid tables and cannot reach this
        # database, so an unpruned Log_Acessos would be the one Log_* table that
        # grows forever.
        repo = UserRepository(tmp_path / "users.db")
        await repo.initialize()
        stale = (datetime.now(tz=UTC) - timedelta(days=400)).isoformat()
        await repo.db.execute(
            "INSERT INTO Log_Acessos (usuario_id, nome, evento, ip, timestamp)"
            " VALUES (?, ?, ?, ?, ?)",
            (1, "ancient", "LOGIN", "10.0.0.9", stale),
        )
        await repo.db.commit()

        await repo.record_access(user_id=1, username="admin", event="LOGIN", ip="10.0.0.1")

        assert [r["username"] for r in await repo.list_access()] == ["admin"]
        await repo.close()
