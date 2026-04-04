"""Tests for APIClient stats methods."""
import httpx

from smart_pid_hmi.services.api_client import APIClient
from smart_pid_hmi.services.session import Session


def _mock_transport(status: int, json_body: dict | list) -> httpx.MockTransport:
    """Create a mock transport that always returns the given response."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body)
    return httpx.MockTransport(handler)


def test_get_controller_stats():
    data = {"iae": 12.5, "itae": 30.0, "ise": 5.0, "mse": 1.2, "tv": 0.8}
    transport = _mock_transport(200, data)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    result = client.get_controller_stats(1)
    assert result["iae"] == 12.5
    assert result["tv"] == 0.8


def test_get_all_stats():
    data = [
        {"controller_id": 1, "iae": 12.5, "tv": 0.8},
        {"controller_id": 2, "iae": 3.2, "tv": 0.1},
    ]
    transport = _mock_transport(200, data)
    session = Session()
    client = APIClient(base_url="http://test:8000", session=session, transport=transport)
    result = client.get_all_stats()
    assert len(result) == 2
    assert result[0]["controller_id"] == 1
    assert result[1]["iae"] == 3.2
