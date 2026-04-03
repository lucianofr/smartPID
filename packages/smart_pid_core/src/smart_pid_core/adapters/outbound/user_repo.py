"""User repository backed by the Usuarios SQLite table."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite


@dataclass
class User:
    """Lightweight user record from DB."""

    id: int
    username: str
    password_hash: str
    role: str
    created_at: str


class UserRepository:
    """CRUD operations on the Usuarios table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def create(self, username: str, password_hash: str, role: str) -> User:
        """Insert a new user. Raises on duplicate username."""
        async with self._db.execute(
            "INSERT INTO Usuarios (nome, senha_hash, perfil) VALUES (?, ?, ?)",
            (username, password_hash, role),
        ) as cur:
            new_id = cur.lastrowid
        await self._db.commit()
        return User(
            id=new_id or 0,
            username=username,
            password_hash=password_hash,
            role=role,
            created_at="",
        )

    async def get_by_username(self, username: str) -> User | None:
        """Return user or None if not found."""
        async with self._db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em FROM Usuarios WHERE nome = ?",
            (username,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return User(
            id=row[0],
            username=row[1],
            password_hash=row[2],
            role=row[3],
            created_at=row[4],
        )

    async def list_all(self) -> list[User]:
        """Return all users."""
        async with self._db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em FROM Usuarios ORDER BY id"
        ) as cur:
            rows = await cur.fetchall()
        return [
            User(id=r[0], username=r[1], password_hash=r[2], role=r[3], created_at=r[4])
            for r in rows
        ]
