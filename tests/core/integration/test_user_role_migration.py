"""Role-value migration tests (spec §9.4, §14 "3-role fixture users.db").

Legacy databases hold uppercase roles: ADMIN → admin, SUPERVISOR → admin
(they held tuning/config powers), OPERATOR → user. The fixture builds the
users.db with the PRE-cutover DDL (DEFAULT 'OPERATOR') exactly as a field
deployment would have it.
"""
from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from smart_pid_core.adapters.inbound.api.auth import hash_password, verify_password
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.main import _migrate_user_roles, _seed_default_admin

_LEGACY_DDL = """
CREATE TABLE Usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL UNIQUE,
    senha_hash  TEXT    NOT NULL,
    perfil      TEXT    NOT NULL DEFAULT 'OPERATOR',
    ativo       INTEGER NOT NULL DEFAULT 1,
    criado_em   TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


async def _make_legacy_users_db(path: Path) -> None:
    async with aiosqlite.connect(path) as db:
        await db.executescript(_LEGACY_DDL)
        await db.executemany(
            "INSERT INTO Usuarios (nome, senha_hash, perfil, ativo) VALUES (?, ?, ?, ?)",
            [
                ("root", "hash-a", "ADMIN", 1),
                ("chief", "hash-s", "SUPERVISOR", 1),
                ("op1", "hash-o", "OPERATOR", 0),
            ],
        )
        await db.commit()


async def _roles_by_name(repo: UserRepository) -> dict[str, str]:
    return {user.username: user.role for user in await repo.list_all()}


class TestRoleValueMigration:
    @pytest.mark.asyncio
    async def test_three_legacy_roles_are_mapped(self, tmp_path: Path) -> None:
        db_path = tmp_path / "users.db"
        await _make_legacy_users_db(db_path)
        repo = UserRepository(db_path)
        await repo.initialize()
        await _migrate_user_roles(repo)
        assert await _roles_by_name(repo) == {
            "root": "admin",
            "chief": "admin",
            "op1": "user",
        }
        await repo.close()

    @pytest.mark.asyncio
    async def test_migration_is_idempotent_and_preserves_other_columns(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "users.db"
        await _make_legacy_users_db(db_path)
        repo = UserRepository(db_path)
        await repo.initialize()
        await _migrate_user_roles(repo)
        await _migrate_user_roles(repo)
        users = {user.username: user for user in await repo.list_all()}
        assert users["root"].password_hash == "hash-a"
        assert users["op1"].active is False
        assert users["op1"].role == "user"
        assert len(users) == 3
        await repo.close()

    @pytest.mark.asyncio
    async def test_new_vocabulary_rows_untouched(self, tmp_path: Path) -> None:
        db_path = tmp_path / "users.db"
        repo = UserRepository(db_path)
        await repo.initialize()
        await repo.create("fresh", "h", "user")
        await _migrate_user_roles(repo)
        assert (await _roles_by_name(repo))["fresh"] == "user"
        await repo.close()


class TestDDLDefault:
    @pytest.mark.asyncio
    async def test_fresh_db_defaults_perfil_to_user(self, tmp_path: Path) -> None:
        repo = UserRepository(tmp_path / "users.db")
        await repo.initialize()
        await repo.db.execute(
            "INSERT INTO Usuarios (nome, senha_hash) VALUES ('nodefault', 'h')"
        )
        await repo.db.commit()
        assert (await _roles_by_name(repo))["nodefault"] == "user"
        await repo.close()


class TestSeedDefaultAdmin:
    @pytest.mark.asyncio
    async def test_seeds_admin_role_admin_on_empty_db(self, tmp_path: Path) -> None:
        repo = UserRepository(tmp_path / "users.db")
        await repo.initialize()
        await _seed_default_admin(repo)
        users = await repo.list_all()
        assert len(users) == 1
        assert users[0].username == "admin"
        assert users[0].role == "admin"
        assert users[0].active is True
        assert verify_password("admin", users[0].password_hash)
        await repo.close()

    @pytest.mark.asyncio
    async def test_noop_when_users_exist(self, tmp_path: Path) -> None:
        repo = UserRepository(tmp_path / "users.db")
        await repo.initialize()
        await repo.create("existing", hash_password("x"), "user")
        await _seed_default_admin(repo)
        users = await repo.list_all()
        assert [user.username for user in users] == ["existing"]
        await repo.close()
