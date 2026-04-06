"""Integration tests for /project REST API routes."""
from __future__ import annotations

import httpx
import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository


class TestGetCurrentProject:
    async def test_returns_200(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/project/current")
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "path" in data
        assert "controller_count" in data


class TestNewProject:
    async def test_creates_project(
        self, client: httpx.AsyncClient, tmp_path,
    ) -> None:
        dest = str(tmp_path / "new_api.spid")
        resp = await client.post(
            "/project/new", json={"name": "API Test", "path": dest},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "API Test"
        assert data["path"] == dest
        assert data["controller_count"] == 0


class TestOpenProject:
    async def test_opens_existing(
        self, client: httpx.AsyncClient, tmp_path,
    ) -> None:
        # Create a valid .spid file
        existing = tmp_path / "open_api.spid"
        prep = SQLiteRepository(existing)
        await prep.initialize()
        await prep.set_meta("nome", "OpenMe")
        await prep.close()

        resp = await client.post(
            "/project/open", json={"path": str(existing)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "OpenMe"

    async def test_returns_404_for_missing(
        self, client: httpx.AsyncClient, tmp_path,
    ) -> None:
        missing = str(tmp_path / "nope.spid")
        resp = await client.post(
            "/project/open", json={"path": missing},
        )
        assert resp.status_code == 404


class TestSaveAs:
    async def test_copies_project(
        self, client: httpx.AsyncClient, tmp_path,
    ) -> None:
        dest = str(tmp_path / "saved.spid")
        resp = await client.post(
            "/project/save-as", json={"path": dest},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["path"] == dest
