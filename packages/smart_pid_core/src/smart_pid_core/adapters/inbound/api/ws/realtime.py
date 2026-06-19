"""RealtimeWS bridge: 2nd EventBus consumer + WebSocket fan-out.

Mirrors the threading/loop model of ``application/telemetry_publisher.py``:
a single asyncio.Task drains the in-process ZMQ bus via
``run_in_executor(None, sub.recv, 10)`` (poll-gated blocking recv offloaded to
a thread) and fans each message out to every connected socket. NEVER a
recv-loop per client and NEVER concurrent recv on the same socket.
"""
from __future__ import annotations

import asyncio
from typing import Protocol


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
