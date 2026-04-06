"""Integration tests for /project REST API routes."""
from __future__ import annotations

import httpx


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


class TestListProjects:
    async def test_list_empty(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/project/list")
        assert resp.status_code == 200
        data = resp.json()
        assert data["projects"] == []

    async def test_list_with_files(
        self, client: httpx.AsyncClient, api_deps,
    ) -> None:
        import aiosqlite

        projects_dir = api_deps["projects_dir"]
        path = projects_dir / "testproj.spid"
        async with aiosqlite.connect(path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS Controladores "
                "(id INTEGER PRIMARY KEY, nome TEXT NOT NULL)"
            )
            await db.execute("INSERT INTO Controladores (nome) VALUES (?)", ("c1",))
            await db.commit()

        resp = await client.get("/project/list")
        assert resp.status_code == 200
        projects = resp.json()["projects"]
        assert len(projects) == 1
        assert projects[0]["name"] == "testproj"
        assert projects[0]["controller_count"] == 1


class TestImportProject:
    async def test_import_project(
        self, client: httpx.AsyncClient, tmp_path,
    ) -> None:
        import aiosqlite

        src = tmp_path / "upload.spid"
        async with aiosqlite.connect(src) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS Controladores "
                "(id INTEGER PRIMARY KEY, nome TEXT NOT NULL)"
            )
            await db.commit()
        file_bytes = src.read_bytes()

        resp = await client.post(
            "/project/import",
            files={"file": ("upload.spid", file_bytes, "application/octet-stream")},
            data={"name": "uploaded"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "uploaded"


class TestDownloadProject:
    async def test_download(self, client: httpx.AsyncClient) -> None:
        # Create a project first
        await client.post("/project/new", json={"name": "dltest"})
        resp = await client.get("/project/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/octet-stream"
        assert "dltest.spid" in resp.headers.get("content-disposition", "")
        assert len(resp.content) > 0


class TestDeleteProject:
    async def test_delete(
        self, client: httpx.AsyncClient, api_deps,
    ) -> None:
        projects_dir = api_deps["projects_dir"]
        (projects_dir / "removeme.spid").write_bytes(b"fake")
        resp = await client.delete("/project/removeme")
        assert resp.status_code == 204
        assert not (projects_dir / "removeme.spid").exists()

    async def test_delete_active_rejected(
        self, client: httpx.AsyncClient,
    ) -> None:
        await client.post("/project/new", json={"name": "nodelete"})
        resp = await client.delete("/project/nodelete")
        assert resp.status_code == 409
