"""ZeroMQ inproc:// event bus with XPUB/XSUB proxy for many-to-many messaging."""
from __future__ import annotations
import threading
import zmq


class BusPublisher:
    """Wrapper around a ZMQ PUB socket connected to the bus."""
    def __init__(self, socket: zmq.Socket[bytes]) -> None:
        self._socket = socket

    def send(self, topic: bytes, payload: bytes) -> None:
        self._socket.send_multipart([topic, payload])


class BusSubscriber:
    """Wrapper around a ZMQ SUB socket connected to the bus."""
    def __init__(self, socket: zmq.Socket[bytes]) -> None:
        self._socket = socket

    def recv(self, timeout_ms: int = 0) -> tuple[bytes, bytes] | None:
        if self._socket.poll(timeout=timeout_ms):
            parts = self._socket.recv_multipart()
            if len(parts) == 2:
                return (parts[0], parts[1])
        return None


class EventBus:
    """XPUB/XSUB proxy running in a daemon thread.

    Publishers connect to the XSUB frontend.
    Subscribers connect to the XPUB backend.
    The proxy relays messages between them.
    """
    def __init__(self, url_prefix: str = "inproc://smartpid") -> None:
        self._ctx = zmq.Context()
        self._url_frontend = f"{url_prefix}_xsub"
        self._url_backend = f"{url_prefix}_xpub"
        self._proxy_thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._xsub = self._ctx.socket(zmq.XSUB)
        self._xsub.setsockopt(zmq.LINGER, 0)
        self._xsub.bind(self._url_frontend)
        self._xpub = self._ctx.socket(zmq.XPUB)
        self._xpub.setsockopt(zmq.LINGER, 0)
        self._xpub.bind(self._url_backend)
        self._running = True
        self._proxy_thread = threading.Thread(
            target=self._run_proxy, daemon=True, name="zmq-proxy",
        )
        self._proxy_thread.start()

    def _run_proxy(self) -> None:
        try:
            zmq.proxy(self._xsub, self._xpub)
        except (zmq.ContextTerminated, zmq.ZMQError):
            pass

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._ctx.destroy(linger=0)

    def create_publisher(self) -> BusPublisher:
        socket = self._ctx.socket(zmq.PUB)
        socket.setsockopt(zmq.LINGER, 0)
        socket.connect(self._url_frontend)
        return BusPublisher(socket)

    def create_subscriber(self, topic_prefix: bytes) -> BusSubscriber:
        socket = self._ctx.socket(zmq.SUB)
        socket.setsockopt(zmq.LINGER, 0)
        socket.connect(self._url_backend)
        socket.subscribe(topic_prefix)
        return BusSubscriber(socket)
