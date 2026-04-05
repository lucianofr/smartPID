"""Integration test for audit trail old/new value capture — Gap #50."""
from __future__ import annotations

import json

import httpx
import pytest

from smart_pid_core.adapters.inbound.api.auth import create_access_token


@pytest.mark.asyncio
async def test_update_controller_audit_captures_old_new(
    app, client, admin_headers, api_deps,
):
    """PUT /controllers/{id} should log old and new values in audit detail."""
    # Create a controller first
    create_resp = await client.post("/controllers", json={
        "name": "FIC-100",
        "description": "test",
        "scan_rate_ms": 1000,
        "gain": 1.5,
        "reset": 10.0,
        "rate": 0.0,
    }, headers=admin_headers)
    assert create_resp.status_code == 201
    cid = create_resp.json()["id"]

    # Update it — change gain and description
    update_resp = await client.put(f"/controllers/{cid}", json={
        "gain": 2.0,
        "description": "updated desc",
    }, headers=admin_headers)
    assert update_resp.status_code == 200

    # Check audit trail
    from datetime import UTC, datetime, timedelta

    audit_repo = api_deps["audit_repo"]
    now = datetime.now(tz=UTC)
    history = await audit_repo.get_history(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
    )
    # Find the UPDATE_CONTROLLER entry
    update_entry = next(
        (e for e in history if e["action"] == "UPDATE_CONTROLLER"),
        None,
    )
    assert update_entry is not None

    detail = json.loads(update_entry["detail"])
    assert "old" in detail
    assert "new" in detail
    assert detail["old"]["gain"] == 1.5
    assert detail["new"]["gain"] == 2.0
    assert detail["old"]["description"] == "test"
    assert detail["new"]["description"] == "updated desc"
