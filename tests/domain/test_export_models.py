"""Tests for ExportRequest and ExportJob DTOs."""
import pytest
from pydantic import ValidationError

from smart_pid_domain.models.export_models import ExportJob, ExportRequest


def test_export_request_creation():
    req = ExportRequest(
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="csv",
    )
    assert req.controller_id == 1
    assert req.format == "csv"


def test_export_request_defaults_to_csv():
    req = ExportRequest(
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
    )
    assert req.format == "csv"


def test_export_request_json_format():
    req = ExportRequest(
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="json",
    )
    assert req.format == "json"


def test_export_request_invalid_format():
    with pytest.raises(ValidationError):
        ExportRequest(
            controller_id=1,
            start="2026-04-01T00:00:00Z",
            end="2026-04-02T00:00:00Z",
            format="xml",
        )


def test_export_job_creation():
    job = ExportJob(
        id="abc-123",
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="csv",
    )
    assert job.id == "abc-123"
    assert job.status == "pending"
    assert job.progress == 0
    assert job.file_path is None


def test_export_job_defaults():
    job = ExportJob(
        id="x",
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="json",
    )
    assert job.status == "pending"
    assert job.progress == 0
    assert job.file_path is None


def test_export_job_with_all_fields():
    job = ExportJob(
        id="x",
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        format="csv",
        status="done",
        progress=100,
        file_path="/tmp/export.csv",
    )
    assert job.status == "done"
    assert job.progress == 100
    assert job.file_path == "/tmp/export.csv"


def test_export_job_invalid_status():
    with pytest.raises(ValidationError):
        ExportJob(
            id="x",
            controller_id=1,
            start="2026-04-01T00:00:00Z",
            end="2026-04-02T00:00:00Z",
            format="csv",
            status="invalid",
        )
