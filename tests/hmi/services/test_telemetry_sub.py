"""Tests for ZMQ SUB telemetry subscriber thread."""
import time

import msgpack
import zmq

from smart_pid_hmi.services.telemetry_sub import TelemetrySub


def test_receives_telemetry_frame():
    """Start a real ZMQ PUB, send a frame, verify subscriber enqueues it."""
    ctx = zmq.Context()
    pub = ctx.socket(zmq.PUB)
    pub.bind("tcp://127.0.0.1:15555")

    try:
        sub = TelemetrySub(zmq_url="tcp://127.0.0.1:15555")
        sub.start()
        time.sleep(0.15)  # let SUB connect and subscribe

        frame_data = {
            "controller_id": 1, "pv": 45.0, "sp": 50.0,
            "co": 62.0, "integral_val": 0.5,
            "timestamp": "2026-04-03T10:00:00", "status": "GOOD",
        }
        topic = b"STATUS.1"
        pub.send_multipart([topic, msgpack.packb(frame_data)])
        time.sleep(0.1)

        assert not sub.queue.empty()
        msg_topic, msg_data = sub.queue.get_nowait()
        assert msg_topic == "STATUS.1"
        assert msg_data["pv"] == 45.0
        assert msg_data["controller_id"] == 1

        sub.stop()
    finally:
        pub.close()
        ctx.term()


def test_stop_cleanly():
    sub = TelemetrySub(zmq_url="tcp://127.0.0.1:15556")
    sub.start()
    time.sleep(0.1)
    sub.stop()
    assert not sub._thread.is_alive()


def test_queue_property():
    sub = TelemetrySub(zmq_url="tcp://127.0.0.1:15557")
    assert sub.queue is not None
    assert sub.queue.empty()
