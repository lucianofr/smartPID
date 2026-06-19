"""RealtimeWS bridge: 2nd EventBus consumer + WebSocket fan-out.

Mirrors the threading/loop model of ``application/telemetry_publisher.py``:
a single asyncio.Task drains the in-process ZMQ bus via
``run_in_executor(None, sub.recv, 10)`` (poll-gated blocking recv offloaded to
a thread) and fans each message out to every connected socket. NEVER a
recv-loop per client and NEVER concurrent recv on the same socket.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import time
from typing import TYPE_CHECKING, Any, Protocol

import msgpack  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import BusSubscriber, EventBus


class _Sendable(Protocol):
    async def send_text(self, message: str) -> None: ...
    async def close(self, code: int = ...) -> None: ...


class ConnectionManager:
    """Tracks live sockets and broadcasts resiliently under an async lock."""

    def __init__(self) -> None:
        self._conns: set[_Sendable] = set()
        self._lock = asyncio.Lock()

    @property
    def count(self) -> int:
        return len(self._conns)

    async def connect(self, ws: _Sendable) -> None:
        async with self._lock:
            self._conns.add(ws)

    async def disconnect(self, ws: _Sendable) -> None:
        async with self._lock:
            self._conns.discard(ws)

    async def broadcast(self, message: str) -> None:
        async with self._lock:
            targets = list(self._conns)
        dead: list[_Sendable] = []
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:  # noqa: BLE001 — one bad socket must not drop the rest
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._conns.discard(ws)


# Bus prefixes the RealtimeWS subscribes to. STATS is on the internal bus only
# (the legacy tcp://5555 whitelist skips it) but we subscribe to the bus DIRECTLY.
_BRIDGE_TOPICS: list[bytes] = [
    b"STATUS.",
    b"ACTION.CTRL.",
    b"ACTION.AI.",
    b"EVENT.ALARM.",
    b"EVENT.SYSTEM",
    b"STATS.",
]

# Topic prefix -> (envelope type, has_loop_id). Order matters: longer/specific first.
_TOPIC_MAP: list[tuple[bytes, str, bool]] = [
    (b"STATUS.", "status", True),
    (b"ACTION.CTRL.", "action", True),
    (b"ACTION.AI.", "ai", True),
    (b"EVENT.ALARM.", "alarm", True),
    (b"EVENT.SYSTEM", "system", False),
    (b"STATS.", "stats", True),
]


def map_topic_to_envelope(
    topic: bytes, payload: dict[str, Any], *, seq: int, ts: float
) -> dict[str, Any] | None:
    """Map a bus (topic, payload) to the canonical JSON envelope, or None if unmapped.

    Returns ``{type, loop_id, seq, ts, data}``. ``loop_id`` is parsed from the
    numeric topic suffix for loop-scoped types; non-numeric suffixes and the
    loop-less ``EVENT.SYSTEM`` yield ``loop_id=None``. Unknown prefixes return
    ``None`` so the bridge can skip them.
    """
    for prefix, etype, has_id in _TOPIC_MAP:
        if topic.startswith(prefix):
            loop_id: int | None = None
            if has_id:
                suffix = topic[len(prefix):].decode("ascii", "ignore")
                with contextlib.suppress(ValueError):
                    loop_id = int(suffix)
            return {"type": etype, "loop_id": loop_id, "seq": seq, "ts": ts, "data": payload}
    return None


class RealtimeBridge:
    """Single asyncio.Task that drains the EventBus and fans out to ConnectionManager.

    Mirrors ``TelemetryPublisher._run``: one subscriber per prefix, drained via
    ``run_in_executor(None, sub.recv, 10)`` so the blocking poll-gated recv never
    blocks the event loop. ONE consumer total — NOT one recv-loop per client, and
    NEVER concurrent recv on the same socket.
    """

    def __init__(self, bus: EventBus, manager: ConnectionManager) -> None:
        self._bus = bus
        self._manager = manager
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._seq = 0

    async def start(self) -> None:
        self._stop.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        subs: list[BusSubscriber] = [
            self._bus.create_subscriber(t) for t in _BRIDGE_TOPICS
        ]
        try:
            while not self._stop.is_set():
                for sub in subs:
                    result = await loop.run_in_executor(None, sub.recv, 10)
                    if result is None:
                        continue
                    topic_bytes, payload_bytes = result
                    data = msgpack.unpackb(payload_bytes, raw=False)
                    self._seq += 1
                    env = map_topic_to_envelope(
                        topic_bytes, data, seq=self._seq, ts=time.time()
                    )
                    if env is not None:
                        await self._manager.broadcast(json.dumps(env))
                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            raise
        finally:
            for sub in subs:
                sub.close()
