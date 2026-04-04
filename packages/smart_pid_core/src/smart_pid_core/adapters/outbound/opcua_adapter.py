"""OPC-UA adapter implementing TelemetrySource + ControlWriter + TagBrowser."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from smart_pid_domain.enums import ConnectionState
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus
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

    def __init__(self, settings: CoreSettings) -> None:
        self._settings = settings
        self._endpoint = settings.opcua_endpoint
        self._timeout_s = settings.opcua_timeout_s
        self._backoff_max_s = settings.opcua_retry_max_s
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

    def start(self) -> None:
        """Start the OPC-UA client in a background daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_event_loop, daemon=True, name="opcua-client",
        )
        self._thread.start()
        logger.info("opcua_adapter_started endpoint=%s", self._endpoint)

    def stop(self) -> None:
        """Stop the client and disconnect."""
        self._stop_event.set()
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        with self._lock:
            self._state = ConnectionState.OFFLINE
        self._client = None
        logger.info("opcua_adapter_stopped")

    def wait_connected(self, timeout_s: float = 10.0) -> bool:
        """Block until ONLINE or timeout. Returns True if connected."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.state == ConnectionState.ONLINE:
                return True
            time.sleep(0.05)
        return False

    @staticmethod
    def _decode_status(status_code: int) -> FFSignalStatus:
        """Decode OPC-UA StatusCode into FFSignalStatus."""
        from smart_pid_domain.enums import LimitBits, SignalSeverity
        from smart_pid_domain.models.signal import FFSignalStatus as _FSS

        severity_bits = (status_code & 0xC0000000) >> 30
        severity_map = {0: SignalSeverity.GOOD, 1: SignalSeverity.UNCERTAIN}
        severity = severity_map.get(severity_bits, SignalSeverity.BAD)

        limit_val = (status_code & 0x00000300) >> 8
        limit_map = {
            0: LimitBits.NONE, 1: LimitBits.LOW_LIMITED,
            2: LimitBits.HIGH_LIMITED, 3: LimitBits.CONSTANT,
        }
        limit_bits = limit_map.get(limit_val, LimitBits.NONE)

        return _FSS(severity=severity, limit_bits=limit_bits)

    @staticmethod
    def _encode_status(status: FFSignalStatus) -> int:
        """Encode FFSignalStatus into OPC-UA StatusCode integer."""
        from smart_pid_domain.enums import LimitBits, SignalSeverity

        severity_map = {
            SignalSeverity.GOOD: 0, SignalSeverity.UNCERTAIN: 1, SignalSeverity.BAD: 2,
        }
        limit_map = {
            LimitBits.NONE: 0, LimitBits.LOW_LIMITED: 1,
            LimitBits.HIGH_LIMITED: 2, LimitBits.CONSTANT: 3,
        }
        return (severity_map.get(status.severity, 2) << 30) | (
            limit_map.get(status.limit_bits, 0) << 8
        )

    # ---- Connection lifecycle (private) ----

    def _run_event_loop(self) -> None:
        """Run the asyncio event loop for OPC-UA operations."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connection_loop())
        except Exception:
            logger.exception("opcua_event_loop_error")
        finally:
            self._loop.close()
            self._loop = None

    async def _connection_loop(self) -> None:
        """Main async loop: connect, maintain, reconnect with backoff."""
        from asyncua import Client

        backoff_s = self._BACKOFF_BASE_S
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    self._state = ConnectionState.CONNECTING
                self._client = Client(url=self._endpoint, timeout=self._timeout_s)
                await self._client.connect()
                with self._lock:
                    self._state = ConnectionState.ONLINE
                backoff_s = self._BACKOFF_BASE_S
                logger.info("opcua_connected endpoint=%s", self._endpoint)

                # Watchdog loop
                await self._watchdog_loop()

            except Exception as exc:
                logger.warning(
                    "opcua_connection_failed error=%s backoff=%s", str(exc), backoff_s,
                )
                with self._lock:
                    self._state = ConnectionState.RECONNECTING
                if self._client is not None:
                    with contextlib.suppress(Exception):
                        await self._client.disconnect()
                    self._client = None

                # Backoff wait
                for _ in range(int(backoff_s * 10)):
                    if self._stop_event.is_set():
                        return
                    await asyncio.sleep(0.1)
                backoff_s = min(backoff_s * 2, self._backoff_max_s)

    async def _watchdog_loop(self) -> None:
        """Periodically read ServerStatus to detect connection loss."""
        from asyncua import ua

        while not self._stop_event.is_set():
            try:
                node = self._client.get_node(ua.ObjectIds.Server_ServerStatus_State)
                await node.read_value()
                # Wait 5s between heartbeats
                for _ in range(50):
                    if self._stop_event.is_set():
                        return
                    await asyncio.sleep(0.1)
            except Exception as exc:
                logger.warning("opcua_watchdog_failed error=%s", str(exc))
                raise  # Triggers reconnect in _connection_loop

    # ---- TelemetrySource ----

    def register_controller(
        self,
        controller_id: int,
        node_id_pv: str,
        node_id_sp: str,
        node_id_co: str,
        node_id_integral: str = "",
        node_id_bkcal_in: str = "",
        node_id_bkcal_out: str = "",
    ) -> None:
        """Register a controller's OPC-UA node mappings."""
        with self._lock:
            self._controllers[controller_id] = {
                "pv": node_id_pv,
                "sp": node_id_sp,
                "co": node_id_co,
                "integral": node_id_integral,
                "bkcal_in": node_id_bkcal_in,
                "bkcal_out": node_id_bkcal_out,
            }

    def read_telemetry(self, controller_id: int) -> TelemetryFrame:
        """Read current PV/SP/CO from OPC-UA via batch read. Thread-safe."""
        with self._lock:
            if controller_id not in self._controllers:
                raise KeyError(f"Controller {controller_id} not registered")
            nodes = self._controllers[controller_id].copy()
            client = self._client

        if client is None or self.state != ConnectionState.ONLINE:
            raise ConnectionError("OPC-UA not connected")

        # Schedule async read on the adapter's event loop
        future = asyncio.run_coroutine_threadsafe(
            self._async_read_telemetry(client, controller_id, nodes),
            self._loop,
        )
        return future.result(timeout=self._timeout_s)

    async def _async_read_telemetry(
        self, client, controller_id: int, nodes: dict[str, str],
    ) -> TelemetryFrame:
        """Async batch read of OPC-UA nodes."""
        node_ids_to_read = []
        keys = []
        for key in ("pv", "sp", "co", "bkcal_in"):
            nid = nodes.get(key, "")
            if nid:
                node_ids_to_read.append(client.get_node(nid))
                keys.append(key)

        # Integral node is optional
        integral_nid = nodes.get("integral", "")
        if integral_nid:
            node_ids_to_read.append(client.get_node(integral_nid))
            keys.append("integral")

        values = await client.read_values(node_ids_to_read)
        result = dict(zip(keys, values, strict=True))

        now = datetime.now(UTC)
        return TelemetryFrame(
            controller_id=controller_id,
            pv=FFSignal.good(float(result.get("pv", 0.0)), now),
            sp=FFSignal.good(float(result.get("sp", 0.0)), now),
            co=FFSignal.good(float(result.get("co", 0.0)), now),
            bkcal_in=FFSignal.good(float(result.get("bkcal_in", 0.0)), now),
            integral_val=float(result.get("integral", 0.0)),
            timestamp=now,
        )

    # ---- ControlWriter ----

    def write_output(self, controller_id: int, co: float) -> None:
        """Write CO value to the controller's output node."""
        with self._lock:
            if controller_id not in self._controllers:
                raise KeyError(f"Controller {controller_id} not registered")
            node_id = self._controllers[controller_id]["co"]
            client = self._client

        if client is None or self.state != ConnectionState.ONLINE:
            raise ConnectionError("OPC-UA not connected")

        future = asyncio.run_coroutine_threadsafe(
            self._async_write_value(client, node_id, co),
            self._loop,
        )
        future.result(timeout=self._timeout_s)

    def write_parameter(self, controller_id: int, param: str, value: float) -> None:
        """Write an arbitrary parameter (sp, pv, co) to the corresponding node."""
        with self._lock:
            if controller_id not in self._controllers:
                raise KeyError(f"Controller {controller_id} not registered")
            node_id = self._controllers[controller_id].get(param, "")
            client = self._client

        if not node_id:
            raise ValueError(f"No node mapping for parameter '{param}'")
        if client is None or self.state != ConnectionState.ONLINE:
            raise ConnectionError("OPC-UA not connected")

        future = asyncio.run_coroutine_threadsafe(
            self._async_write_value(client, node_id, value),
            self._loop,
        )
        future.result(timeout=self._timeout_s)

    def write_bkcal_out(self, controller_id: int, signal: FFSignal) -> None:
        """Write BKCAL_OUT value and status to the controller's BKCAL_OUT node."""
        with self._lock:
            if controller_id not in self._controllers:
                raise KeyError(f"Controller {controller_id} not registered")
            node_id = self._controllers[controller_id].get("bkcal_out", "")
            client = self._client

        if not node_id:
            return  # No BKCAL_OUT node configured — skip silently
        if client is None or self.state != ConnectionState.ONLINE:
            raise ConnectionError("OPC-UA not connected")

        future = asyncio.run_coroutine_threadsafe(
            self._async_write_bkcal_out(client, node_id, signal),
            self._loop,
        )
        future.result(timeout=self._timeout_s)

    async def _async_write_bkcal_out(
        self, client, node_id: str, signal: FFSignal,
    ) -> None:
        """Write BKCAL_OUT with encoded StatusCode."""
        from asyncua import ua

        node = client.get_node(node_id)
        status_code = ua.StatusCode(self._encode_status(signal.status))
        dv = ua.DataValue(
            Value=ua.Variant(signal.value, ua.VariantType.Float),
            StatusCode=status_code,
            SourceTimestamp=signal.timestamp or datetime.now(UTC),
        )
        await node.write_data_value(dv)

    async def _async_write_value(self, client, node_id: str, value: float) -> None:
        """Write a float value to an OPC-UA node."""
        from asyncua import ua

        node = client.get_node(node_id)
        dv = ua.DataValue(ua.Variant(value, ua.VariantType.Float))
        await node.write_value(dv)

    # ---- TagBrowser ----

    def browse_children(self, node_id: str) -> list[dict[str, str]]:
        """List children of an OPC-UA node. Returns list of dicts."""
        if self._client is None or self.state != ConnectionState.ONLINE:
            raise ConnectionError("OPC-UA not connected")

        future = asyncio.run_coroutine_threadsafe(
            self._async_browse_children(self._client, node_id),
            self._loop,
        )
        return future.result(timeout=self._timeout_s)

    def search(self, query: str) -> list[dict[str, str]]:
        """Search OPC-UA address space by DisplayName. Recursive from Objects folder."""
        if self._client is None or self.state != ConnectionState.ONLINE:
            raise ConnectionError("OPC-UA not connected")

        future = asyncio.run_coroutine_threadsafe(
            self._async_search(self._client, query),
            self._loop,
        )
        return future.result(timeout=self._timeout_s)

    async def _async_browse_children(
        self, client, node_id: str,
    ) -> list[dict[str, str]]:
        """Browse children of a node asynchronously."""
        node = client.get_node(node_id)
        children = await node.get_children()
        result = []
        for child in children:
            display_name = (await child.read_display_name()).Text
            node_class = await child.read_node_class()
            result.append({
                "node_id": child.nodeid.to_string(),
                "display_name": display_name,
                "node_class": node_class.name,
            })
        return result

    async def _async_search(self, client, query: str) -> list[dict[str, str]]:
        """Recursively search address space under Objects for matching DisplayName."""
        from asyncua import ua

        results: list[dict[str, str]] = []
        query_lower = query.lower()

        async def _walk(node, depth: int = 0) -> None:
            if depth > 5:  # Limit recursion
                return
            children = await node.get_children()
            for child in children:
                display_name = (await child.read_display_name()).Text
                node_class = await child.read_node_class()
                if query_lower in display_name.lower():
                    results.append({
                        "node_id": child.nodeid.to_string(),
                        "display_name": display_name,
                        "node_class": node_class.name,
                    })
                # Recurse into folders/objects
                if node_class in {ua.NodeClass.Object, ua.NodeClass.ObjectType}:
                    await _walk(child, depth + 1)

        objects = client.get_node(ua.ObjectIds.ObjectsFolder)
        await _walk(objects)
        return results
