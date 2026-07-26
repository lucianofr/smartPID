"""Hermetic OpenAPI dump powering the web codegen chain (spec §7).

Runs the dump script as a subprocess (the CLI surface npm calls) and asserts
the phase-0 schema surface is present and the output is deterministic.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "dump_openapi.py"


def _dump(out: Path) -> dict:
    subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(out)],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
    )
    return json.loads(out.read_text(encoding="utf-8"))


def test_dump_contains_the_phase0_surface(tmp_path: Path) -> None:
    schema = _dump(tmp_path / "openapi.json")
    assert schema["info"]["title"] == "Smart PID API"
    paths = schema["paths"]
    assert "/auth/login" in paths
    assert "/auth/me" in paths
    # Phase-0 users router (spec §9): /users + /users/{user_id}.
    assert any(p == "/users" or p.startswith("/users/") for p in paths)
    # Lowercase two-role enum (spec §9). Do NOT assert per-route 403 objects:
    # plain HTTPException 403s are not auto-documented by FastAPI.
    role_enum = schema["components"]["schemas"]["UserRole"]["enum"]
    assert sorted(role_enum) == ["admin", "user"]


def test_dump_is_deterministic(tmp_path: Path) -> None:
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    _dump(a)
    _dump(b)
    assert a.read_bytes() == b.read_bytes()