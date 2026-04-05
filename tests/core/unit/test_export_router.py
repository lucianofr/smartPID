"""Tests for the export router."""
from __future__ import annotations

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from smart_pid_core.adapters.inbound.api.routers.export import get_export_worker, router
from smart_pid_domain.models.export_models import ExportJob


def _make_app(worker) -> FastAPI:
    """Create a minimal FastAPI app with export router and overridden deps."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/export")

    # Override auth dependency to bypass JWT
    from smart_pid_core.adapters.inbound.api.dependencies import require_operator
    from smart_pid_domain.dtos.auth import UserClaims

    app.dependency_overrides[require_operator] = lambda: UserClaims(
        user_id=1, username="admin", role="ADMIN",
    )
    app.dependency_overrides[get_export_worker] = lambda: worker

    return app


def test_create_export():
    worker = MagicMock()
    job = ExportJob(
        id="test-id",
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="csv",
    )
    worker.create_job.return_value = job

    app = _make_app(worker)
    client = TestClient(app)
    resp = client.post(
        "/api/v1/export",
        json={
            "controller_id": 1,
            "start": "2026-04-01T00:00:00Z",
            "end": "2026-04-02T00:00:00Z",
            "format": "csv",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == "test-id"
    assert resp.json()["status"] == "pending"


def test_get_export_status():
    worker = MagicMock()
    job = ExportJob(
        id="test-id",
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="csv",
        status="running",
        progress=50,
    )
    worker.get_job.return_value = job

    app = _make_app(worker)
    client = TestClient(app)
    resp = client.get("/api/v1/export/test-id")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"
    assert resp.json()["progress"] == 50


def test_get_export_not_found():
    worker = MagicMock()
    worker.get_job.return_value = None

    app = _make_app(worker)
    client = TestClient(app)
    resp = client.get("/api/v1/export/nonexistent")
    assert resp.status_code == 404


def test_download_export(tmp_path):
    csv_file = tmp_path / "export_test.csv"
    csv_file.write_text("timestamp,pv,sp\n2026-04-01,50.0,50.0\n")

    worker = MagicMock()
    job = ExportJob(
        id="test-id",
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="csv",
        status="done",
        progress=100,
        file_path=str(csv_file),
    )
    worker.get_job.return_value = job

    app = _make_app(worker)
    client = TestClient(app)
    resp = client.get("/api/v1/export/test-id/download")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "50.0" in resp.text


def test_download_not_ready():
    worker = MagicMock()
    job = ExportJob(
        id="test-id",
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="csv",
        status="running",
        progress=50,
    )
    worker.get_job.return_value = job

    app = _make_app(worker)
    client = TestClient(app)
    resp = client.get("/api/v1/export/test-id/download")
    assert resp.status_code == 409
