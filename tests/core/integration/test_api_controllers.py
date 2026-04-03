"""Tests for /config/controllers CRUD endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


class TestListControllers:
    @pytest.mark.asyncio
    async def test_list_empty(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/config/controllers", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, client: AsyncClient) -> None:
        resp = await client.get("/config/controllers")
        assert resp.status_code == 401


class TestCreateController:
    @pytest.mark.asyncio
    async def test_create_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/config/controllers",
            json={"name": "TIC-101", "description": "Temperature loop"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "TIC-101"
        assert data["id"] > 0

    @pytest.mark.asyncio
    async def test_create_non_admin_forbidden(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/config/controllers",
            json={"name": "TIC-101"},
            headers=user_headers,
        )
        assert resp.status_code == 403


class TestGetController:
    @pytest.mark.asyncio
    async def test_get_existing(
        self, client: AsyncClient, admin_headers: dict[str, str], user_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/config/controllers",
            json={"name": "TIC-101"},
            headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.get(f"/config/controllers/{cid}", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "TIC-101"

    @pytest.mark.asyncio
    async def test_get_not_found(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/config/controllers/9999", headers=user_headers)
        assert resp.status_code == 404


class TestUpdateController:
    @pytest.mark.asyncio
    async def test_update_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/config/controllers",
            json={"name": "TIC-101"},
            headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.put(
            f"/config/controllers/{cid}",
            json={"description": "Updated"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated"


class TestDeleteController:
    @pytest.mark.asyncio
    async def test_delete_as_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        create_resp = await client.post(
            "/config/controllers",
            json={"name": "TIC-101"},
            headers=admin_headers,
        )
        cid = create_resp.json()["id"]
        resp = await client.delete(f"/config/controllers/{cid}", headers=admin_headers)
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_not_found(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.delete("/config/controllers/9999", headers=admin_headers)
        assert resp.status_code == 404
