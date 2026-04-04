"""Tests for APIClient export methods."""
import httpx

from smart_pid_hmi.services.api_client import APIClient
from smart_pid_hmi.services.session import Session


def _mock_transport(status: int, json_body: dict | list) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body)
    return httpx.MockTransport(handler)


def test_create_export():
    data = {
        "id": "abc-123",
        "controller_id": 1,
        "start": "2026-04-01T00:00:00Z",
        "end": "2026-04-02T00:00:00Z",
        "format": "csv",
        "status": "pending",
        "progress": 0,
        "file_path": None,
    }
    transport = _mock_transport(201, data)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    result = client.create_export(
        controller_id=1,
        start="2026-04-01T00:00:00Z",
        end="2026-04-02T00:00:00Z",
        fmt="csv",
    )
    assert result["id"] == "abc-123"
    assert result["status"] == "pending"


def test_get_export_status():
    data = {
        "id": "abc-123",
        "controller_id": 1,
        "start": "2026-04-01T00:00:00Z",
        "end": "2026-04-02T00:00:00Z",
        "format": "csv",
        "status": "done",
        "progress": 100,
        "file_path": "/tmp/export.csv",
    }
    transport = _mock_transport(200, data)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    result = client.get_export_status("abc-123")
    assert result["status"] == "done"
    assert result["progress"] == 100


def test_download_export(tmp_path):
    csv_content = "timestamp,pv,sp\n2026-04-01,50.0,50.0\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=csv_content.encode(), headers={
            "content-type": "text/csv",
        })

    transport = httpx.MockTransport(handler)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    dest = tmp_path / "downloaded.csv"
    result = client.download_export("abc-123", dest)
    assert result == dest
    assert dest.read_text() == csv_content
