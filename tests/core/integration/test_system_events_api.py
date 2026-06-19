"""Integration tests for GET /system-events endpoint."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_get_system_events_empty(client, user_headers):
    resp = await client.get(
        "/system-events",
        params={"start": "2026-01-01T00:00:00", "end": "2026-12-31T23:59:59"},
        headers=user_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_system_events_requires_auth(client):
    resp = await client.get(
        "/system-events",
        params={"start": "2026-01-01T00:00:00", "end": "2026-12-31T23:59:59"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_system_events_with_data(client, user_headers, system_event_repo):
    await system_event_repo.insert_event("BACKEND", "INFO", "Started")
    await system_event_repo.insert_event("OPCUA", "WARNING", "Lost connection")

    resp = await client.get(
        "/system-events",
        params={"start": "2026-01-01T00:00:00", "end": "2027-12-31T23:59:59"},
        headers=user_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_system_events_filter_source(client, user_headers, system_event_repo):
    await system_event_repo.insert_event("BACKEND", "INFO", "Started")
    await system_event_repo.insert_event("OPCUA", "WARNING", "Lost")

    resp = await client.get(
        "/system-events",
        params={
            "start": "2026-01-01T00:00:00",
            "end": "2027-12-31T23:59:59",
            "source": "OPCUA",
        },
        headers=user_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["source"] == "OPCUA"
