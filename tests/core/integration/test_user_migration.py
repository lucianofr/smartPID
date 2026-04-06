"""Tests for automatic user migration from .spid to users.db."""
from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from smart_pid_core.main import _migrate_users_if_needed


class TestUserMigration:
    @pytest.mark.asyncio
    async def test_migrates_users_from_spid(self, tmp_path: Path) -> None:
        spid_path = tmp_path / "project.spid"
        async with aiosqlite.connect(spid_path) as db:
            await db.executescript("""
                CREATE TABLE Usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL UNIQUE,
                    senha_hash TEXT NOT NULL,
                    perfil TEXT NOT NULL DEFAULT 'OPERATOR',
                    ativo INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
                );
            """)
            await db.execute(
                "INSERT INTO Usuarios (nome, senha_hash, perfil) VALUES (?, ?, ?)",
                ("admin", "hash123", "ADMIN"),
            )
            await db.commit()

        users_db_path = tmp_path / "users.db"
        await _migrate_users_if_needed(spid_path, users_db_path)

        from smart_pid_core.adapters.outbound.user_repo import UserRepository

        repo = UserRepository(users_db_path)
        await repo.initialize()
        users = await repo.list_all()
        assert len(users) == 1
        assert users[0].username == "admin"
        await repo.close()

    @pytest.mark.asyncio
    async def test_skips_if_users_db_exists(self, tmp_path: Path) -> None:
        spid_path = tmp_path / "project.spid"
        spid_path.touch()
        users_db_path = tmp_path / "users.db"
        users_db_path.touch()
        await _migrate_users_if_needed(spid_path, users_db_path)

    @pytest.mark.asyncio
    async def test_skips_if_no_usuarios_table(self, tmp_path: Path) -> None:
        spid_path = tmp_path / "project.spid"
        async with aiosqlite.connect(spid_path) as db:
            await db.execute("CREATE TABLE dummy (id INTEGER)")
            await db.commit()

        users_db_path = tmp_path / "users.db"
        await _migrate_users_if_needed(spid_path, users_db_path)
        assert not users_db_path.exists()

    @pytest.mark.asyncio
    async def test_skips_if_spid_missing(self, tmp_path: Path) -> None:
        spid_path = tmp_path / "nope.spid"
        users_db_path = tmp_path / "users.db"
        await _migrate_users_if_needed(spid_path, users_db_path)
        assert not users_db_path.exists()
