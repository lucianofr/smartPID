"""UserRepository.update — partial updates and SET-clause construction.

``update`` assembles its SET clause dynamically, so these pin the behaviour of
every field combination and assert that only whitelisted column names can ever
reach the statement.
"""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.user_repo import UserRepository


@pytest.fixture
async def user_repo(tmp_path) -> UserRepository:
    repo = UserRepository(tmp_path / "users.db")
    await repo.initialize()
    yield repo
    await repo.close()


class TestUpdateFieldCombinations:
    @pytest.mark.asyncio
    async def test_update_role_only(self, user_repo: UserRepository) -> None:
        user = await user_repo.create("alice", "h1", "user")
        updated = await user_repo.update(user.id, role="admin")
        assert updated is not None
        assert updated.role == "admin"
        assert updated.password_hash == "h1"
        assert updated.active is True

    @pytest.mark.asyncio
    async def test_update_password_only(self, user_repo: UserRepository) -> None:
        user = await user_repo.create("alice", "h1", "user")
        updated = await user_repo.update(user.id, password_hash="h2")
        assert updated is not None
        assert updated.password_hash == "h2"
        assert updated.role == "user"

    @pytest.mark.asyncio
    async def test_deactivate_via_update(self, user_repo: UserRepository) -> None:
        user = await user_repo.create("alice", "h1", "user")
        updated = await user_repo.update(user.id, active=False)
        assert updated is not None
        assert updated.active is False

    @pytest.mark.asyncio
    async def test_reactivate_via_update(self, user_repo: UserRepository) -> None:
        """``active=False`` must not be mistaken for "field omitted"."""
        user = await user_repo.create("alice", "h1", "user")
        await user_repo.update(user.id, active=False)
        updated = await user_repo.update(user.id, active=True)
        assert updated is not None
        assert updated.active is True

    @pytest.mark.asyncio
    async def test_update_all_fields_at_once(self, user_repo: UserRepository) -> None:
        user = await user_repo.create("alice", "h1", "user")
        updated = await user_repo.update(
            user.id, role="admin", password_hash="h2", active=False,
        )
        assert updated is not None
        assert (updated.role, updated.password_hash, updated.active) == (
            "admin", "h2", False,
        )

    @pytest.mark.asyncio
    async def test_no_fields_is_a_read(self, user_repo: UserRepository) -> None:
        user = await user_repo.create("alice", "h1", "user")
        updated = await user_repo.update(user.id)
        assert updated is not None
        assert (updated.role, updated.password_hash, updated.active) == (
            "user", "h1", True,
        )

    @pytest.mark.asyncio
    async def test_unknown_user_returns_none(self, user_repo: UserRepository) -> None:
        assert await user_repo.update(9999, role="admin") is None

    @pytest.mark.asyncio
    async def test_update_does_not_touch_other_rows(
        self, user_repo: UserRepository,
    ) -> None:
        alice = await user_repo.create("alice", "h1", "user")
        bob = await user_repo.create("bob", "h2", "user")
        await user_repo.update(alice.id, role="admin", active=False)
        untouched = await user_repo.get_by_id(bob.id)
        assert untouched is not None
        assert (untouched.role, untouched.password_hash, untouched.active) == (
            "user", "h2", True,
        )


class TestUpdateIsInjectionSafe:
    @pytest.mark.asyncio
    async def test_sql_metacharacters_in_values_are_stored_literally(
        self, user_repo: UserRepository,
    ) -> None:
        """Values are bound, never interpolated: a payload that would drop the
        table if concatenated must round-trip as an ordinary string."""
        payload = "'; DROP TABLE Usuarios; --"
        user = await user_repo.create("alice", "h1", "user")
        updated = await user_repo.update(user.id, password_hash=payload)
        assert updated is not None
        assert updated.password_hash == payload
        # The table survived and still holds the row.
        assert len(await user_repo.list_all()) == 1

    @pytest.mark.asyncio
    async def test_set_clause_only_ever_names_whitelisted_columns(
        self, user_repo: UserRepository,
    ) -> None:
        """Capture the statement actually issued and assert its SET clause is
        built from the three known columns and bound parameters only."""
        user = await user_repo.create("alice", "h1", "user")
        statements: list[str] = []
        original = user_repo.db.execute

        # aiosqlite's execute() returns an object that is both awaitable and an
        # async context manager, so the spy must hand it back untouched rather
        # than wrap it in a coroutine of its own.
        def spy(sql, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
            statements.append(sql)
            return original(sql, *args, **kwargs)

        user_repo.db.execute = spy  # type: ignore[method-assign]
        try:
            await user_repo.update(
                user.id, role="admin", password_hash="h2", active=False,
            )
        finally:
            user_repo.db.execute = original  # type: ignore[method-assign]

        update_sql = next(s for s in statements if s.startswith("UPDATE Usuarios"))
        assert update_sql == (
            "UPDATE Usuarios SET perfil = ?, senha_hash = ?, ativo = ? WHERE id = ?"
        )
