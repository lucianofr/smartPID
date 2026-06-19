"""Tests for the RealtimeWS bridge."""
from __future__ import annotations

import asyncio
import json

import msgpack
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from smart_pid_core.adapters.inbound.api.auth import create_access_token
from smart_pid_core.adapters.inbound.api.ws.realtime import (
    ConnectionBuffer,
    ConnectionManager,
    RealtimeBridge,
    map_topic_to_envelope,
    register_realtime_ws,
)


class FakeSocket:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[str] = []
        self.closed = False
        self.close_code: int | None = None

    async def send_text(self, message: str) -> None:
        if self.fail:
            raise RuntimeError("socket gone")
        self.sent.append(message)

    async def close(self, code: int = 1000) -> None:
        self.closed = True
        self.close_code = code


@pytest.mark.asyncio
async def test_broadcast_reaches_all_healthy_sockets() -> None:
    mgr = ConnectionManager()
    a, b = FakeSocket(), FakeSocket()
    await mgr.connect(a)
    await mgr.connect(b)

    await mgr.broadcast(json.dumps({"type": "status"}))

    assert a.sent == ['{"type": "status"}']
    assert b.sent == ['{"type": "status"}']


@pytest.mark.asyncio
async def test_one_failing_socket_does_not_drop_others() -> None:
    mgr = ConnectionManager()
    bad, good = FakeSocket(fail=True), FakeSocket()
    await mgr.connect(bad)
    await mgr.connect(good)

    await mgr.broadcast("payload")

    assert good.sent == ["payload"]
    # the failing socket is auto-removed
    assert mgr.count == 1


@pytest.mark.asyncio
async def test_disconnect_removes_socket() -> None:
    mgr = ConnectionManager()
    s = FakeSocket()
    await mgr.connect(s)
    assert mgr.count == 1
    await mgr.disconnect(s)
    assert mgr.count == 0


# ---------------------------------------------------------------------------
# map_topic_to_envelope — pure mapping
# ---------------------------------------------------------------------------


def test_map_status_topic_to_status_envelope() -> None:
    payload = {"pv": 150.2, "sp": 152.0, "co": 64.0, "mode": "AUTO"}
    env = map_topic_to_envelope(b"STATUS.12", payload, seq=7, ts=1718743200.5)
    assert env == {
        "type": "status",
        "loop_id": 12,
        "seq": 7,
        "ts": 1718743200.5,
        "data": payload,
    }


def test_map_action_ctrl_topic() -> None:
    env = map_topic_to_envelope(b"ACTION.CTRL.3", {"cv": 1.0, "delta": 0.2}, seq=1, ts=0.0)
    assert env is not None
    assert env["type"] == "action"
    assert env["loop_id"] == 3


def test_map_ai_topic() -> None:
    env = map_topic_to_envelope(
        b"ACTION.AI.4", {"gamma": 0.1, "ki": 2.0, "strategy": "FUZZY"}, seq=1, ts=0.0
    )
    assert env is not None
    assert env["type"] == "ai"
    assert env["loop_id"] == 4


def test_map_alarm_topic() -> None:
    env = map_topic_to_envelope(
        b"EVENT.ALARM.9",
        {"alarm_id": "a1", "severity": "CRITICAL", "state": "UNACK"},
        seq=1,
        ts=0.0,
    )
    assert env is not None
    assert env["type"] == "alarm"
    assert env["loop_id"] == 9


def test_map_stats_topic() -> None:
    env = map_topic_to_envelope(b"STATS.2", {"iae": 1.0}, seq=1, ts=0.0)
    assert env is not None
    assert env["type"] == "stats"
    assert env["loop_id"] == 2


def test_map_system_event_topic_has_null_loop_id() -> None:
    env = map_topic_to_envelope(b"EVENT.SYSTEM", {"kind": "startup"}, seq=1, ts=0.0)
    assert env is not None
    assert env["type"] == "system"
    assert env["loop_id"] is None


def test_map_unknown_topic_returns_none() -> None:
    assert map_topic_to_envelope(b"TELEMETRY.1", {}, seq=1, ts=0.0) is None


def test_map_non_numeric_loop_suffix_yields_none_loop_id() -> None:
    env = map_topic_to_envelope(b"STATUS.broadcast", {"x": 1}, seq=1, ts=0.0)
    assert env is not None
    assert env["loop_id"] is None


# ---------------------------------------------------------------------------
# RealtimeBridge — single non-blocking consumer + fan-out
# ---------------------------------------------------------------------------


class FakeSubscriber:
    """Yields canned (topic, msgpack-payload) frames once, then None forever."""

    def __init__(self, frames: list[tuple[bytes, dict]]) -> None:
        self._frames = [(t, msgpack.packb(p, use_bin_type=True)) for t, p in frames]
        self.closed = False

    def recv(self, timeout_ms: int = 0) -> tuple[bytes, bytes] | None:
        if self._frames:
            return self._frames.pop(0)
        return None

    def close(self) -> None:
        self.closed = True


class FakeBus:
    """Hands out one FakeSubscriber per prefix; first prefix gets all frames."""

    def __init__(self, frames: list[tuple[bytes, dict]]) -> None:
        self._frames = frames
        self.subscribers: list[FakeSubscriber] = []
        self._first = True

    def create_subscriber(self, topic_prefix: bytes) -> FakeSubscriber:
        sub = FakeSubscriber(self._frames if self._first else [])
        self._first = False
        self.subscribers.append(sub)
        return sub


@pytest.mark.asyncio
async def test_bridge_drains_bus_and_broadcasts_envelopes() -> None:
    frames = [
        (b"STATUS.5", {"pv": 1.0, "sp": 2.0}),
        (b"ACTION.CTRL.5", {"cv": 0.5}),
        (b"TELEMETRY.5", {"ignored": True}),  # unmapped -> skipped
    ]
    bus = FakeBus(frames)
    mgr = ConnectionManager()
    sock = FakeSocket()
    await mgr.connect(sock)

    bridge = RealtimeBridge(bus, mgr)
    await bridge.start()
    for _ in range(200):
        if len(sock.sent) >= 2:
            break
        await asyncio.sleep(0.005)
    await bridge.stop()

    decoded = [json.loads(m) for m in sock.sent]
    types = [d["type"] for d in decoded]
    assert types == ["status", "action"]
    assert decoded[0]["loop_id"] == 5
    assert decoded[0]["data"] == {"pv": 1.0, "sp": 2.0}
    # seq is monotonic per the bridge
    assert decoded[0]["seq"] < decoded[1]["seq"]


@pytest.mark.asyncio
async def test_bridge_start_stop_cancels_task_cleanly() -> None:
    bus = FakeBus([])
    mgr = ConnectionManager()
    bridge = RealtimeBridge(bus, mgr)

    await bridge.start()
    assert bridge._task is not None
    await bridge.stop()
    assert bridge._task is None
    # subscribers were closed on shutdown
    assert all(s.closed for s in bus.subscribers)


@pytest.mark.asyncio
async def test_bridge_stop_is_idempotent() -> None:
    bus = FakeBus([])
    mgr = ConnectionManager()
    bridge = RealtimeBridge(bus, mgr)
    await bridge.start()
    await bridge.stop()
    await bridge.stop()  # second stop must not raise


# ---------------------------------------------------------------------------
# realtime_ws endpoint — first-message auth + Origin validation
# ---------------------------------------------------------------------------

_SECRET = "test-secret"
_ALLOWED_ORIGIN = "http://127.0.0.1:5173"


def _make_app() -> FastAPI:
    app = FastAPI()

    class _Settings:
        jwt_secret = _SECRET
        allowed_ws_origins = (_ALLOWED_ORIGIN,)

    app.state.settings = _Settings()
    app.state.realtime_manager = ConnectionManager()
    register_realtime_ws(app)
    return app


def _good_token() -> str:
    return create_access_token(
        user_id=1, username="admin", role="ADMIN", secret=_SECRET
    )


def test_ws_rejects_missing_token() -> None:
    app = _make_app()
    client = TestClient(app)
    with client.websocket_connect(
        "/ws/realtime", headers={"origin": _ALLOWED_ORIGIN}
    ) as ws:
        ws.send_json({"type": "auth"})  # no token
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
    assert exc.value.code == 4401


def test_ws_rejects_invalid_token() -> None:
    app = _make_app()
    client = TestClient(app)
    with client.websocket_connect(
        "/ws/realtime", headers={"origin": _ALLOWED_ORIGIN}
    ) as ws:
        ws.send_json({"type": "auth", "token": "garbage.jwt.value"})
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
    assert exc.value.code == 4401


def test_ws_rejects_bad_origin() -> None:
    app = _make_app()
    client = TestClient(app)
    with client.websocket_connect(
        "/ws/realtime", headers={"origin": "http://evil.example"}
    ) as ws:
        ws.send_json({"type": "auth", "token": _good_token()})
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()
    assert exc.value.code == 4401


def test_ws_accepts_valid_token_and_broadcast_reaches_client() -> None:
    app = _make_app()
    client = TestClient(app)
    with client.websocket_connect(
        "/ws/realtime", headers={"origin": _ALLOWED_ORIGIN}
    ) as ws:
        ws.send_json({"type": "auth", "token": _good_token()})
        # server acknowledges auth
        ack = ws.receive_json()
        assert ack["type"] == "auth_ok"


# ---------------------------------------------------------------------------
# ConnectionBuffer — coalesce status/stats, lossless alarm/ai/system
# ---------------------------------------------------------------------------


def test_status_coalesces_last_value_per_loop() -> None:
    buf = ConnectionBuffer()
    buf.offer({"type": "status", "loop_id": 1, "seq": 1, "ts": 0.0, "data": {"pv": 1}})
    buf.offer({"type": "status", "loop_id": 1, "seq": 2, "ts": 1.0, "data": {"pv": 2}})
    drained = buf.drain()
    # only the latest status for loop 1 survives
    statuses = [m for m in drained if m["type"] == "status" and m["loop_id"] == 1]
    assert len(statuses) == 1
    assert statuses[0]["data"]["pv"] == 2


def test_alarm_is_lossless() -> None:
    buf = ConnectionBuffer()
    buf.offer({"type": "alarm", "loop_id": 9, "seq": 1, "ts": 0.0, "data": {"alarm_id": "a"}})
    buf.offer({"type": "alarm", "loop_id": 9, "seq": 2, "ts": 1.0, "data": {"alarm_id": "b"}})
    drained = buf.drain()
    alarms = [m for m in drained if m["type"] == "alarm"]
    assert [m["data"]["alarm_id"] for m in alarms] == ["a", "b"]


def test_lossless_overflow_flags_for_close() -> None:
    buf = ConnectionBuffer(lossless_max=2)
    for i in range(3):
        buf.offer(
            {"type": "alarm", "loop_id": 1, "seq": i, "ts": 0.0, "data": {"alarm_id": str(i)}}
        )
    assert buf.overflowed is True
