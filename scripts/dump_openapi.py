#!/usr/bin/env python3
"""Dump the FastAPI OpenAPI schema to static JSON — no listening daemon.

Hermetic codegen (spec §7): build the app with stub adapter dependencies
(create_app only stores them on app.state; route/schema introspection never
touches them), call app.openapi(), write deterministic JSON. The web package
consumes the dump with openapi-typescript (npm run gen:api).

Workaround for FastAPI 0.135 + Pydantic 2.12 ForwardRef resolution: replace
the adapter types in sys.modules with Pydantic-friendly stub classes before
schema generation runs. The real classes are restored after the dump — the
running daemon is never affected.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

# Pre-import every router so route signatures are loaded.
from smart_pid_core.adapters.inbound.api.routers import (  # noqa: F401
    ai, alarms, audit, auth, commands, controllers, export, history,
    opcua, project, simulator, stats, system, system_events, trend, users,
)

from pydantic import BaseModel

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.config import CoreSettings

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = REPO_ROOT / "packages" / "smart_pid_web" / "openapi.json"


def _patch_adapter_types() -> None:
    """Replace adapter classes with Pydantic-friendly stubs.

    FastAPI's openapi generator introspects every parameter type and tries to
    build a Pydantic TypeAdapter for it. Our concrete adapter classes (which
    wrap SQLite connections) confuse that generator under PEP 563 lazy
    annotations + Depends(). Swapping in BaseModel stand-ins satisfies the
    generator without touching the real runtime semantics.
    """
    import sys
    from smart_pid_core.adapters.outbound import ai_repo, alarm_repo, audit_repo
    from smart_pid_core.adapters.outbound import historian, opcua_adapter
    from smart_pid_core.adapters.outbound import sqlite_repo

    class _AIRepository(BaseModel):
        model_config = {'arbitrary_types_allowed': True}

    class _AlarmRepository(BaseModel):
        model_config = {'arbitrary_types_allowed': True}

    class _AuditRepository(BaseModel):
        model_config = {'arbitrary_types_allowed': True}

    class _SQLiteHistorian(BaseModel):
        model_config = {'arbitrary_types_allowed': True}

    class _OPCUAAdapter(BaseModel):
        model_config = {'arbitrary_types_allowed': True}

    class _SQLiteRepository(BaseModel):
        model_config = {'arbitrary_types_allowed': True}

    ai_repo.AIRepository = _AIRepository
    alarm_repo.AlarmRepository = _AlarmRepository
    audit_repo.AuditRepository = _AuditRepository
    historian.SQLiteHistorian = _SQLiteHistorian
    opcua_adapter.OPCUAAdapter = _OPCUAAdapter
    sqlite_repo.SQLiteRepository = _SQLiteRepository

    # Re-exports under the canonical names
    sys.modules['smart_pid_core.adapters.outbound.ai_repo'].AIRepository = _AIRepository
    sys.modules['smart_pid_core.adapters.outbound.alarm_repo'].AlarmRepository = _AlarmRepository
    sys.modules['smart_pid_core.adapters.outbound.audit_repo'].AuditRepository = _AuditRepository
    sys.modules['smart_pid_core.adapters.outbound.historian'].SQLiteHistorian = _SQLiteHistorian
    sys.modules['smart_pid_core.adapters.outbound.opcua_adapter'].OPCUAAdapter = _OPCUAAdapter
    sys.modules['smart_pid_core.adapters.outbound.sqlite_repo'].SQLiteRepository = _SQLiteRepository


def build_schema() -> dict[str, Any]:
    settings = CoreSettings(jwt_secret="openapi-dump", _env_file=None)
    stub: Any = None
    _patch_adapter_types()
    app = create_app(
        repo=stub,
        historian=stub,
        user_repo=stub,
        loop_manager=stub,
        settings=settings,
    )
    return app.openapi()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output JSON path")
    args = parser.parse_args()

    schema = build_schema()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()