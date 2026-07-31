"""OPC-UA adapter implementing TelemetrySource + ControlWriter + TagBrowser."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from smart_pid_domain.enums import ConnectionState, ControllerMode
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus
from smart_pid_domain.models.telemetry import TelemetryFrame
from smart_pid_domain.models.tuning import PIDParamsRead

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

    # Write verification — after writing tuning/mode, read back the value and
    # retry the write if it didn't take. Guards against DCS write-through
    # failures that leave the setpoint stale without raising.
    _VERIFY_DELAY_S = 1.5
    _VERIFY_MAX_RETRIES = 2
    _VERIFY_FLOAT_REL_TOL = 0.005  # 0.5 % of expected magnitude
    _VERIFY_FLOAT_ABS_TOL = 1e-3   # absolute minimum tolerance

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
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            # Force-stop if graceful shutdown didn't finish
            if self._thread.is_alive() and self._loop is not None:
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._thread.join(timeout=3.0)
            self._thread = None
        with self._lock:
            self._state = ConnectionState.OFFLINE
        self._client = None
        logger.info("opcua_adapter_stopped")

    def set_endpoint(self, url: str) -> None:
        """Stop the adapter and update the endpoint. Does NOT reconnect."""
        self.stop()
        self._endpoint = url

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
        node_id_kp: str = "",
        node_id_ti: str = "",
        node_id_td: str = "",
        node_id_mode_target: str = "",
        node_id_mode_actual: str = "",
        node_id_enabled: str = "",
        mode_int_map: dict[str, int] | None = None,
    ) -> None:
        """Register a controller's OPC-UA node mappings.

        ``node_id_enabled`` points at the PLC boolean that reports whether the
        process this PID drives is actually running — conventionally exposed as
        ``PID_[MALHA]_ENABLED`` (e.g. a ``Process_Running`` tag on a
        ControlLogix, or a ``DB.Process_Running`` bit on an S7). Leave it empty
        when the PLC publishes no such tag; the optimizer then runs ungated.
        """
        int_map = mode_int_map or {}
        inv_map = {v: k for k, v in int_map.items()}
        with self._lock:
            self._controllers[controller_id] = {
                "pv": node_id_pv,
                "sp": node_id_sp,
                "co": node_id_co,
                "integral": node_id_integral,
                "bkcal_in": node_id_bkcal_in,
                "bkcal_out": node_id_bkcal_out,
                "kp": node_id_kp,
                "ti": node_id_ti,
                "td": node_id_td,
                "mode_target": node_id_mode_target,
                "mode_actual": node_id_mode_actual,
                "enabled": node_id_enabled,
                "mode_int_map": int_map,
                "mode_int_map_inv": inv_map,
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
        """Async batch read of OPC-UA DataValues with StatusCode decoding."""
        signal_keys = []
        signal_nodes = []
        for key in ("pv", "sp", "co", "bkcal_in"):
            nid = nodes.get(key, "")
            if nid:
                signal_nodes.append(client.get_node(nid))
                signal_keys.append(key)

        # Read DataValues (value + StatusCode + timestamps) instead of plain values
        signals: dict[str, FFSignal] = {}
        for key, node in zip(signal_keys, signal_nodes, strict=True):
            dv = await node.read_data_value()
            value = float(dv.Value.Value) if dv.Value is not None else 0.0
            status = self._decode_status(dv.StatusCode.value)
            ts = dv.SourceTimestamp or datetime.now(UTC)
            signals[key] = FFSignal(value=value, status=status, timestamp=ts)

        # Integral node is optional — plain value read (no signal semantics)
        integral_val = 0.0
        integral_nid = nodes.get("integral", "")
        if integral_nid:
            integral_node = client.get_node(integral_nid)
            integral_val = float(await integral_node.read_value())

        now = datetime.now(UTC)
        # An unmapped tag is the absence of a measurement, not a measurement of
        # zero. A GOOD 0.0 tells the operator the valve is shut — actionable and
        # wrong; BAD renders as "sem dados" instead of a confident lie.
        default_signal = FFSignal.bad(0.0, now)
        return TelemetryFrame(
            controller_id=controller_id,
            pv=signals.get("pv", default_signal),
            sp=signals.get("sp", default_signal),
            co=signals.get("co", default_signal),
            bkcal_in=signals.get("bkcal_in", default_signal),
            integral_val=integral_val,
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

    async def _async_write_int32(self, client, node_id: str, value: int) -> None:
        """Write an Int32 value to an OPC-UA node."""
        from asyncua import ua

        node = client.get_node(node_id)
        dv = ua.DataValue(ua.Variant(value, ua.VariantType.Int32))
        await node.write_value(dv)

    # ---- Write verification (fire-and-forget retry on mismatch) ----

    async def _async_verify_write_float(
        self, client, node_id: str, expected: float,
    ) -> bool:
        """Read-back a float node after _VERIFY_DELAY_S; retry write on mismatch.

        Fire-and-forget: the caller schedules this on the event loop and does
        not wait. Returns True if the value was confirmed, False if all
        retries were exhausted (or the adapter went offline mid-check).
        """
        tolerance = max(
            self._VERIFY_FLOAT_ABS_TOL, abs(expected) * self._VERIFY_FLOAT_REL_TOL,
        )
        last_actual: float | None = None
        for attempt in range(self._VERIFY_MAX_RETRIES + 1):
            await asyncio.sleep(self._VERIFY_DELAY_S)
            if self.state != ConnectionState.ONLINE:
                logger.warning(
                    "opcua_verify_skipped_disconnected node=%s", node_id,
                )
                return False
            try:
                node = client.get_node(node_id)
                last_actual = float(await node.read_value())
            except Exception:
                logger.warning(
                    "opcua_verify_read_failed node=%s attempt=%d",
                    node_id, attempt + 1, exc_info=True,
                )
                continue
            if abs(last_actual - expected) <= tolerance:
                return True
            logger.warning(
                "opcua_verify_mismatch node=%s expected=%.6f actual=%.6f "
                "attempt=%d/%d",
                node_id, expected, last_actual,
                attempt + 1, self._VERIFY_MAX_RETRIES + 1,
            )
            if attempt < self._VERIFY_MAX_RETRIES:
                try:
                    await self._async_write_value(client, node_id, expected)
                except Exception:
                    logger.warning(
                        "opcua_verify_rewrite_failed node=%s attempt=%d",
                        node_id, attempt + 1, exc_info=True,
                    )
        logger.error(
            "opcua_verify_exhausted node=%s expected=%.6f last_actual=%s",
            node_id, expected,
            f"{last_actual:.6f}" if last_actual is not None else "n/a",
        )
        return False

    async def _async_verify_write_int(
        self, client, node_id: str, expected: int,
    ) -> bool:
        """Read-back an int node after _VERIFY_DELAY_S; retry write on mismatch."""
        last_actual: int | None = None
        for attempt in range(self._VERIFY_MAX_RETRIES + 1):
            await asyncio.sleep(self._VERIFY_DELAY_S)
            if self.state != ConnectionState.ONLINE:
                logger.warning(
                    "opcua_verify_skipped_disconnected node=%s", node_id,
                )
                return False
            try:
                node = client.get_node(node_id)
                last_actual = int(await node.read_value())
            except Exception:
                logger.warning(
                    "opcua_verify_read_failed node=%s attempt=%d",
                    node_id, attempt + 1, exc_info=True,
                )
                continue
            if last_actual == expected:
                return True
            logger.warning(
                "opcua_verify_mismatch_int node=%s expected=%d actual=%d "
                "attempt=%d/%d",
                node_id, expected, last_actual,
                attempt + 1, self._VERIFY_MAX_RETRIES + 1,
            )
            if attempt < self._VERIFY_MAX_RETRIES:
                try:
                    await self._async_write_int32(client, node_id, expected)
                except Exception:
                    logger.warning(
                        "opcua_verify_rewrite_failed node=%s attempt=%d",
                        node_id, attempt + 1, exc_info=True,
                    )
        logger.error(
            "opcua_verify_exhausted_int node=%s expected=%d last_actual=%s",
            node_id, expected, last_actual,
        )
        return False

    # ---- Tuning Read/Write ----

    def read_pid_params(self, controller_id: int) -> PIDParamsRead | None:
        """Read Kp, Ti, Td from external DCS. Returns None if no tuning tags mapped."""
        with self._lock:
            tags = self._controllers.get(controller_id, {})
            kp_id = tags.get("kp", "")
            ti_id = tags.get("ti", "")
            td_id = tags.get("td", "")
            client = self._client

        if not kp_id and not ti_id and not td_id:
            return None
        if client is None or self.state != ConnectionState.ONLINE:
            return None

        future = asyncio.run_coroutine_threadsafe(
            self._async_read_pid_params(client, kp_id, ti_id, td_id),
            self._loop,
        )
        return future.result(timeout=self._timeout_s)

    async def _async_read_pid_params(
        self, client, kp_id: str, ti_id: str, td_id: str,
    ) -> PIDParamsRead:
        """Async read of tuning parameter nodes."""
        kp: float | None = None
        ti: float | None = None
        td: float | None = None

        if kp_id:
            node = client.get_node(kp_id)
            kp = float(await node.read_value())
        if ti_id:
            node = client.get_node(ti_id)
            ti = float(await node.read_value())
        if td_id:
            node = client.get_node(td_id)
            td = float(await node.read_value())

        return PIDParamsRead(kp=kp, ti=ti, td=td, timestamp=time.time())

    def write_pid_params(
        self, controller_id: int, kp: float | None, ti: float | None, td: float | None,
    ) -> None:
        """Write tuning parameters to DCS. Only writes non-None values."""
        with self._lock:
            tags = self._controllers.get(controller_id, {})
            client = self._client

        pairs: list[tuple[str, float]] = []
        if kp is not None:
            nid = tags.get("kp", "")
            if nid:
                pairs.append((nid, kp))
        if ti is not None:
            nid = tags.get("ti", "")
            if nid:
                pairs.append((nid, ti))
        if td is not None:
            nid = tags.get("td", "")
            if nid:
                pairs.append((nid, td))

        if not pairs:
            return

        if client is None or self.state != ConnectionState.ONLINE:
            raise ConnectionError("OPC-UA not connected")

        future = asyncio.run_coroutine_threadsafe(
            self._async_write_pid_params(client, pairs),
            self._loop,
        )
        future.result(timeout=self._timeout_s)
        # Fire-and-forget read-back verification per node. If the DCS silently
        # dropped the write (ACL quirks, write-through race, etc.) the verify
        # coroutine will retry up to _VERIFY_MAX_RETRIES times.
        for node_id, value in pairs:
            asyncio.run_coroutine_threadsafe(
                self._async_verify_write_float(client, node_id, value),
                self._loop,
            )

    async def _async_write_pid_params(
        self, client, pairs: list[tuple[str, float]],
    ) -> None:
        """Async write of tuning parameter nodes."""
        for node_id, value in pairs:
            await self._async_write_value(client, node_id, value)

    def read_actual_mode(self, controller_id: int) -> ControllerMode | None:
        """Read actual PID mode from DCS via integer map.

        Returns None if no mode_actual node is mapped, adapter is offline,
        or the integer value read is not in the inverse map.
        """
        with self._lock:
            tags = self._controllers.get(controller_id, {})
            mode_id = tags.get("mode_actual", "")
            inv_map = tags.get("mode_int_map_inv", {})
            client = self._client

        if not mode_id or not self.is_connected or client is None:
            return None

        future = asyncio.run_coroutine_threadsafe(
            self._async_read_actual_mode(client, mode_id, inv_map),
            self._loop,
        )
        return future.result(timeout=self._timeout_s)

    async def _async_read_actual_mode(
        self, client, mode_id: str, inv_map: dict[int, str],
    ) -> ControllerMode | None:
        """Async read of mode integer node, mapped back to ControllerMode."""
        node = client.get_node(mode_id)
        value = await node.read_value()
        int_val = int(value)
        mode_str = inv_map.get(int_val)
        if mode_str is None:
            logger.warning("unmapped_mode_integer value=%d node=%s", int_val, mode_id)
            return None
        return ControllerMode(mode_str)

    def read_pid_enabled(self, controller_id: int) -> bool | None:
        """Read the PLC's "process using this PID is running" flag.

        The node is the ``node_id_enabled`` binding — conventionally the PLC
        tag ``PID_[MALHA]_ENABLED`` (e.g. ``Process_Running``). It carries a
        boolean, or an integer where 1 = running and 0 = stopped.

        Returns None — meaning "unknown", never a fabricated ``True`` — when
        no node is mapped, the adapter is offline, or the read fails. Callers
        must treat None as "no opinion" and leave the optimizer ungated:
        an unmapped tag is the absence of a permissive, not a prohibition.
        """
        with self._lock:
            tags = self._controllers.get(controller_id, {})
            enabled_id = tags.get("enabled", "")
            client = self._client

        if not enabled_id or not self.is_connected or client is None:
            return None

        future = asyncio.run_coroutine_threadsafe(
            self._async_read_pid_enabled(client, enabled_id),
            self._loop,
        )
        return future.result(timeout=self._timeout_s)

    async def _async_read_pid_enabled(self, client, node_id: str) -> bool | None:
        """Async read of the process-running node, coerced to bool."""
        node = client.get_node(node_id)
        value = await node.read_value()
        if value is None:
            return None
        return bool(value)

    def write_target_mode(self, controller_id: int, mode: ControllerMode) -> bool:
        """Write target mode to DCS as integer via mode_int_map.

        Returns True on success, False if offline, no target node mapped,
        or the mode is not present in the integer map.
        """
        with self._lock:
            tags = self._controllers.get(controller_id, {})
            target_id = tags.get("mode_target", "")
            int_map = tags.get("mode_int_map", {})
            client = self._client

        if not target_id or not self.is_connected or client is None:
            return False

        int_val = int_map.get(mode.value)
        if int_val is None:
            logger.warning("mode_not_in_map mode=%s controller=%d", mode.value, controller_id)
            return False

        future = asyncio.run_coroutine_threadsafe(
            self._async_write_int32(client, target_id, int(int_val)),
            self._loop,
        )
        try:
            future.result(timeout=self._timeout_s)
        except Exception:
            logger.exception("write_target_mode_failed controller=%d", controller_id)
            return False
        # Fire-and-forget read-back verification
        asyncio.run_coroutine_threadsafe(
            self._async_verify_write_int(client, target_id, int(int_val)),
            self._loop,
        )
        return True

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
