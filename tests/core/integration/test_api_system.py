"""Tests for /system endpoints."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestSystemStatus:
    @pytest.mark.asyncio
    async def test_status_returns_running(self, client: AsyncClient) -> None:
        resp = await client.get("/system/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["api_version"] == "2.0.0"
        assert "uptime_s" in data
        assert "active_controllers" in data
        assert "bus_active" in data

    @pytest.mark.asyncio
    async def test_status_no_auth_required(self, client: AsyncClient) -> None:
        resp = await client.get("/system/status")
        assert resp.status_code == 200
