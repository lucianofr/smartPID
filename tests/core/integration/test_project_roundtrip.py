"""Regression cover for E2E-040: download -> import has to round-trip.

``GET /project/download`` streams whatever the active project weighs, and a
plant accumulates ``Log_Processo`` rows for as long as it runs, so any import
ceiling below that size silently breaks the documented workflow. The defect
this file pins was exactly that: a 53 MB download that the 50 MB import cap
refused with 413.

These tests deliberately run against the *shipped* settings. The root
``api_deps`` pins ``max_upload_bytes`` to 1 MB so the suite's upload-refusal
tests can post a small payload, and that override is precisely what would hide
the limits drifting apart again.
"""
from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from smart_pid_core.config import CoreSettings
from smart_pid_domain.models.controller import Controller

if TYPE_CHECKING:
    import httpx

# The ceiling that made the round-trip impossible. A generated archive has to
# clear it for these tests to prove anything.
_OLD_IMPORT_CAP = 50 * 1024 * 1024


@pytest.fixture(autouse=True)
def shipped_upload_limits(api_deps) -> CoreSettings:
    """Restore the limits operators actually deploy with.

    Reading the values off ``CoreSettings.model_fields`` rather than repeating
    them is the drift guard: lowering the shipped default back under a real
    project's size fails the round-trip test below instead of only failing in
    the field.
    """
    settings = api_deps["settings"]
    fields = CoreSettings.model_fields
    settings.max_upload_bytes = fields["max_upload_bytes"].default
    settings.min_free_disk_bytes = fields["min_free_disk_bytes"].default
    return settings


def _grow_history(db_path: Path, target_bytes: int) -> tuple[int, int]:
    """Fill ``Log_Processo`` until the project file passes ``target_bytes``.

    Doubling the table beats row-by-row inserts by orders of magnitude, which
    is what makes a genuine >50 MB round-trip affordable as a test instead of a
    53 MB fixture committed to the repo.
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO Log_Processo "
            "(controlador_id, timestamp, pv, sp, co, integral_val) "
            "VALUES (1, '2026-07-27T00:00:00', 50.0, 50.0, 42.0, 0.0)"
        )
        conn.commit()
        while db_path.stat().st_size <= target_bytes:
            conn.execute(
                "INSERT INTO Log_Processo "
                "(controlador_id, timestamp, pv, sp, co, integral_val) "
                "SELECT controlador_id, timestamp, pv, sp, co, integral_val "
                "FROM Log_Processo"
            )
            conn.commit()
        rows = conn.execute("SELECT COUNT(*) FROM Log_Processo").fetchone()[0]
    finally:
        conn.close()
    return rows, db_path.stat().st_size


async def _seed_controllers(repo, count: int) -> None:
    for i in range(count):
        await repo.save(Controller(name=f"LOOP-{i + 1:02d}"))


async def _download_to(client: httpx.AsyncClient, headers: dict[str, str],
                       dest: Path) -> int:
    """Stream the download to ``dest`` and return its size."""
    async with client.stream(
        "GET", "/project/download", headers=headers,
    ) as response:
        assert response.status_code == 200, await response.aread()
        with dest.open("wb") as sink:
            async for chunk in response.aiter_bytes():
                sink.write(chunk)
    return dest.stat().st_size


def _staging_residue(projects_dir: Path) -> list[Path]:
    """Staging files the import layer should never leave behind."""
    return list(projects_dir.glob(".import-*"))


class TestDownloadImportRoundTrip:
    async def test_project_with_real_history_survives_download_then_import(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        api_deps,
        tmp_path,
    ) -> None:
        """The exact workflow E2E-040 walks, at a size a real plant reaches."""
        repo = api_deps["repo"]
        await _seed_controllers(repo, 4)
        rows, project_bytes = _grow_history(repo.db_path, _OLD_IMPORT_CAP)

        archive = tmp_path / "downloaded.spid"
        size = await _download_to(client, admin_headers, archive)

        # Sentinel: without this the test would pass on a 4 KB file and prove
        # nothing about the cap.
        assert size > _OLD_IMPORT_CAP, (
            f"generated project is {size} bytes across {rows} history rows; it "
            f"must exceed the old {_OLD_IMPORT_CAP}-byte cap to be a regression"
        )

        with archive.open("rb") as upload:
            response = await client.post(
                "/project/import",
                files={"file": ("plant.spid", upload, "application/octet-stream")},
                data={"name": "roundtrip"},
                headers=admin_headers,
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["name"] == "roundtrip"
        # "Import restores controllers" — the procedure's wording.
        assert body["controller_count"] == 4
        assert (api_deps["projects_dir"] / "roundtrip.spid").exists()
        assert _staging_residue(api_deps["projects_dir"]) == []

    async def test_import_echoes_the_requested_name_not_the_archive_name(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        api_deps,
        tmp_path,
    ) -> None:
        """The response used to echo the donor's stored name (E2E-040)."""
        repo = api_deps["repo"]
        await repo.set_meta("nome", "e2e-disposable")

        archive = tmp_path / "named.spid"
        await _download_to(client, admin_headers, archive)

        with archive.open("rb") as upload:
            response = await client.post(
                "/project/import",
                files={"file": ("e2e-disposable.spid", upload,
                                "application/octet-stream")},
                data={"name": "e2e-imported"},
                headers=admin_headers,
            )

        assert response.status_code == 200, response.text
        assert response.json()["name"] == "e2e-imported"
        assert response.json()["path"] == "e2e-imported.spid"
        # /project/current must agree with the roster, which keys off the file.
        current = await client.get("/project/current", headers=admin_headers)
        assert current.json()["name"] == "e2e-imported"


class TestImportGuards:
    """The DoS protection the raised ceiling rests on."""

    async def test_upload_over_the_ceiling_is_refused_without_residue(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        api_deps,
        shipped_upload_limits: CoreSettings,
    ) -> None:
        shipped_upload_limits.max_upload_bytes = 512 * 1024
        response = await client.post(
            "/project/import",
            files={"file": ("big.spid", b"\x00" * (2 * 1024 * 1024),
                            "application/octet-stream")},
            data={"name": "toobig"},
            headers=admin_headers,
        )
        assert response.status_code == 413
        # A rejected upload that left its staging file behind would BE the
        # disk-fill vector the ceiling is supposed to prevent.
        assert _staging_residue(api_deps["projects_dir"]) == []
        assert not (api_deps["projects_dir"] / "toobig.spid").exists()

    async def test_low_free_space_is_refused_with_507(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        api_deps,
        shipped_upload_limits: CoreSettings,
    ) -> None:
        """The guard that actually bounds disk-fill, unlike a per-request cap."""
        free = shutil.disk_usage(api_deps["projects_dir"]).free
        shipped_upload_limits.min_free_disk_bytes = free + 1

        response = await client.post(
            "/project/import",
            files={"file": ("x.spid", b"\x00" * 4096,
                            "application/octet-stream")},
            data={"name": "nospace"},
            headers=admin_headers,
        )
        assert response.status_code == 507
        assert _staging_residue(api_deps["projects_dir"]) == []

    async def test_non_archive_upload_is_rejected_without_residue(
        self,
        client: httpx.AsyncClient,
        admin_headers: dict[str, str],
        api_deps,
    ) -> None:
        """Import re-points the live repository, so junk must never install."""
        response = await client.post(
            "/project/import",
            files={"file": ("junk.spid", b"not-a-db" * 1024,
                            "application/octet-stream")},
            data={"name": "junk"},
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert not (api_deps["projects_dir"] / "junk.spid").exists()
        assert _staging_residue(api_deps["projects_dir"]) == []
