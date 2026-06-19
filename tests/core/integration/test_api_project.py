"""Integration tests for /project REST API routes.

Security note: this is a single-admin deployment. Every route requires
authentication (401 when missing/invalid); there are no role tiers, so any
authenticated user may call every route. Project names are sanitized to
prevent path traversal outside projects_dir.
"""
from __future__ import annotations

import httpx


class TestGetCurrentProject:
    async def test_returns_200(
        self, client: httpx.AsyncClient, user_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/project/current", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "name" in data
        assert "path" in data
        assert "controller_count" in data

    async def test_no_auth_returns_401(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/project/current")
        assert resp.status_code == 401


class TestNewProject:
    async def test_creates_project(
        self, client: httpx.AsyncClient, supervisor_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/project/new", json={"name": "API Test"}, headers=supervisor_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "API Test"
        assert data["path"] == "API Test.spid"
        assert data["controller_count"] == 0

    async def test_conflict_returns_409(
        self, client: httpx.AsyncClient, supervisor_headers: dict[str, str],
    ) -> None:
        await client.post(
            "/project/new", json={"name": "dup"}, headers=supervisor_headers,
        )
        resp = await client.post(
            "/project/new", json={"name": "dup"}, headers=supervisor_headers,
        )
        assert resp.status_code == 409

    async def test_no_auth_returns_401(self, client: httpx.AsyncClient) -> None:
        resp = await client.post("/project/new", json={"name": "x"})
        assert resp.status_code == 401

    async def test_any_authenticated_user_allowed(
        self, client: httpx.AsyncClient, user_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/project/new", json={"name": "x"}, headers=user_headers,
        )
        assert resp.status_code == 200

    async def test_path_traversal_rejected(
        self,
        client: httpx.AsyncClient,
        supervisor_headers: dict[str, str],
        api_deps,
    ) -> None:
        projects_dir = api_deps["projects_dir"]
        resp = await client.post(
            "/project/new",
            json={"name": "../../etc/evil"},
            headers=supervisor_headers,
        )
        assert resp.status_code in (400, 422)
        # No file escaped the projects directory.
        escaped = projects_dir.parent.parent / "etc" / "evil.spid"
        assert not escaped.exists()

    async def test_absolute_path_rejected(
        self, client: httpx.AsyncClient, supervisor_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/project/new",
            json={"name": "/tmp/evil"},
            headers=supervisor_headers,
        )
        assert resp.status_code in (400, 422)


class TestOpenProject:
    async def test_opens_existing(
        self,
        client: httpx.AsyncClient,
        supervisor_headers: dict[str, str],
        api_deps,
    ) -> None:
        await client.post(
            "/project/new", json={"name": "openme"}, headers=supervisor_headers,
        )
        await client.post(
            "/project/new", json={"name": "other"}, headers=supervisor_headers,
        )
        resp = await client.post(
            "/project/open", json={"name": "openme"}, headers=supervisor_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "openme"

    async def test_returns_404_for_missing(
        self, client: httpx.AsyncClient, supervisor_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/project/open",
            json={"name": "nonexistent"},
            headers=supervisor_headers,
        )
        assert resp.status_code == 404

    async def test_any_authenticated_user_allowed(
        self, client: httpx.AsyncClient, user_headers: dict[str, str],
    ) -> None:
        # Any authenticated user reaches the handler; a missing project is 404,
        # never a role-based 403.
        resp = await client.post(
            "/project/open", json={"name": "x"}, headers=user_headers,
        )
        assert resp.status_code == 404

    async def test_path_traversal_rejected(
        self, client: httpx.AsyncClient, supervisor_headers: dict[str, str],
    ) -> None:
        resp = await client.post(
            "/project/open",
            json={"name": "../../../etc/passwd"},
            headers=supervisor_headers,
        )
        assert resp.status_code in (400, 422)


class TestListProjects:
    async def test_list_empty(
        self, client: httpx.AsyncClient, user_headers: dict[str, str],
    ) -> None:
        resp = await client.get("/project/list", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["projects"] == []

    async def test_no_auth_returns_401(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/project/list")
        assert resp.status_code == 401

    async def test_list_with_files(
        self, client: httpx.AsyncClient, user_headers: dict[str, str], api_deps,
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

        resp = await client.get("/project/list", headers=user_headers)
        assert resp.status_code == 200
        projects = resp.json()["projects"]
        assert len(projects) == 1
        assert projects[0]["name"] == "testproj"
        assert projects[0]["controller_count"] == 1


class TestImportProject:
    async def test_import_project(
        self, client: httpx.AsyncClient, supervisor_headers: dict[str, str], tmp_path,
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
            headers=supervisor_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "uploaded"

    async def test_any_authenticated_user_allowed(
        self, client: httpx.AsyncClient, user_headers: dict[str, str], tmp_path,
    ) -> None:
        # Single-admin deployment: any authenticated user may import.
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
            data={"name": "uploaded_by_user"},
            headers=user_headers,
        )
        assert resp.status_code == 200

    async def test_path_traversal_via_name_rejected(
        self,
        client: httpx.AsyncClient,
        supervisor_headers: dict[str, str],
        api_deps,
    ) -> None:
        projects_dir = api_deps["projects_dir"]
        resp = await client.post(
            "/project/import",
            files={"file": ("upload.spid", b"data", "application/octet-stream")},
            data={"name": "../../etc/evil"},
            headers=supervisor_headers,
        )
        assert resp.status_code in (400, 422)
        escaped = projects_dir.parent.parent / "etc" / "evil.spid"
        assert not escaped.exists()

    async def test_path_traversal_via_filename_rejected(
        self,
        client: httpx.AsyncClient,
        supervisor_headers: dict[str, str],
        api_deps,
    ) -> None:
        projects_dir = api_deps["projects_dir"]
        resp = await client.post(
            "/project/import",
            files={
                "file": (
                    "../../etc/evil.spid",
                    b"data",
                    "application/octet-stream",
                ),
            },
            headers=supervisor_headers,
        )
        assert resp.status_code in (400, 422)
        escaped = projects_dir.parent.parent / "etc" / "evil.spid"
        assert not escaped.exists()

    async def test_oversized_upload_rejected(
        self, client: httpx.AsyncClient, supervisor_headers: dict[str, str],
    ) -> None:
        # Exceed the configured max upload size (default 50 MB in tests is
        # lowered via settings to keep the payload small).
        big = b"\x00" * (2 * 1024 * 1024)  # 2 MB; test settings cap below this
        resp = await client.post(
            "/project/import",
            files={"file": ("big.spid", big, "application/octet-stream")},
            data={"name": "toobig"},
            headers=supervisor_headers,
        )
        assert resp.status_code == 413


class TestDownloadProject:
    async def test_download(
        self, client: httpx.AsyncClient, supervisor_headers: dict[str, str],
    ) -> None:
        await client.post(
            "/project/new", json={"name": "dltest"}, headers=supervisor_headers,
        )
        resp = await client.get("/project/download", headers=supervisor_headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/octet-stream"
        assert "dltest.spid" in resp.headers.get("content-disposition", "")
        assert len(resp.content) > 0

    async def test_no_auth_returns_401(self, client: httpx.AsyncClient) -> None:
        resp = await client.get("/project/download")
        assert resp.status_code == 401

    async def test_any_authenticated_user_allowed(
        self, client: httpx.AsyncClient, user_headers: dict[str, str],
    ) -> None:
        # Single-admin deployment: any authenticated user may download.
        await client.post(
            "/project/new", json={"name": "dluser"}, headers=user_headers,
        )
        resp = await client.get("/project/download", headers=user_headers)
        assert resp.status_code == 200


class TestDeleteProject:
    async def test_delete(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str], api_deps,
    ) -> None:
        projects_dir = api_deps["projects_dir"]
        (projects_dir / "removeme.spid").write_bytes(b"fake")
        resp = await client.delete("/project/removeme", headers=admin_headers)
        assert resp.status_code == 204
        assert not (projects_dir / "removeme.spid").exists()

    async def test_delete_active_rejected(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str],
        supervisor_headers: dict[str, str],
    ) -> None:
        await client.post(
            "/project/new", json={"name": "nodelete"}, headers=supervisor_headers,
        )
        resp = await client.delete("/project/nodelete", headers=admin_headers)
        assert resp.status_code == 409

    async def test_any_authenticated_user_allowed(
        self, client: httpx.AsyncClient, supervisor_headers: dict[str, str],
    ) -> None:
        # Any authenticated user reaches the handler; a missing project is 404,
        # never a role-based 403.
        resp = await client.delete("/project/x", headers=supervisor_headers)
        assert resp.status_code == 404

    async def test_no_auth_returns_401(self, client: httpx.AsyncClient) -> None:
        resp = await client.delete("/project/x")
        assert resp.status_code == 401

    async def test_path_traversal_rejected(
        self, client: httpx.AsyncClient, admin_headers: dict[str, str], api_deps,
    ) -> None:
        projects_dir = api_deps["projects_dir"]
        target = projects_dir.parent / "victim.spid"
        target.write_bytes(b"keep me")
        # URL-encoded traversal in the path segment.
        resp = await client.delete(
            "/project/..%2Fvictim", headers=admin_headers,
        )
        assert resp.status_code in (400, 404, 422)
        assert target.exists()
