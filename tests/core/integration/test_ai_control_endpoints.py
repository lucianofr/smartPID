"""Tests for AI control endpoints (start/stop/pause) — Gap #15."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestAIStartEndpoint:
    @pytest.mark.asyncio
    async def test_start_ai_returns_ok(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post("/controllers/1/ai/start", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["controller_id"] == 1
        assert "start" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_start_ai_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/controllers/1/ai/start")
        assert resp.status_code == 401


class TestAIStopEndpoint:
    @pytest.mark.asyncio
    async def test_stop_ai_returns_ok(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post("/controllers/1/ai/stop", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "stop" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_stop_ai_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/controllers/1/ai/stop")
        assert resp.status_code == 401


class TestAIPauseEndpoint:
    @pytest.mark.asyncio
    async def test_pause_ai_returns_ok(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post("/controllers/1/ai/pause", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "pause" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_pause_ai_no_auth(self, client: AsyncClient) -> None:
        resp = await client.post("/controllers/1/ai/pause")
        assert resp.status_code == 401
