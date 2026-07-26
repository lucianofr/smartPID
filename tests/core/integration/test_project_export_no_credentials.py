"""An exported .spid must NOT contain user/credential tables.

Credential boundary (fatia 7 contract): admin credentials live in users.db,
never in .spid projects. Asserts the SQLite schema of an exported project file
contains no user/credential table.
"""
from __future__ import annotations

import sqlite3

import pytest


@pytest.mark.asyncio
async def test_exported_spid_has_no_credential_tables(api_deps) -> None:
    project_service = api_deps["project_service"]
    meta = await project_service.new_project("boundary-check")  # async -> active
    export_path = await project_service.prepare_download()  # active .spid Path

    con = sqlite3.connect(export_path)
    try:
        names = {
            row[0].lower()
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        con.close()

    forbidden = {"users", "usuarios", "credentials", "passwords"}
    leaked = names & forbidden
    assert not leaked, f".spid export leaked credential tables: {leaked}"
    assert meta.name == "boundary-check"
