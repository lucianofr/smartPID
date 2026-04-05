"""Tests for UserRepository (Usuarios table)."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository


@pytest.fixture
async def user_repo(tmp_path) -> UserRepository:
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    return UserRepository(repo.db)


class TestUserRepository:
    @pytest.mark.asyncio
    async def test_create_and_get_by_username(self, user_repo: UserRepository) -> None:
        user = await user_repo.create("alice", "hashed_pw", "admin")
        assert user.id > 0
        assert user.username == "alice"
        assert user.role == "admin"

        loaded = await user_repo.get_by_username("alice")
        assert loaded is not None
        assert loaded.id == user.id
        assert loaded.password_hash == "hashed_pw"

    @pytest.mark.asyncio
    async def test_get_by_username_not_found(self, user_repo: UserRepository) -> None:
        result = await user_repo.get_by_username("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all(self, user_repo: UserRepository) -> None:
        await user_repo.create("alice", "h1", "admin")
        await user_repo.create("bob", "h2", "user")
        users = await user_repo.list_all()
        assert len(users) == 2
        names = {u.username for u in users}
        assert names == {"alice", "bob"}

    @pytest.mark.asyncio
    async def test_create_duplicate_username_raises(self, user_repo: UserRepository) -> None:
        from sqlite3 import IntegrityError

        await user_repo.create("alice", "h1", "admin")
        with pytest.raises(IntegrityError):
            await user_repo.create("alice", "h2", "user")
