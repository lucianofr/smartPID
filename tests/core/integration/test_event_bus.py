from __future__ import annotations
import threading
import time
import msgpack
import pytest
from smart_pid_core.application.event_bus import EventBus


class TestEventBus:
    def test_publish_and_receive(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"TEST")
            time.sleep(0.05)
            pub.send(b"TEST.hello", b"world")
            msg = sub.recv(timeout_ms=1000)
            assert msg is not None
            topic, payload = msg
            assert topic == b"TEST.hello"
            assert payload == b"world"
        finally:
            bus.stop()

    def test_subscriber_filters_by_prefix(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"TELEM")
            time.sleep(0.05)
            pub.send(b"ALARM.fire", b"alarm_data")
            pub.send(b"TELEM.1", b"telem_data")
            msg = sub.recv(timeout_ms=1000)
            assert msg is not None
            assert msg[0] == b"TELEM.1"
            msg2 = sub.recv(timeout_ms=100)
            assert msg2 is None
        finally:
            bus.stop()

    def test_multiple_subscribers(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            pub = bus.create_publisher()
            sub1 = bus.create_subscriber(b"DATA")
            sub2 = bus.create_subscriber(b"DATA")
            time.sleep(0.05)
            pub.send(b"DATA.x", b"payload")
            msg1 = sub1.recv(timeout_ms=1000)
            msg2 = sub2.recv(timeout_ms=1000)
            assert msg1 is not None
            assert msg2 is not None
            assert msg1[1] == msg2[1] == b"payload"
        finally:
            bus.stop()

    def test_noblock_returns_none_when_empty(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            sub = bus.create_subscriber(b"EMPTY")
            time.sleep(0.05)
            msg = sub.recv(timeout_ms=50)
            assert msg is None
        finally:
            bus.stop()

    def test_cross_thread_communication(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            sub = bus.create_subscriber(b"THREAD")
            time.sleep(0.05)

            def publisher_thread() -> None:
                pub = bus.create_publisher()
                time.sleep(0.02)
                pub.send(b"THREAD.test", b"from_thread")

            t = threading.Thread(target=publisher_thread)
            t.start()
            msg = sub.recv(timeout_ms=2000)
            assert msg is not None
            assert msg[1] == b"from_thread"
            t.join(timeout=2.0)
        finally:
            bus.stop()

    def test_msgpack_round_trip(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"MP")
            time.sleep(0.05)
            data = {"pv": 50.5, "sp": 50.0, "co": 25.0}
            pub.send(b"MP.telem", msgpack.packb(data))
            msg = sub.recv(timeout_ms=1000)
            assert msg is not None
            decoded = msgpack.unpackb(msg[1])
            assert decoded["pv"] == 50.5
        finally:
            bus.stop()
