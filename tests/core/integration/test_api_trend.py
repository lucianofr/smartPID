"""Integration tests for GET /trend/{controller_id} and the TrendBufferWorker parse path."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import msgpack
import pytest

from smart_pid_core.application.trend_buffer import TrendBuffer
from smart_pid_core.application.workers.trend_buffer_worker import TrendBufferWorker

if TYPE_CHECKING:
    from httpx import AsyncClient


def _frame_payload(controller_id: int, ts: str, pv: float, sp: float, co: float) -> bytes:
    """Same msgpack shape IOWorker publishes on TELEMETRY.{cid}."""
    signal = {"value": 0.0, "severity": "GOOD", "limit_bits": "NONE", "sub_status": "NONE"}
    return msgpack.packb(
        {
            "controller_id": controller_id,
            "pv": {**signal, "value": pv},
            "sp": {**signal, "value": sp},
            "co": {**signal, "value": co},
            "timestamp": ts,
        }
    )


class TestTrendBufferWorkerParse:
    def test_process_appends_frame(self) -> None:
        buf = TrendBuffer()
        worker = TrendBufferWorker.__new__(TrendBufferWorker)
        worker._buffer = buf
        payload = _frame_payload(7, "2026-08-03T12:00:00+00:00", 61.5, 60.0, 42.0)
        worker._process((b"TELEMETRY.7", payload))
        window = buf.query(7, 60.0)
        assert len(window) == 1
        assert window[0].pv == 61.5
        assert window[0].sp == 60.0
        assert window[0].co == 42.0
        assert window[0].ts == datetime(2026, 8, 3, 12, 0, tzinfo=UTC).timestamp()

    def test_process_accepts_epoch_timestamp(self) -> None:
        buf = TrendBuffer()
        worker = TrendBufferWorker.__new__(TrendBufferWorker)
        worker._buffer = buf
        signal = {"value": 1.0, "severity": "GOOD", "limit_bits": "NONE", "sub_status": "NONE"}
        payload = msgpack.packb(
            {
                "controller_id": 7,
                "pv": signal,
                "sp": {**signal, "value": 2.0},
                "co": {**signal, "value": 3.0},
                "timestamp": 1770000000.0,
            }
        )
        worker._process((b"TELEMETRY.7", payload))
        assert buf.query(7, 60.0)[0].ts == 1770000000.0

    def test_malformed_payload_is_dropped(self) -> None:
        buf = TrendBuffer()
        worker = TrendBufferWorker.__new__(TrendBufferWorker)
        worker._buffer = buf
        worker._process((b"TELEMETRY.7", b"not-msgpack"))
        worker._process((b"TELEMETRY.7", msgpack.packb({"controller_id": 7})))
        assert buf.query(7, 60.0) == []


class TestTrendEndpoint:
    @pytest.mark.asyncio
    async def test_returns_ring_contents(
        self, client: AsyncClient, app, user_headers: dict[str, str]
    ) -> None:
        now = datetime.now(tz=UTC).timestamp()
        for i in range(5):
            app.state.trend_buffer.append(3, now - 100 + i, 50.0 + i, 50.0, 25.0)

        resp = await client.get("/trend/3", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["controller_id"] == 3
        assert data["count"] == 5
        assert [f["pv"] for f in data["frames"]] == [50.0, 51.0, 52.0, 53.0, 54.0]
        # Ascending ISO-8601 timestamps, same contract as /history.
        stamps = [f["timestamp"] for f in data["frames"]]
        assert stamps == sorted(stamps)

    @pytest.mark.asyncio
    async def test_seconds_param_narrows_window(
        self, client: AsyncClient, app, user_headers: dict[str, str]
    ) -> None:
        now = datetime.now(tz=UTC).timestamp()
        for i in range(10):
            app.state.trend_buffer.append(4, now - 100 + i, float(i), 0.0, 0.0)

        resp = await client.get("/trend/4", params={"seconds": 3}, headers=user_headers)
        assert resp.status_code == 200
        # Inclusive 3 s span at 1 Hz: the four newest samples.
        assert resp.json()["count"] == 4

    @pytest.mark.asyncio
    async def test_seconds_over_one_hour_is_rejected(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/trend/4", params={"seconds": 3601}, headers=user_headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_ring_returns_zero_frames(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/trend/99", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0
        assert resp.json()["frames"] == []

    @pytest.mark.asyncio
    async def test_no_auth_fails(self, client: AsyncClient) -> None:
        resp = await client.get("/trend/1")
        assert resp.status_code == 401
