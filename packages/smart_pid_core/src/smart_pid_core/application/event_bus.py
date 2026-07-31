"""ZeroMQ inproc:// event bus with XPUB/XSUB proxy for many-to-many messaging."""
from __future__ import annotations

import contextlib
import threading

import zmq

#: Proxy poll slice. Bounds how long stop() waits for the forwarder to notice
#: the stop flag; small enough to be imperceptible, large enough that an idle
#: bus costs ~20 wakeups/s.
_PROXY_POLL_MS = 50

#: How long start() waits for the proxy thread to finish binding.
_BIND_TIMEOUT_S = 5.0

#: How long stop() waits for the forwarder to exit and close its sockets.
_PROXY_JOIN_TIMEOUT_S = 5.0


def _forward(src: zmq.Socket[bytes], dst: zmq.Socket[bytes]) -> None:
    """Drain every queued multipart message from *src* into *dst*.

    Draining per poll rather than one message per poll keeps the Python-level
    forwarder's per-message cost near the C proxy's on bursty telemetry.
    """
    while True:
        try:
            dst.send_multipart(src.recv_multipart(zmq.NOBLOCK))
        except zmq.Again:
            return


class BusPublisher:
    """Wrapper around a ZMQ PUB socket connected to the bus."""
    def __init__(self, socket: zmq.Socket[bytes]) -> None:
        self._socket = socket

    def send(self, topic: bytes, payload: bytes) -> None:
        self._socket.send_multipart([topic, payload])

    def close(self) -> None:
        """Close the underlying ZMQ socket."""
        with contextlib.suppress(zmq.ZMQError):
            self._socket.setsockopt(zmq.LINGER, 0)
            self._socket.close()


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

    def close(self) -> None:
        """Close the underlying ZMQ socket."""
        with contextlib.suppress(zmq.ZMQError):
            self._socket.setsockopt(zmq.LINGER, 0)
            self._socket.close()


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
        self._stop_event = threading.Event()
        self._bound = threading.Event()
        self._bind_ok = False

    def start(self) -> None:
        if self._running:
            return
        self._stop_event.clear()
        self._bound.clear()
        self._bind_ok = False
        self._running = True
        self._proxy_thread = threading.Thread(
            target=self._run_proxy, daemon=True, name="zmq-proxy",
        )
        self._proxy_thread.start()
        # Callers connect publishers/subscribers straight after start()
        # returns, so the bind has to have happened by then.
        self._bound.wait(timeout=_BIND_TIMEOUT_S)
        if not self._bind_ok:
            self._running = False
            raise RuntimeError("event bus proxy failed to bind")

    def _run_proxy(self) -> None:
        """Forward XSUB<->XPUB until stopped.

        The proxy sockets are created, polled and closed entirely inside this
        thread. ZMQ sockets are not thread-safe: the previous version bound
        them in the caller's thread and let ``stop()`` close them while this
        thread sat inside ``zmq.proxy()``, which intermittently deadlocked
        ``zmq_ctx_term()`` or aborted the interpreter outright.
        ``zmq.proxy()`` cannot be used here because it only returns once the
        context is terminated — the very call that was hanging.
        """
        xsub = self._ctx.socket(zmq.XSUB)
        xsub.setsockopt(zmq.LINGER, 0)
        xpub = self._ctx.socket(zmq.XPUB)
        xpub.setsockopt(zmq.LINGER, 0)
        try:
            xsub.bind(self._url_frontend)
            xpub.bind(self._url_backend)
            self._bind_ok = True
            self._bound.set()
            poller = zmq.Poller()
            poller.register(xsub, zmq.POLLIN)
            poller.register(xpub, zmq.POLLIN)
            while not self._stop_event.is_set():
                events = dict(poller.poll(timeout=_PROXY_POLL_MS))
                if xsub in events:
                    _forward(xsub, xpub)
                if xpub in events:
                    # Subscribe/unsubscribe frames travel back upstream.
                    _forward(xpub, xsub)
        except zmq.ZMQError:
            pass
        finally:
            # Unblock a start() still waiting on a bind that never happened.
            self._bound.set()
            for sock in (xsub, xpub):
                with contextlib.suppress(zmq.ZMQError):
                    sock.close()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        if self._proxy_thread is not None:
            # Join before destroying the context: the thread closes its own
            # sockets on the way out, so destroy() is left with nothing to
            # reach across threads for.
            self._proxy_thread.join(timeout=_PROXY_JOIN_TIMEOUT_S)
            self._proxy_thread = None
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
