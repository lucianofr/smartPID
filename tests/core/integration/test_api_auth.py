"""Tests for /auth endpoints."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from smart_pid_core.adapters.inbound.api.auth import create_access_token

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


class TestLegacyRoleClaims:
    """Spec §9.5: tokens minted before the cutover carry uppercase roles for
    up to 8h. They are rejected with 401 — one forced re-login, no mapping."""

    @pytest.mark.asyncio
    async def test_legacy_role_claims_rejected_with_401(
        self, client: AsyncClient, api_deps: dict
    ) -> None:
        for legacy_role in ("ADMIN", "SUPERVISOR", "OPERATOR"):
            token = create_access_token(
                user_id=1,
                username="admin",
                role=legacy_role,
                secret=api_deps["settings"].jwt_secret,
            )
            resp = await client.get(
                "/controllers", headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code == 401, f"role={legacy_role!r} must be 401"

    @pytest.mark.asyncio
    async def test_login_now_mints_lowercase_role_accepted_by_api(
        self, client: AsyncClient
    ) -> None:
        login = await client.post(
            "/auth/login", json={"username": "admin", "password": "admin"}
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        resp = await client.get(
            "/controllers", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200


class TestMe:
    @pytest.mark.asyncio
    async def test_me_returns_admin_claims(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == {
            "user_id": 1, "username": "admin", "role": "admin", "theme": None,
        }

    @pytest.mark.asyncio
    async def test_me_returns_user_claims(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/auth/me", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json() == {
            "user_id": 2, "username": "operator", "role": "user", "theme": None,
        }

    @pytest.mark.asyncio
    async def test_me_reports_the_stored_theme(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        """The palette follows the USER, so /auth/me is where a fresh
        browser learns it. Stored as null until the operator chooses."""
        put = await client.put(
            "/users/me/theme", json={"theme": "phosphor"}, headers=user_headers,
        )
        assert put.status_code == 204, put.text

        resp = await client.get("/auth/me", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["theme"] == "phosphor"

    @pytest.mark.asyncio
    async def test_theme_must_be_one_the_frontend_can_render(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        """An unrenderable value parked on the account would leave the
        operator staring at an unstyled page after every login."""
        resp = await client.put(
            "/users/me/theme", json={"theme": "chartreuse"}, headers=user_headers,
        )
        assert resp.status_code == 422, resp.text

    @pytest.mark.asyncio
    async def test_me_requires_token(self, client: AsyncClient) -> None:
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_works_for_user_role(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post("/auth/refresh", headers=user_headers)
        assert resp.status_code == 200
        assert "access_token" in resp.json()
