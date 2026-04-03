"""OPC-UA adapter implementing TelemetrySource + ControlWriter + TagBrowser."""
from __future__ import annotations

import asyncio
import logging
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from smart_pid_domain.enums import ConnectionState
from smart_pid_domain.models.telemetry import TelemetryFrame

if TYPE_CHECKING:
    from smart_pid_core.config import CoreSettings

logger = logging.getLogger(__name__)


class OPCUAAdapter:
    """OPC-UA client adapter for real process I/O.

    Implements TelemetrySource, ControlWriter, and TagBrowser protocols.
    Runs asyncua.Client in a daemon thread with a dedicated asyncio event loop.
    """

    # Backoff constants
    _BACKOFF_BASE_S = 1.0
    _BACKOFF_MAX_S = 60.0

    def __init__(self, settings: CoreSettings) -> None:
        self._settings = settings
        self._endpoint = settings.opcua_endpoint
        self._timeout_s = settings.opcua_timeout_s
        self._state = ConnectionState.OFFLINE
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._client = None  # asyncua.Client, lazily created
        self._controllers: dict[int, dict[str, str]] = {}  # id -> {pv: node_id, ...}

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def state(self) -> ConnectionState:
        with self._lock:
            return self._state

    @property
    def is_connected(self) -> bool:
        return self.state == ConnectionState.ONLINE
