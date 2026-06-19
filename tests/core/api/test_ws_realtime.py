"""Tests for the RealtimeWS bridge."""
from __future__ import annotations

import json

import pytest

from smart_pid_core.adapters.inbound.api.ws.realtime import ConnectionManager


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
