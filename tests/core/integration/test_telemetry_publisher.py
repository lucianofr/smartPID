"""Tests for TelemetryPublisher — bridge from inproc EventBus to tcp ZMQ PUB."""
from __future__ import annotations

import asyncio
import time

import msgpack
import pytest
import zmq
import zmq.asyncio

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.telemetry_publisher import TelemetryPublisher


class TestTelemetryPublisher:
    @pytest.mark.asyncio
    async def test_republishes_status_topic(self) -> None:
        bus = EventBus()
        bus.start()
        time.sleep(0.1)

        publisher = TelemetryPublisher(bus=bus, publish_port=15555)
        await publisher.start()
        await asyncio.sleep(0.2)  # Let publisher task subscribe to internal bus

        # External SUB socket (simulates HMI client)
        ctx = zmq.asyncio.Context()
        sub = ctx.socket(zmq.SUB)
        sub.connect("tcp://127.0.0.1:15555")
        sub.subscribe(b"STATUS.")
        await asyncio.sleep(0.2)  # Allow subscription to propagate

        # Publish on internal bus — send multiple times to overcome slow joiner
        internal_pub = bus.create_publisher()
        time.sleep(0.05)
        payload = msgpack.packb({"controller_id": 1, "pv": 50.0, "sp": 50.0})
        for _ in range(5):
            internal_pub.send(b"STATUS.1", payload)
            await asyncio.sleep(0.05)

        # Receive on external socket
        if await sub.poll(timeout=3000):
            parts = await sub.recv_multipart()
            assert parts[0] == b"STATUS.1"
            data = msgpack.unpackb(parts[1])
            assert data["pv"] == 50.0
        else:
            pytest.fail("Did not receive republished message within timeout")

        await publisher.stop()
        sub.close()
        ctx.term()
        bus.stop()

    @pytest.mark.asyncio
    async def test_republishes_action_topic(self) -> None:
        bus = EventBus()
        bus.start()
        time.sleep(0.1)

        publisher = TelemetryPublisher(bus=bus, publish_port=15556)
        await publisher.start()
        await asyncio.sleep(0.2)

        ctx = zmq.asyncio.Context()
        sub = ctx.socket(zmq.SUB)
        sub.connect("tcp://127.0.0.1:15556")
        sub.subscribe(b"ACTION.CTRL.")
        await asyncio.sleep(0.2)

        internal_pub = bus.create_publisher()
        time.sleep(0.05)
        payload = msgpack.packb({"controller_id": 1, "co": 75.0})
        for _ in range(5):
            internal_pub.send(b"ACTION.CTRL.1", payload)
            await asyncio.sleep(0.05)

        if await sub.poll(timeout=3000):
            parts = await sub.recv_multipart()
            assert parts[0] == b"ACTION.CTRL.1"
            data = msgpack.unpackb(parts[1])
            assert data["co"] == 75.0
        else:
            pytest.fail("Did not receive republished action within timeout")

        await publisher.stop()
        sub.close()
        ctx.term()
        bus.stop()

    @pytest.mark.asyncio
    async def test_stop_is_clean(self) -> None:
        bus = EventBus()
        bus.start()
        time.sleep(0.05)

        publisher = TelemetryPublisher(bus=bus, publish_port=15557)
        await publisher.start()
        await publisher.stop()
        bus.stop()
        # No assertion — just verifying no hang or exception
