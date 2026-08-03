"""Tests for SystemEventWorker."""
from __future__ import annotations

from unittest.mock import MagicMock

from smart_pid_core.application.workers.system_event_worker import SystemEventWorker


def test_emit_publishes_to_bus():
    """emit() should publish EVENT.SYSTEM on the bus."""
    bus = MagicMock()
    pub = MagicMock()
    bus.create_publisher.return_value = pub
    worker = SystemEventWorker(bus=bus)

    worker.emit("BACKEND", "INFO", "Backend started")

    pub.send.assert_called_once()
    args = pub.send.call_args
    assert args[0][0] == b"EVENT.SYSTEM"
    # Second arg is msgpack payload
    import msgpack
    data = msgpack.unpackb(args[0][1])
    assert data["source"] == "BACKEND"
    assert data["severity"] == "INFO"
    assert data["message"] == "Backend started"
    assert "timestamp" in data


def test_emit_schedules_persistence():
    """emit() should schedule async persistence when repo is available."""
    import asyncio
    bus = MagicMock()
    bus.create_publisher.return_value = MagicMock()
    repo = MagicMock()
    loop = MagicMock(spec=asyncio.AbstractEventLoop)

    worker = SystemEventWorker(bus=bus, system_event_repo=repo, event_loop=loop)
    worker.emit("OPCUA", "WARNING", "Connection lost")

    loop.call_soon_threadsafe.assert_called_once()


def test_emit_no_repo_no_error():
    """emit() without repo should not raise."""
    bus = MagicMock()
    bus.create_publisher.return_value = MagicMock()
    worker = SystemEventWorker(bus=bus)

    # Should not raise
    worker.emit("BACKEND", "INFO", "Started")


def test_emit_uses_the_callers_publisher_when_given_one():
    """ZeroMQ sockets belong to the thread that created them.

    The per-loop AI workers emit from their own threads; sharing this
    object's publisher with them is undefined behaviour and silently
    dropped every optimizer suggestion event.
    """
    from unittest.mock import MagicMock

    from smart_pid_core.application.workers.system_event_worker import SystemEventWorker

    bus = MagicMock()
    own_pub = MagicMock()
    bus.create_publisher.return_value = own_pub
    worker = SystemEventWorker(bus=bus)

    caller_pub = MagicMock()
    worker.emit("AI", "LOG", "sintonia sugerida", pub=caller_pub)

    caller_pub.send.assert_called_once()
    own_pub.send.assert_not_called()


def test_emit_falls_back_to_its_own_publisher():
    from unittest.mock import MagicMock

    from smart_pid_core.application.workers.system_event_worker import SystemEventWorker

    bus = MagicMock()
    own_pub = MagicMock()
    bus.create_publisher.return_value = own_pub
    SystemEventWorker(bus=bus).emit("USER", "INFO", "mode changed")

    own_pub.send.assert_called_once()
