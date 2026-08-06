"""Integration tests for GET /trend/{controller_id} and the TrendBufferWorker parse path."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import msgpack
import pytest

from smart_pid_core.application.trend_buffer import RETENTION_S, TrendBuffer
from smart_pid_core.application.workers.trend_buffer_worker import TrendBufferWorker
from smart_pid_domain.models.signal import FFSignal
from smart_pid_domain.models.telemetry import TelemetryFrame

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
    async def test_seconds_over_retention_is_rejected(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get(
            "/trend/4", params={"seconds": int(RETENTION_S) + 1}, headers=user_headers
        )
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


_BASE = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


def _history_frame(controller_id: int, pv: float, ts: datetime) -> TelemetryFrame:
    return TelemetryFrame(
        controller_id=controller_id,
        pv=FFSignal.good(pv),
        sp=FFSignal.good(50.0),
        co=FFSignal.good(25.0),
        bkcal_in=FFSignal.good(0.0),
        integral_val=0.0,
        timestamp=ts,
    )


async def _seed(app, api_deps, controller_id: int) -> None:
    """Ring holds the newest 60 s; Log_Processo holds the 300 s before that.

    The state a daemon is in shortly after a restart: only HYDRATE_S was
    pre-loaded, so a wider window has to come off disk.
    """
    for i in range(60):
        app.state.trend_buffer.append(
            controller_id, (_BASE - timedelta(seconds=59 - i)).timestamp(), float(i), 50.0, 25.0
        )
    await api_deps["historian"].write_batch(
        [
            _history_frame(controller_id, pv=1000.0 + i, ts=_BASE - timedelta(seconds=300 - i))
            for i in range(241)
        ]
    )


class TestTrendLazyFill:
    @pytest.mark.asyncio
    async def test_window_wider_than_the_ring_is_filled_from_the_historian(
        self, client: AsyncClient, app, api_deps, user_headers: dict[str, str]
    ) -> None:
        await _seed(app, api_deps, 21)

        # The ring alone can only answer 60 s of this.
        resp = await client.get("/trend/21", params={"seconds": 300}, headers=user_headers)

        assert resp.status_code == 200
        frames = resp.json()["frames"]
        assert len(frames) == 301  # 241 backfilled + 60 already held
        stamps = [f["timestamp"] for f in frames]
        assert stamps == sorted(stamps)
        # Oldest frame came off disk, newest from the live end.
        assert frames[0]["pv"] == 1000.0
        assert frames[-1]["pv"] == 59.0

    @pytest.mark.asyncio
    async def test_a_narrow_window_never_touches_the_database(
        self, client: AsyncClient, app, api_deps, user_headers: dict[str, str]
    ) -> None:
        await _seed(app, api_deps, 22)
        calls = _count_fills(app, api_deps)

        resp = await client.get("/trend/22", params={"seconds": 30}, headers=user_headers)

        assert resp.status_code == 200
        assert calls == []

    @pytest.mark.asyncio
    async def test_the_fill_happens_once_not_on_every_request(
        self, client: AsyncClient, app, api_deps, user_headers: dict[str, str]
    ) -> None:
        """The slow path is the point of the design; paying it twice is not."""
        await _seed(app, api_deps, 23)
        calls = _count_fills(app, api_deps)

        first = await client.get("/trend/23", params={"seconds": 300}, headers=user_headers)
        second = await client.get("/trend/23", params={"seconds": 300}, headers=user_headers)

        assert first.json()["count"] == second.json()["count"] == 301
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_a_failed_fill_still_serves_what_the_ring_holds(
        self, client: AsyncClient, app, api_deps, user_headers: dict[str, str]
    ) -> None:
        await _seed(app, api_deps, 24)

        async def broken(*_args, **_kwargs):
            raise RuntimeError("historian unavailable")

        app.state.historian.query_decimated = broken

        resp = await client.get("/trend/24", params={"seconds": 300}, headers=user_headers)

        assert resp.status_code == 200
        assert resp.json()["count"] == 60  # exactly what the ring had


def _count_fills(app, api_deps) -> list[tuple]:
    """Record every historian read the route performs."""
    calls: list[tuple] = []
    original = api_deps["historian"].query_decimated

    async def counting(*args, **kwargs):
        calls.append(args)
        return await original(*args, **kwargs)

    app.state.historian.query_decimated = counting
    return calls
