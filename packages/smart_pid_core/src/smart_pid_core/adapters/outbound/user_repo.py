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
    active: bool = True


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
        """Return active user or None if not found."""
        async with self._db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em, ativo"
            " FROM Usuarios WHERE nome = ? AND ativo = 1",
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
            active=bool(row[5]),
        )

    async def list_all(self) -> list[User]:
        """Return all users."""
        async with self._db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em, ativo FROM Usuarios ORDER BY id"
        ) as cur:
            rows = await cur.fetchall()
        return [
            User(
                id=r[0], username=r[1], password_hash=r[2],
                role=r[3], created_at=r[4], active=bool(r[5]),
            )
            for r in rows
        ]

    async def get_by_id(self, user_id: int) -> User | None:
        """Return user by id or None if not found."""
        async with self._db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em, ativo FROM Usuarios WHERE id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return User(
            id=row[0], username=row[1], password_hash=row[2],
            role=row[3], created_at=row[4], active=bool(row[5]),
        )

    async def update(
        self,
        user_id: int,
        role: str | None = None,
        password_hash: str | None = None,
    ) -> User | None:
        """Update user fields. Returns updated user or None if not found."""
        updates: list[str] = []
        params: list[str | int] = []
        if role is not None:
            updates.append("perfil = ?")
            params.append(role)
        if password_hash is not None:
            updates.append("senha_hash = ?")
            params.append(password_hash)
        if not updates:
            return await self.get_by_id(user_id)
        params.append(user_id)
        await self._db.execute(
            f"UPDATE Usuarios SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self._db.commit()
        return await self.get_by_id(user_id)

    async def deactivate(self, user_id: int) -> User | None:
        """Soft-delete a user by setting ativo=0."""
        await self._db.execute(
            "UPDATE Usuarios SET ativo = 0 WHERE id = ?", (user_id,),
        )
        await self._db.commit()
        return await self.get_by_id(user_id)
