"""Tests for /history endpoints."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import TelemetryFrame

if TYPE_CHECKING:
    from httpx import AsyncClient


class TestHistory:
    @pytest.mark.asyncio
    async def test_query_with_data(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        historian = api_deps["historian"]
        now = datetime.now(tz=UTC)
        frames = [
            TelemetryFrame(
                controller_id=1, pv=FFSignal.good(50.0 + i), sp=FFSignal.good(50.0),
                co=FFSignal.good(25.0), bkcal_in=FFSignal.good(0.0),
                integral_val=0.0, timestamp=now + timedelta(seconds=i),
            )
            for i in range(5)
        ]
        await historian.write_batch(frames)

        resp = await client.get(
            "/history/1",
            params={
                "start": (now - timedelta(minutes=1)).isoformat(),
                "end": (now + timedelta(minutes=1)).isoformat(),
            },
            headers=user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["controller_id"] == 1
        assert data["count"] == 5
        assert len(data["frames"]) == 5

    @pytest.mark.asyncio
    async def test_query_empty(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get(
            "/history/1",
            params={
                "start": "2020-01-01T00:00:00+00:00",
                "end": "2020-01-02T00:00:00+00:00",
            },
            headers=user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["frames"] == []

    @pytest.mark.asyncio
    async def test_query_default_time_range(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/history/1", headers=user_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_query_with_limit(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        historian = api_deps["historian"]
        now = datetime.now(tz=UTC)
        frames = [
            TelemetryFrame(
                controller_id=2, pv=FFSignal.good(50.0), sp=FFSignal.good(50.0),
                co=FFSignal.good(25.0), bkcal_in=FFSignal.good(0.0),
                integral_val=0.0, timestamp=now + timedelta(seconds=i),
            )
            for i in range(10)
        ]
        await historian.write_batch(frames)

        resp = await client.get(
            "/history/2",
            params={
                "start": (now - timedelta(minutes=1)).isoformat(),
                "end": (now + timedelta(minutes=1)).isoformat(),
                "limit": 3,
            },
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 3

    @pytest.mark.asyncio
    async def test_query_no_auth_fails(self, client: AsyncClient) -> None:
        resp = await client.get("/history/1")
        assert resp.status_code == 401
