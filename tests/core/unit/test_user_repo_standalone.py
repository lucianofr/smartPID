"""Tests for standalone UserRepository with its own DB file."""
from __future__ import annotations

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
        user = await repo.create("admin", "hash123", "ADMIN")
        assert user.username == "admin"
        assert user.role == "ADMIN"
        fetched = await repo.get_by_username("admin")
        assert fetched is not None
        assert fetched.id == user.id
        await repo.close()

    @pytest.mark.asyncio
    async def test_close_and_reopen(self, tmp_path) -> None:
        db_path = tmp_path / "users.db"
        repo = UserRepository(db_path)
        await repo.initialize()
        await repo.create("admin", "hash123", "ADMIN")
        await repo.close()
        repo2 = UserRepository(db_path)
        await repo2.initialize()
        users = await repo2.list_all()
        assert len(users) == 1
        assert users[0].username == "admin"
        await repo2.close()
