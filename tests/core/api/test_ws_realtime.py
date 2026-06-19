"""Tests for the RealtimeWS bridge."""
from __future__ import annotations

import asyncio
import json

import msgpack
import pytest

from smart_pid_core.adapters.inbound.api.ws.realtime import (
    ConnectionManager,
    RealtimeBridge,
    map_topic_to_envelope,
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
