"""OPCUAServer — embedded asyncua.Server for simulator OPC-UA exposure."""
from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)

NAMESPACE_URI = "urn:smartpid:sim"


class OPCUAServer:
    """Embedded asyncua.Server exposing simulated controller nodes.

    Runs in a daemon thread with its own asyncio event loop.
    Creates a namespace ``urn:smartpid:sim`` with folders per controller,
    each containing Float variables PV, SP, CO and Int variables Mode, Status.
    """

    def __init__(self, port: int = 4841) -> None:
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
        """Register callback for external writes to CO or SP nodes."""
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
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
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

    def update_values(
        self,
        controller_id: int,
        pv: float,
        sp: float,
        co: float,
        mode: int = 0,
        status: int = 0,
    ) -> None:
        """Update OPC-UA node values for a controller. Thread-safe."""
        if self._loop is None or not self._loop.is_running():
            return
        asyncio.run_coroutine_threadsafe(
            self._async_update_values(controller_id, pv, sp, co, mode, status),
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
            for param in ("co", "sp"):
                node = nodes_dict.get(param)
                if node is not None:
                    await sub.subscribe_data_change(node)

        async with self._server:
            self._ready.set()
            while not self._stop_event.is_set():
                await asyncio.sleep(0.1)

    async def _async_register_controller(self, controller_id: int) -> dict[str, str]:
        """Create OPC-UA nodes for a controller under Controllers folder."""
        from asyncua import ua

        tag = f"CTRL_{controller_id}"
        ctrl_folder = await self._controllers_folder.add_folder(self._ns_idx, tag)

        pv_node = await ctrl_folder.add_variable(
            self._ns_idx, "PV", 0.0, ua.VariantType.Float,
        )
        sp_node = await ctrl_folder.add_variable(
            self._ns_idx, "SP", 50.0, ua.VariantType.Float,
        )
        co_node = await ctrl_folder.add_variable(
            self._ns_idx, "CO", 0.0, ua.VariantType.Float,
        )
        mode_node = await ctrl_folder.add_variable(
            self._ns_idx, "Mode", 0, ua.VariantType.Int32,
        )
        status_node = await ctrl_folder.add_variable(
            self._ns_idx, "Status", 0, ua.VariantType.Int32,
        )

        # Make CO and SP writable (for external clients)
        await co_node.set_writable()
        await sp_node.set_writable()

        node_ids = {
            "pv": pv_node.nodeid.to_string(),
            "sp": sp_node.nodeid.to_string(),
            "co": co_node.nodeid.to_string(),
            "mode": mode_node.nodeid.to_string(),
            "status": status_node.nodeid.to_string(),
        }
        self._controller_node_ids[controller_id] = node_ids
        self._controller_nodes[controller_id] = {
            "pv": pv_node,
            "sp": sp_node,
            "co": co_node,
            "mode": mode_node,
            "status": status_node,
        }
        logger.info("opcua_server_registered controller=%d tag=%s", controller_id, tag)

        # Subscribe new CO/SP nodes if subscription exists (late registration)
        if self._subscription is not None:
            for param in ("co", "sp"):
                node = self._controller_nodes[controller_id].get(param)
                if node is not None:
                    await self._subscription.subscribe_data_change(node)

        return node_ids

    async def _async_update_values(
        self,
        controller_id: int,
        pv: float,
        sp: float,
        co: float,
        mode: int,
        status: int,
    ) -> None:
        """Write new values to the controller's OPC-UA nodes."""
        nodes = self._controller_nodes.get(controller_id)
        if nodes is None:
            return
        from asyncua import ua

        await nodes["pv"].write_value(ua.DataValue(ua.Variant(pv, ua.VariantType.Float)))
        await nodes["sp"].write_value(ua.DataValue(ua.Variant(sp, ua.VariantType.Float)))
        await nodes["co"].write_value(ua.DataValue(ua.Variant(co, ua.VariantType.Float)))
        await nodes["mode"].write_value(ua.DataValue(ua.Variant(mode, ua.VariantType.Int32)))
        await nodes["status"].write_value(
            ua.DataValue(ua.Variant(status, ua.VariantType.Int32)),
        )


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
            for param in ("co", "sp"):
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
