"""ZMQ SUB daemon thread — receives telemetry and enqueues into SimpleQueue."""
from __future__ import annotations

import threading
from queue import SimpleQueue

import msgpack
import zmq

# Topics to subscribe to
_SUBSCRIBE_TOPICS = [b"STATUS.", b"ACTION.CTRL.", b"ACTION.AI."]


class TelemetrySub:
    """Background thread that receives ZMQ multipart [topic, msgpack_payload]."""

    def __init__(self, zmq_url: str = "tcp://localhost:5555") -> None:
        self._zmq_url = zmq_url
        self._queue: SimpleQueue = SimpleQueue()
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    @property
    def queue(self) -> SimpleQueue:
        return self._queue

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        ctx = zmq.Context()
        socket = ctx.socket(zmq.SUB)
        socket.setsockopt(zmq.RCVTIMEO, 100)  # 100ms poll
        socket.setsockopt(zmq.LINGER, 0)

        for topic in _SUBSCRIBE_TOPICS:
            socket.subscribe(topic)

        socket.connect(self._zmq_url)

        try:
            while not self._stop_event.is_set():
                try:
                    parts = socket.recv_multipart()
                    if len(parts) == 2:
                        topic_str = parts[0].decode("utf-8", errors="replace")
                        data = msgpack.unpackb(parts[1], raw=False)
                        self._queue.put((topic_str, data))
                except zmq.Again:
                    continue
        finally:
            socket.close()
            ctx.term()
