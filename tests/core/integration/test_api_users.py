"""Tests for the admin-gated /users management router (spec §9.3)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create(
    client: AsyncClient,
    headers: dict[str, str],
    username: str,
    password: str = "pw123",
    role: str = "user",
) -> dict:
    resp = await client.post(
        "/users",
        json={"username": username, "password": password, "role": role},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestListUsers:
    @pytest.mark.asyncio
    async def test_admin_lists_seeded_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/users", headers=admin_headers)
        assert resp.status_code == 200
        users = resp.json()
        assert len(users) == 1
        assert users[0]["username"] == "admin"
        assert users[0]["role"] == "admin"
        assert users[0]["active"] is True
        assert set(users[0]) == {"id", "username", "role", "active", "created_at"}

    @pytest.mark.asyncio
    async def test_user_role_forbidden(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/users", headers=user_headers)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_401(self, client: AsyncClient) -> None:
        resp = await client.get("/users")
        assert resp.status_code == 401


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_create_then_login_round_trip(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        created = await _create(client, admin_headers, "op1", password="secret1")
        assert created["role"] == "user"
        assert created["active"] is True
        login = await client.post(
            "/auth/login", json={"username": "op1", "password": "secret1"}
        )
        assert login.status_code == 200

    @pytest.mark.asyncio
    async def test_duplicate_username_409(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        await _create(client, admin_headers, "dup")
        resp = await client.post(
            "/users",
            json={"username": "dup", "password": "x", "role": "user"},
            headers=admin_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_legacy_role_body_422(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/users",
            json={"username": "x", "password": "x", "role": "SUPERVISOR"},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_user_role_forbidden(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/users",
            json={"username": "nope", "password": "x", "role": "user"},
            headers=user_headers,
        )
        assert resp.status_code == 403


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_promote_to_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        created = await _create(client, admin_headers, "promoted")
        resp = await client.patch(
            f"/users/{created['id']}", json={"role": "admin"}, headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    @pytest.mark.asyncio
    async def test_change_password_round_trip(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        created = await _create(client, admin_headers, "pwuser", password="old-pw")
        resp = await client.patch(
            f"/users/{created['id']}",
            json={"password": "new-pw"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert (
            await client.post(
                "/auth/login", json={"username": "pwuser", "password": "new-pw"}
            )
        ).status_code == 200
        assert (
            await client.post(
                "/auth/login", json={"username": "pwuser", "password": "old-pw"}
            )
        ).status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_id_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.patch(
            "/users/9999", json={"role": "user"}, headers=admin_headers
        )
        assert resp.status_code == 404


class TestDeactivateUser:
    @pytest.mark.asyncio
    async def test_deactivated_user_cannot_login(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        created = await _create(client, admin_headers, "leaver", password="bye")
        resp = await client.delete(f"/users/{created['id']}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["active"] is False
        login = await client.post(
            "/auth/login", json={"username": "leaver", "password": "bye"}
        )
        assert login.status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_id_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.delete("/users/9999", headers=admin_headers)
        assert resp.status_code == 404


class TestLastAdminGuard:
    """users.db is standalone: zero active admins == permanent lockout."""

    @pytest.mark.asyncio
    async def test_demoting_sole_admin_409(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.patch(
            "/users/1", json={"role": "user"}, headers=admin_headers
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_deactivating_sole_admin_409(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.delete("/users/1", headers=admin_headers)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_demotion_allowed_once_second_admin_exists(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        await _create(client, admin_headers, "admin2", role="admin")
        resp = await client.patch(
            "/users/1", json={"role": "user"}, headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "user"
