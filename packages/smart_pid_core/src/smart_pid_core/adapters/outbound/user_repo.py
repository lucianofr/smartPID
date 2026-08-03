"""User repository backed by a standalone SQLite database."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    # Chosen HMI palette. Lives with the USER, not with the browser: the
    # theme used to be localStorage-only, so signing in anywhere else (or
    # after the profile was cleared) dropped the operator back to the
    # default. NULL means "never chosen", which is not the same as "chose
    # the default" and lets the client keep its local preference.
    theme: str | None = None


_USERS_DDL = """
CREATE TABLE IF NOT EXISTS Usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL UNIQUE,
    senha_hash  TEXT    NOT NULL,
    perfil      TEXT    NOT NULL DEFAULT 'user',
    ativo       INTEGER NOT NULL DEFAULT 1,
    criado_em   TEXT    NOT NULL DEFAULT (datetime('now')),
    tema        TEXT
);
"""

# Added after the table shipped, so an existing users.db needs it back-filled.
_USERS_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("tema", "TEXT"),
)


class UserRepository:
    """CRUD operations on the Usuarios table using its own SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    @property
    def db(self) -> aiosqlite.Connection:
        """Return the underlying connection (must call initialize first)."""
        if self._db is None:
            msg = "UserRepository not initialized — call initialize() first"
            raise RuntimeError(msg)
        return self._db

    async def initialize(self) -> None:
        """Open the database, enable WAL mode, create the Usuarios table."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript(_USERS_DDL)
        await self._apply_migrations()
        await self._db.commit()

    async def _apply_migrations(self) -> None:
        """Add columns introduced after the table first shipped."""
        async with self.db.execute("PRAGMA table_info(Usuarios)") as cur:
            existing = {row[1] for row in await cur.fetchall()}
        for column, ddl in _USERS_MIGRATIONS:
            if column not in existing:
                await self.db.execute(
                    f"ALTER TABLE Usuarios ADD COLUMN {column} {ddl}",
                )

    async def close(self) -> None:
        """Close the SQLite connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def create(self, username: str, password_hash: str, role: str) -> User:
        """Insert a new user. Raises on duplicate username."""
        async with self.db.execute(
            "INSERT INTO Usuarios (nome, senha_hash, perfil) VALUES (?, ?, ?)",
            (username, password_hash, role),
        ) as cur:
            new_id = cur.lastrowid
        await self.db.commit()
        return User(
            id=new_id or 0,
            username=username,
            password_hash=password_hash,
            role=role,
            created_at="",
        )

    async def get_by_username(self, username: str) -> User | None:
        """Return active user or None if not found."""
        async with self.db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em, ativo, tema"
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
            theme=row[6],
        )

    async def list_all(self) -> list[User]:
        """Return all users."""
        async with self.db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em, ativo, tema"
            " FROM Usuarios ORDER BY id"
        ) as cur:
            rows = await cur.fetchall()
        return [
            User(
                id=r[0], username=r[1], password_hash=r[2],
                role=r[3], created_at=r[4], active=bool(r[5]), theme=r[6],
            )
            for r in rows
        ]

    async def get_by_id(self, user_id: int) -> User | None:
        """Return user by id or None if not found."""
        async with self.db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em, ativo, tema"
            " FROM Usuarios WHERE id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return User(
            id=row[0], username=row[1], password_hash=row[2],
            role=row[3], created_at=row[4], active=bool(row[5]), theme=row[6],
        )

    async def set_theme(self, user_id: int, theme: str) -> User | None:
        """Persist the user's chosen HMI palette."""
        await self.db.execute(
            "UPDATE Usuarios SET tema = ? WHERE id = ?", (theme, user_id),
        )
        await self.db.commit()
        return await self.get_by_id(user_id)

    async def update(
        self,
        user_id: int,
        role: str | None = None,
        password_hash: str | None = None,
        active: bool | None = None,
    ) -> User | None:
        """Update user fields. Returns updated user or None if not found."""
        # Column names come from this literal tuple and nowhere else, so the
        # assembled SET clause cannot contain caller-derived text even if the
        # signature grows. Values stay parameterized.
        changes: tuple[tuple[str, str | int | None], ...] = (
            ("perfil", role),
            ("senha_hash", password_hash),
            ("ativo", None if active is None else int(active)),
        )
        set_clauses = [f"{column} = ?" for column, value in changes if value is not None]
        params: list[str | int] = [value for _, value in changes if value is not None]
        if not set_clauses:
            return await self.get_by_id(user_id)
        params.append(user_id)
        await self.db.execute(
            f"UPDATE Usuarios SET {', '.join(set_clauses)} WHERE id = ?",  # noqa: S608
            params,
        )
        await self.db.commit()
        return await self.get_by_id(user_id)

    async def deactivate(self, user_id: int) -> User | None:
        """Soft-delete a user by setting ativo=0."""
        await self.db.execute(
            "UPDATE Usuarios SET ativo = 0 WHERE id = ?", (user_id,),
        )
        await self.db.commit()
        return await self.get_by_id(user_id)
