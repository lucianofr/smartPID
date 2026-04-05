"""Tests for /auth endpoints."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/auth/login", json={"username": "admin", "password": "admin"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/auth/login", json={"username": "admin", "password": "wrong"}
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_unknown_user(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/auth/login", json={"username": "nobody", "password": "x"}
        )
        assert resp.status_code == 401


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/auth/register",
            json={"username": "newuser", "password": "pass123", "role": "OPERATOR"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["role"] == "OPERATOR"

    @pytest.mark.asyncio
    async def test_register_without_auth_fails(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/auth/register",
            json={"username": "hacker", "password": "x"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_register_non_admin_fails(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/auth/register",
            json={"username": "hacker", "password": "x"},
            headers=user_headers,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_register_duplicate_fails(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/auth/register",
            json={"username": "admin", "password": "x"},
            headers=admin_headers,
        )
        assert resp.status_code == 409


class TestJWTValidation:
    @pytest.mark.asyncio
    async def test_missing_auth_header(self, client: AsyncClient) -> None:
        resp = await client.get("/controllers")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token(self, client: AsyncClient) -> None:
        resp = await client.get(
            "/controllers", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401
