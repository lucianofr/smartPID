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
        self, client: httpx.AsyncClient,
    ) -> None:
        resp = await client.post(
            "/project/new", json={"name": "API Test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "API Test"
        assert data["path"] == "API Test.spid"
        assert data["controller_count"] == 0

    async def test_conflict_returns_409(
        self, client: httpx.AsyncClient,
    ) -> None:
        await client.post("/project/new", json={"name": "dup"})
        resp = await client.post("/project/new", json={"name": "dup"})
        assert resp.status_code == 409


class TestOpenProject:
    async def test_opens_existing(
        self, client: httpx.AsyncClient, api_deps,
    ) -> None:
        # Create a project via the API first
        await client.post("/project/new", json={"name": "openme"})
        # Now create another project so "openme" is no longer active
        await client.post("/project/new", json={"name": "other"})
        # Open the first project
        resp = await client.post(
            "/project/open", json={"name": "openme"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "openme"

    async def test_returns_404_for_missing(
        self, client: httpx.AsyncClient,
    ) -> None:
        resp = await client.post(
            "/project/open", json={"name": "nonexistent"},
        )
        assert resp.status_code == 404
