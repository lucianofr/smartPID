"""User repository backed by a standalone SQLite database (engine C)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from smart_pid_core.adapters.outbound.db_engine import create_sqlite_engine


@dataclass
class User:
    """Lightweight user record from DB."""

    id: int
    username: str
    password_hash: str
    role: str
    created_at: str
    active: bool = True


_USERS_DDL = """
CREATE TABLE IF NOT EXISTS Usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL UNIQUE,
    senha_hash  TEXT    NOT NULL,
    perfil      TEXT    NOT NULL DEFAULT 'user',
    ativo       INTEGER NOT NULL DEFAULT 1,
    criado_em   TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


class UserRepository:
    """CRUD operations on the Usuarios table using its own SQLite database.

    Owns engine C (users.db, main loop, single connection). Credentials
    never travel inside .spid; this engine is never touched by project
    switching.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            expire_on_commit=False,
        )

    async def initialize(self) -> None:
        """Open the database, apply PRAGMAs, create the Usuarios table."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_sqlite_engine(self._db_path)
        self.session_factory.configure(bind=self._engine)
        async with self._engine.connect() as conn:
            raw = await conn.get_raw_connection()
            await raw.driver_connection.executescript(_USERS_DDL)
            await raw.driver_connection.commit()

    async def close(self) -> None:
        """Dispose engine C."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    async def create(self, username: str, password_hash: str, role: str) -> User:
        """Insert a new user. Raises on duplicate username."""
        async with self.session_factory() as session:
            result = await session.execute(
                text("INSERT INTO Usuarios (nome, senha_hash, perfil) VALUES (:n, :h, :p)"),
                {"n": username, "h": password_hash, "p": role},
            )
            new_id = result.lastrowid
            await session.commit()
        return User(
            id=new_id or 0,
            username=username,
            password_hash=password_hash,
            role=role,
            created_at="",
        )

    async def get_by_username(self, username: str) -> User | None:
        """Return active user or None if not found."""
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id, nome, senha_hash, perfil, criado_em, ativo"
                    " FROM Usuarios WHERE nome = :n AND ativo = 1"
                ),
                {"n": username},
            )
            row = result.first()
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
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id, nome, senha_hash, perfil, criado_em, ativo"
                    " FROM Usuarios ORDER BY id"
                ),
            )
            rows = result.all()
        return [
            User(
                id=r[0], username=r[1], password_hash=r[2],
                role=r[3], created_at=r[4], active=bool(r[5]),
            )
            for r in rows
        ]

    async def get_by_id(self, user_id: int) -> User | None:
        """Return user by id or None if not found."""
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id, nome, senha_hash, perfil, criado_em, ativo"
                    " FROM Usuarios WHERE id = :uid"
                ),
                {"uid": user_id},
            )
            row = result.first()
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
        active: bool | None = None,
    ) -> User | None:
        """Update user fields. Returns updated user or None if not found."""
        updates: list[str] = []
        params: dict = {"uid": user_id}
        if role is not None:
            updates.append("perfil = :role")
            params["role"] = role
        if password_hash is not None:
            updates.append("senha_hash = :hash")
            params["hash"] = password_hash
        if active is not None:
            updates.append("ativo = :active")
            params["active"] = 1 if active else 0
        if not updates:
            return await self.get_by_id(user_id)
        async with self.session_factory() as session:
            await session.execute(
                text(f"UPDATE Usuarios SET {', '.join(updates)} WHERE id = :uid"),  # noqa: S608
                params,
            )
            await session.commit()
        return await self.get_by_id(user_id)

    async def deactivate(self, user_id: int) -> User | None:
        """Soft-delete a user by setting ativo=0."""
        async with self.session_factory() as session:
            await session.execute(
                text("UPDATE Usuarios SET ativo = 0 WHERE id = :uid"),
                {"uid": user_id},
            )
            await session.commit()
        return await self.get_by_id(user_id)
