"""OPCUAServer — embedded asyncua.Server for simulator OPC-UA exposure."""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

NAMESPACE_URI = "urn:smartpid:sim"
_WRITABLE_PARAMS = ("co", "sp", "kp", "ti", "td", "pid_mode", "pid_sp")

# All node keys grouped by sub-folder for address space organization
_PID_NODES = (
    "pv", "sp", "co", "mode", "status",
    "kp", "ti", "td", "pid_mode", "pid_sp", "pid_enabled", "pid_cv", "error",
)
_PROCESS_NODES = (
    "process_gain", "process_tau1", "process_tau2", "process_dead_time",
    "process_preset", "process_pv_min", "process_pv_max",
    "process_input", "process_output",
)
_DISTURBANCE_NODES = (
    "step_active", "step_amplitude", "noise_active", "noise_amplitude",
    "auto_sp_enabled", "auto_sp_min_pct", "auto_sp_max_pct",
    "auto_dist_enabled", "auto_dist_max_pct",
)


class OPCUAServer:
    """Embedded asyncua.Server exposing simulated controller nodes.

    Runs in a daemon thread with its own asyncio event loop.
    Creates a namespace ``urn:smartpid:sim`` with folders per controller,
    each containing Float variables PV, SP, CO and Int variables Mode, Status.
    """

    def __init__(self, port: int = 4849) -> None:
        self._port = port
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._server = None  # asyncua.Server, created in thread
        self._ns_idx: int = 0
        self._controller_node_ids: dict[int, dict[str, str]] = {}
        self._controller_nodes: dict[int, dict] = {}
        self._on_write: Callable[[int, str, float], None] | None = None
        self._subscription = None
        self._write_handler = None
        self._smartpid_folder = None
        self._controllers_folder = None

    @property
    def port(self) -> int:
        return self._port

    @property
    def endpoint(self) -> str:
        return f"opc.tcp://0.0.0.0:{self._port}"

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def controller_node_ids(self) -> dict[int, dict[str, str]]:
        """Return controller_id -> {param: node_id_str} mapping."""
        return dict(self._controller_node_ids)

    def set_on_write(self, callback: Callable[[int, str, float], None]) -> None:
        """Register callback for external writes to writable nodes."""
        self._on_write = callback

    def start(self) -> None:
        """Start the OPC-UA server in a background daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="opcua-sim-server",
        )
        self._thread.start()
        if not self._ready.wait(timeout=10.0):
            raise RuntimeError("OPCUAServer failed to start within 10s")
        logger.info("opcua_server_started port=%d", self._port)

    def stop(self) -> None:
        """Stop the server and join the thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=10.0)
            self._thread = None
        self._server = None
        logger.info("opcua_server_stopped")

    def register_controller(self, controller_id: int) -> dict[str, str]:
        """Register a controller — creates OPC-UA nodes.

        If called before start(), stores for deferred creation.
        If called after start(), schedules creation on the server's event loop.
        Returns dict of {param: node_id_str} for the controller.
        """
        if self._loop is not None and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self._async_register_controller(controller_id), self._loop,
            )
            return future.result(timeout=5.0)
        # Pre-start: store for deferred creation
        self._controller_node_ids[controller_id] = {}
        return {}

    def update_values(  # noqa: PLR0913
        self,
        controller_id: int,
        *,
        values: dict[str, float | int | str | bool],
    ) -> None:
        """Update OPC-UA node values for a controller. Thread-safe.

        ``values`` is a dict of node_key -> value for all nodes to update.
        """
        if self._loop is None or not self._loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(
            self._async_update_values(controller_id, values),
            self._loop,
        )

    # ---- Private async methods ----

    def _run(self) -> None:
        """Run the asyncio event loop for the OPC-UA server."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._setup_and_serve())
        except Exception:
            logger.exception("opcua_server_error")
        finally:
            self._loop.close()
            self._loop = None

    async def _setup_and_serve(self) -> None:
        """Initialize asyncua.Server, register namespace, create nodes, run."""
        from asyncua import Server  # noqa: F811

        self._server = Server()
        await self._server.init()
        self._server.set_endpoint(self.endpoint)
        self._server.set_server_name("SmartPID Simulator")
        self._ns_idx = await self._server.register_namespace(NAMESPACE_URI)

        objects = self._server.nodes.objects
        self._smartpid_folder = await objects.add_folder(self._ns_idx, "SmartPID")
        self._controllers_folder = await self._smartpid_folder.add_folder(
            self._ns_idx, "Controllers",
        )

        # Create nodes for any pre-registered controllers
        for controller_id in list(self._controller_node_ids.keys()):
            await self._async_register_controller(controller_id)

        # Subscribe to write events
        handler = _WriteHandler(self._on_write, self._controller_nodes)
        self._write_handler = handler
        sub = await self._server.create_subscription(100, handler)
        self._subscription = sub
        for nodes_dict in self._controller_nodes.values():
            for param in _WRITABLE_PARAMS:
                node = nodes_dict.get(param)
                if node is not None:
                    await sub.subscribe_data_change(node)

        async with self._server:
            self._ready.set()
            while not self._stop_event.is_set():
                await asyncio.sleep(0.1)

    async def _async_register_controller(self, controller_id: int) -> dict[str, str]:
        """Create OPC-UA nodes for a controller under Controllers folder.

        Address space layout per controller::

            CTRL_{id}/
              PID/        — PV, SP, CO, Mode, Status, Kp, Ti, Td, PID_Mode, PID_SP,
                            PID_Enabled, PID_CV, Error
              Process/    — Gain, Tau1, Tau2, DeadTime, Preset, PV_Min, PV_Max,
                            Input (CO→process), Output (raw process out)
              Disturbance/ — Step_Active, Step_Amplitude, Noise_Active, Noise_Amplitude,
                             Auto_SP_Enabled, Auto_SP_Min, Auto_SP_Max,
                             Auto_Dist_Enabled, Auto_Dist_Max
        """
        from asyncua import ua

        tag = f"CTRL_{controller_id}"
        ctrl_folder = await self._controllers_folder.add_folder(self._ns_idx, tag)

        # --- PID sub-folder ---
        pid_folder = await ctrl_folder.add_folder(self._ns_idx, "PID")
        nodes: dict[str, object] = {}

        nodes["pv"] = await pid_folder.add_variable(
            self._ns_idx, "PV", 0.0, ua.VariantType.Float,
        )
        nodes["sp"] = await pid_folder.add_variable(
            self._ns_idx, "SP", 50.0, ua.VariantType.Float,
        )
        nodes["co"] = await pid_folder.add_variable(
            self._ns_idx, "CO", 0.0, ua.VariantType.Float,
        )
        nodes["mode"] = await pid_folder.add_variable(
            self._ns_idx, "Mode", 0, ua.VariantType.Int32,
        )
        nodes["status"] = await pid_folder.add_variable(
            self._ns_idx, "Status", 0, ua.VariantType.Int32,
        )
        nodes["kp"] = await pid_folder.add_variable(
            self._ns_idx, "Kp", 1.0, ua.VariantType.Float,
        )
        nodes["ti"] = await pid_folder.add_variable(
            self._ns_idx, "Ti", 10.0, ua.VariantType.Float,
        )
        nodes["td"] = await pid_folder.add_variable(
            self._ns_idx, "Td", 0.0, ua.VariantType.Float,
        )
        nodes["pid_mode"] = await pid_folder.add_variable(
            self._ns_idx, "PID_Mode", 0, ua.VariantType.Int32,
        )
        nodes["pid_sp"] = await pid_folder.add_variable(
            self._ns_idx, "PID_SP", 50.0, ua.VariantType.Float,
        )
        nodes["pid_enabled"] = await pid_folder.add_variable(
            self._ns_idx, "PID_Enabled", False, ua.VariantType.Boolean,
        )
        nodes["pid_cv"] = await pid_folder.add_variable(
            self._ns_idx, "PID_CV", 0.0, ua.VariantType.Float,
        )
        nodes["error"] = await pid_folder.add_variable(
            self._ns_idx, "Error", 0.0, ua.VariantType.Float,
        )

        # --- Process sub-folder ---
        proc_folder = await ctrl_folder.add_folder(self._ns_idx, "Process")

        nodes["process_gain"] = await proc_folder.add_variable(
            self._ns_idx, "Gain", 1.2, ua.VariantType.Float,
        )
        nodes["process_tau1"] = await proc_folder.add_variable(
            self._ns_idx, "Tau1", 3.0, ua.VariantType.Float,
        )
        nodes["process_tau2"] = await proc_folder.add_variable(
            self._ns_idx, "Tau2", 0.0, ua.VariantType.Float,
        )
        nodes["process_dead_time"] = await proc_folder.add_variable(
            self._ns_idx, "DeadTime", 1.0, ua.VariantType.Float,
        )
        nodes["process_preset"] = await proc_folder.add_variable(
            self._ns_idx, "Preset", "FLOW", ua.VariantType.String,
        )
        nodes["process_pv_min"] = await proc_folder.add_variable(
            self._ns_idx, "PV_Min", 0.0, ua.VariantType.Float,
        )
        nodes["process_pv_max"] = await proc_folder.add_variable(
            self._ns_idx, "PV_Max", 100.0, ua.VariantType.Float,
        )
        nodes["process_input"] = await proc_folder.add_variable(
            self._ns_idx, "Input", 0.0, ua.VariantType.Float,
        )
        nodes["process_output"] = await proc_folder.add_variable(
            self._ns_idx, "Output", 0.0, ua.VariantType.Float,
        )

        # --- Disturbance sub-folder ---
        dist_folder = await ctrl_folder.add_folder(self._ns_idx, "Disturbance")

        nodes["step_active"] = await dist_folder.add_variable(
            self._ns_idx, "Step_Active", False, ua.VariantType.Boolean,
        )
        nodes["step_amplitude"] = await dist_folder.add_variable(
            self._ns_idx, "Step_Amplitude", 0.0, ua.VariantType.Float,
        )
        nodes["noise_active"] = await dist_folder.add_variable(
            self._ns_idx, "Noise_Active", False, ua.VariantType.Boolean,
        )
        nodes["noise_amplitude"] = await dist_folder.add_variable(
            self._ns_idx, "Noise_Amplitude", 0.0, ua.VariantType.Float,
        )
        nodes["auto_sp_enabled"] = await dist_folder.add_variable(
            self._ns_idx, "Auto_SP_Enabled", False, ua.VariantType.Boolean,
        )
        nodes["auto_sp_min_pct"] = await dist_folder.add_variable(
            self._ns_idx, "Auto_SP_Min", 30.0, ua.VariantType.Float,
        )
        nodes["auto_sp_max_pct"] = await dist_folder.add_variable(
            self._ns_idx, "Auto_SP_Max", 70.0, ua.VariantType.Float,
        )
        nodes["auto_dist_enabled"] = await dist_folder.add_variable(
            self._ns_idx, "Auto_Dist_Enabled", False, ua.VariantType.Boolean,
        )
        nodes["auto_dist_max_pct"] = await dist_folder.add_variable(
            self._ns_idx, "Auto_Dist_Max", 10.0, ua.VariantType.Float,
        )

        # Make writable params accessible to external clients
        for param in _WRITABLE_PARAMS:
            await nodes[param].set_writable()

        # Build node_id mapping
        node_ids = {key: node.nodeid.to_string() for key, node in nodes.items()}
        self._controller_node_ids[controller_id] = node_ids
        self._controller_nodes[controller_id] = nodes
        logger.info("opcua_server_registered controller=%d tag=%s", controller_id, tag)

        # Subscribe writable nodes if subscription exists (late registration)
        if self._subscription is not None:
            for param in _WRITABLE_PARAMS:
                node = self._controller_nodes[controller_id].get(param)
                if node is not None:
                    await self._subscription.subscribe_data_change(node)

        return node_ids

    # Mapping from node key to asyncua VariantType
    _VARIANT_TYPES: dict[str, str] = {
        "pv": "Float", "sp": "Float", "co": "Float",
        "mode": "Int32", "status": "Int32",
        "kp": "Float", "ti": "Float", "td": "Float",
        "pid_mode": "Int32", "pid_sp": "Float",
        "pid_enabled": "Boolean", "pid_cv": "Float", "error": "Float",
        "process_gain": "Float", "process_tau1": "Float",
        "process_tau2": "Float", "process_dead_time": "Float",
        "process_preset": "String",
        "process_pv_min": "Float", "process_pv_max": "Float",
        "process_input": "Float", "process_output": "Float",
        "step_active": "Boolean", "step_amplitude": "Float",
        "noise_active": "Boolean", "noise_amplitude": "Float",
        "auto_sp_enabled": "Boolean",
        "auto_sp_min_pct": "Float", "auto_sp_max_pct": "Float",
        "auto_dist_enabled": "Boolean", "auto_dist_max_pct": "Float",
    }

    async def _async_update_values(
        self,
        controller_id: int,
        values: dict[str, float | int | str | bool],
    ) -> None:
        """Write new values to the controller's OPC-UA nodes."""
        nodes = self._controller_nodes.get(controller_id)
        if nodes is None:
            return
        from asyncua import ua

        for key, value in values.items():
            node = nodes.get(key)
            if node is None:
                continue
            vtype_name = self._VARIANT_TYPES.get(key)
            if vtype_name is None:
                continue
            vtype = getattr(ua.VariantType, vtype_name)
            await node.write_value(ua.DataValue(ua.Variant(value, vtype)))


class _WriteHandler:
    """asyncua subscription handler — live node lookup for late-registered controllers."""

    def __init__(
        self,
        callback: Callable[[int, str, float], None] | None,
        controller_nodes: dict[int, dict],
    ) -> None:
        self._callback = callback
        # Hold reference to live dict (not a copy) so late-registered controllers are visible
        self._controller_nodes = controller_nodes

    def _resolve_node(self, node_id_str: str) -> tuple[int, str] | None:
        """Find controller_id and param name from a node_id string."""
        for cid, nodes in self._controller_nodes.items():
            for param in _WRITABLE_PARAMS:
                node = nodes.get(param)
                if node is not None and node.nodeid.to_string() == node_id_str:
                    return (cid, param)
        return None

    def datachange_notification(self, node, val, data) -> None:  # noqa: ANN001
        """Called by asyncua when a monitored node changes value."""
        if self._callback is None:
            return
        node_id_str = node.nodeid.to_string()
        mapping = self._resolve_node(node_id_str)
        if mapping is not None:
            controller_id, param = mapping
            try:
                self._callback(controller_id, param, float(val))
            except Exception:
                logger.exception(
                    "opcua_write_callback_error controller=%d param=%s", controller_id, param,
                )
