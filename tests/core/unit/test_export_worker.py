"""Tests for ExportWorker."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from smart_pid_core.application.export_worker import ExportWorker
from smart_pid_domain.models.export_models import ExportRequest
from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import TelemetryFrame


def _make_frames(n: int = 3) -> list[TelemetryFrame]:
    return [
        TelemetryFrame(
            controller_id=1,
            pv=FFSignal.good(50.0 + i),
            sp=FFSignal.good(50.0),
            co=FFSignal.good(60.0 + i),
            bkcal_in=FFSignal.good(0.0),
            integral_val=0.0,
            timestamp=datetime(2026, 4, 1, 0, 0, i, tzinfo=UTC),
        )
        for i in range(n)
    ]


def test_create_job():
    historian = AsyncMock()
    worker = ExportWorker(historian=historian, export_dir="/tmp/exports")
    req = ExportRequest(
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="csv",
    )
    job = worker.create_job(req)
    assert job.status == "pending"
    assert job.controller_id == 1
    assert job.format == "csv"
    assert job.id  # non-empty UUID


def test_get_job():
    historian = AsyncMock()
    worker = ExportWorker(historian=historian, export_dir="/tmp/exports")
    req = ExportRequest(
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="csv",
    )
    job = worker.create_job(req)
    retrieved = worker.get_job(job.id)
    assert retrieved is not None
    assert retrieved.id == job.id


def test_get_job_not_found():
    historian = AsyncMock()
    worker = ExportWorker(historian=historian, export_dir="/tmp/exports")
    assert worker.get_job("nonexistent") is None


@pytest.mark.asyncio
async def test_run_export_csv(tmp_path):
    frames = _make_frames(3)
    historian = AsyncMock()
    historian.query = AsyncMock(return_value=frames)

    worker = ExportWorker(historian=historian, export_dir=str(tmp_path))
    req = ExportRequest(
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="csv",
    )
    job = worker.create_job(req)
    await worker.run_export(job)

    updated = worker.get_job(job.id)
    assert updated.status == "done"
    assert updated.progress == 100
    assert updated.file_path is not None

    import pathlib
    content = pathlib.Path(updated.file_path).read_text()
    assert "pv" in content
    assert "50.0" in content


@pytest.mark.asyncio
async def test_run_export_json(tmp_path):
    frames = _make_frames(2)
    historian = AsyncMock()
    historian.query = AsyncMock(return_value=frames)

    worker = ExportWorker(historian=historian, export_dir=str(tmp_path))
    req = ExportRequest(
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="json",
    )
    job = worker.create_job(req)
    await worker.run_export(job)

    updated = worker.get_job(job.id)
    assert updated.status == "done"

    import pathlib
    data = json.loads(pathlib.Path(updated.file_path).read_text())
    assert len(data) == 2
    assert data[0]["pv"] == 50.0
