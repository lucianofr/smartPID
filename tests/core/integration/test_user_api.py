"""Integration tests for user management REST endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient  # noqa: TC002

from smart_pid_core.adapters.inbound.api.auth import hash_password
from smart_pid_core.adapters.outbound.user_repo import UserRepository  # noqa: TC001


@pytest.fixture
def user_repo(api_deps) -> UserRepository:
    return api_deps["user_repo"]


class TestListUsers:
    @pytest.mark.asyncio
    async def test_list_users_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["username"] == "admin"

    @pytest.mark.asyncio
    async def test_list_users_operator_forbidden(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/users", headers=user_headers)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_users_no_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/users")
        assert resp.status_code == 401


class TestGetUser:
    @pytest.mark.asyncio
    async def test_get_user_by_id(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/users/1", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 1
        assert data["username"] == "admin"

    @pytest.mark.asyncio
    async def test_get_user_not_found(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/users/999", headers=admin_headers)
        assert resp.status_code == 404


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_update_user_role(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        user_repo: UserRepository,
    ) -> None:
        await user_repo.create("op1", hash_password("pass"), "OPERATOR")
        resp = await client.put(
            "/users/2", json={"role": "SUPERVISOR"}, headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "SUPERVISOR"

    @pytest.mark.asyncio
    async def test_update_user_password(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        user_repo: UserRepository,
    ) -> None:
        await user_repo.create("op2", hash_password("old"), "OPERATOR")
        resp = await client.put(
            "/users/2", json={"password": "newpass"}, headers=admin_headers
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_update_user_not_found(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.put(
            "/users/999", json={"role": "ADMIN"}, headers=admin_headers
        )
        assert resp.status_code == 404


class TestDeactivateUser:
    @pytest.mark.asyncio
    async def test_deactivate_user(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        user_repo: UserRepository,
    ) -> None:
        await user_repo.create("op1", hash_password("pass"), "OPERATOR")
        resp = await client.delete("/users/2", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    @pytest.mark.asyncio
    async def test_deactivate_user_not_found(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.delete("/users/999", headers=admin_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_deactivated_user_not_found_by_username(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        user_repo: UserRepository,
    ) -> None:
        await user_repo.create("op1", hash_password("pass"), "OPERATOR")
        await user_repo.deactivate(2)
        user = await user_repo.get_by_username("op1")
        assert user is None


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_create_user_as_admin(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/users",
            json={"username": "newuser", "password": "secret123", "role": "OPERATOR"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["role"] == "OPERATOR"
        assert data["active"] is True

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        await client.post(
            "/users",
            json={"username": "dupuser", "password": "pass1"},
            headers=admin_headers,
        )
        resp = await client.post(
            "/users",
            json={"username": "dupuser", "password": "pass2"},
            headers=admin_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_create_user_as_operator_forbidden(
        self,
        client: AsyncClient,
        user_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/users",
            json={"username": "blocked", "password": "pass"},
            headers=user_headers,
        )
        assert resp.status_code == 403


class TestReactivateUser:
    @pytest.mark.asyncio
    async def test_reactivate_user(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        user_repo: UserRepository,
    ) -> None:
        await user_repo.create("deact1", hash_password("pass"), "OPERATOR")
        await user_repo.deactivate(2)
        resp = await client.put(
            "/users/2", json={"active": True}, headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is True

    @pytest.mark.asyncio
    async def test_deactivate_via_put(
        self,
        client: AsyncClient,
        admin_headers: dict[str, str],
        user_repo: UserRepository,
    ) -> None:
        await user_repo.create("act1", hash_password("pass"), "OPERATOR")
        resp = await client.put(
            "/users/2", json={"active": False}, headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["active"] is False
