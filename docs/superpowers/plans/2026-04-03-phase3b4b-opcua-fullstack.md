# Phase 3b+4b — OPC-UA Full-Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add embedded asyncua.Server to SimulatorAdapter and wire OPCUAAdapter as the unified I/O path, enabling closed-loop PID control over OPC-UA — testable locally without hardware.

**Architecture:** SimulatorAdapter hosts an asyncua.Server exposing PV/SP/CO as OPC-UA nodes. OPCUAAdapter (already complete) connects as client. AdapterFactory creates both when simulator is enabled. All I/O goes through OPC-UA, replacing the SimpleQueue path.

**Tech Stack:** asyncua (server + client), threading, asyncio, scipy.signal, pytest-asyncio

**Depends on:** Phase 3a (merged), Phase 4 simulator (merged), Phase 3b OPCUAAdapter (merged)

---

## Task 1: OPCUAServer Wrapper

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py`
- Test: `tests/core/unit/test_opcua_server.py`

### Overview
A reusable asyncua.Server wrapper that runs in a daemon thread, creates a `urn:smartpid:sim` namespace, and exposes per-controller OPC-UA nodes (PV, SP, CO, Mode, Status). Supports value updates from the simulator tick loop and notifies via callback when an external client writes to CO or SP.

- [ ] **Step 1.1: Write the failing test — OPCUAServer init and lifecycle**

```python
# tests/core/unit/test_opcua_server.py
"""Unit tests for OPCUAServer wrapper."""
from __future__ import annotations

import pytest


class TestOPCUAServerInit:
    def test_initial_state_not_running(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=48420)
        assert not server.is_running

    def test_port_stored(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=48421)
        assert server.port == 48421

    def test_endpoint_format(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=48422)
        assert server.endpoint == "opc.tcp://0.0.0.0:48422"

    def test_no_controllers_initially(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=48423)
        assert server.controller_node_ids == {}
```

- [ ] **Step 1.2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_opcua_server.py -v`
Expected: FAIL (ModuleNotFoundError — opcua_server module does not exist)

- [ ] **Step 1.3: Write minimal implementation — OPCUAServer class skeleton**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py
"""OPCUAServer — embedded asyncua.Server for simulator OPC-UA exposure."""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)

# Namespace URI for SimulatorAdapter OPC-UA nodes
NAMESPACE_URI = "urn:smartpid:sim"


class OPCUAServer:
    """Embedded asyncua.Server exposing simulated controller nodes.

    Runs in a daemon thread with its own asyncio event loop.
    Creates a namespace ``urn:smartpid:sim`` with folders per controller,
    each containing Float variables PV, SP, CO and Int variables Mode, Status.

    Supports:
    - ``register_controller(controller_id)`` — creates OPC-UA node folder
    - ``update_values(controller_id, pv, sp, co, mode, status)`` — pushes new values
    - ``on_write`` callback — notified when external client writes CO or SP
    """

    def __init__(self, port: int = 4841) -> None:
        self._port = port
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._ready = threading.Event()
        self._server = None  # asyncua.Server, created in thread
        self._ns_idx: int = 0

        # controller_id -> {"pv": node_id_str, "sp": ..., "co": ..., "mode": ..., "status": ...}
        self._controller_node_ids: dict[int, dict[str, str]] = {}
        # controller_id -> {"pv": Node, "sp": Node, "co": Node, "mode": Node, "status": Node}
        self._controller_nodes: dict[int, dict] = {}

        # Callback: on_write(controller_id: int, param: str, value: float) -> None
        self._on_write: Callable[[int, str, float], None] | None = None

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
        """Register a controller — creates OPC-UA nodes. Must be called BEFORE start().

        Returns dict of {param: node_id_str} for the controller.
        If called after start(), schedules creation on the server's event loop.
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
        from asyncua import Server, ua

        self._server = Server()
        await self._server.init()
        self._server.set_endpoint(self.endpoint)
        self._server.set_server_name("SmartPID Simulator")
        self._ns_idx = await self._server.register_namespace(NAMESPACE_URI)

        # Create root folder: Objects/SmartPID
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
        sub = await self._server.create_subscription(100, handler)
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
    """asyncua subscription handler that fires on_write callback when CO/SP changes."""

    def __init__(
        self,
        callback: Callable[[int, str, float], None] | None,
        controller_nodes: dict[int, dict],
    ) -> None:
        self._callback = callback
        self._controller_nodes = controller_nodes
        # Build reverse lookup: node_id_str -> (controller_id, param_name)
        self._node_to_ctrl: dict[str, tuple[int, str]] = {}
        for cid, nodes in controller_nodes.items():
            for param in ("co", "sp"):
                node = nodes.get(param)
                if node is not None:
                    self._node_to_ctrl[node.nodeid.to_string()] = (cid, param)

    def datachange_notification(self, node, val, data) -> None:  # noqa: ANN001
        """Called by asyncua when a monitored node changes value."""
        if self._callback is None:
            return
        node_id_str = node.nodeid.to_string()
        mapping = self._node_to_ctrl.get(node_id_str)
        if mapping is not None:
            controller_id, param = mapping
            try:
                self._callback(controller_id, param, float(val))
            except Exception:
                logger.exception(
                    "opcua_write_callback_error controller=%d param=%s", controller_id, param,
                )
```

- [ ] **Step 1.4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_opcua_server.py -v`
Expected: PASS (all 4 init tests green)

- [ ] **Step 1.5: Commit**

`feat(opcua): add OPCUAServer wrapper class with lifecycle and node management`

---

- [ ] **Step 1.6: Write the failing test — start/stop lifecycle with asyncua**

```python
# tests/core/unit/test_opcua_server.py (append to file)

class TestOPCUAServerLifecycle:
    def test_start_and_stop(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=48424)
        server.start()
        try:
            assert server.is_running
        finally:
            server.stop()
        assert not server.is_running

    def test_double_start_is_idempotent(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=48425)
        server.start()
        try:
            server.start()  # Should not raise
            assert server.is_running
        finally:
            server.stop()

    def test_stop_when_not_started_is_safe(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=48426)
        server.stop()  # Should not raise
```

- [ ] **Step 1.7: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_opcua_server.py::TestOPCUAServerLifecycle -v`
Expected: PASS (implementation from Step 1.3 already handles start/stop)

- [ ] **Step 1.8: Commit (if any changes were needed)**

`test(opcua): add OPCUAServer lifecycle tests`

---

- [ ] **Step 1.9: Write the failing test — register_controller creates nodes**

```python
# tests/core/unit/test_opcua_server.py (append to file)
import time


class TestOPCUAServerRegisterController:
    def test_register_before_start_stores_controller(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=48427)
        server.register_controller(1)
        # Pre-start: node_ids dict exists but is empty (deferred creation)
        assert 1 in server.controller_node_ids

    def test_register_after_start_creates_nodes(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=48428)
        server.start()
        try:
            node_ids = server.register_controller(1)
            assert "pv" in node_ids
            assert "sp" in node_ids
            assert "co" in node_ids
            assert "mode" in node_ids
            assert "status" in node_ids
            # Node IDs should be non-empty strings like "ns=2;i=..."
            assert all(nid.startswith("ns=") for nid in node_ids.values())
        finally:
            server.stop()

    def test_pre_registered_controllers_get_nodes_after_start(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer

        server = OPCUAServer(port=48429)
        server.register_controller(1)
        server.start()
        try:
            # After start, node_ids should be populated
            node_ids = server.controller_node_ids[1]
            assert "pv" in node_ids
            assert all(nid.startswith("ns=") for nid in node_ids.values())
        finally:
            server.stop()
```

- [ ] **Step 1.10: Run test to verify it fails / passes**

Run: `uv run pytest tests/core/unit/test_opcua_server.py::TestOPCUAServerRegisterController -v`
Expected: PASS (implementation from Step 1.3 handles both paths)

- [ ] **Step 1.11: Commit**

`test(opcua): add register_controller tests for OPCUAServer`

---

- [ ] **Step 1.12: Write the failing test — update_values and read-back via client**

```python
# tests/core/unit/test_opcua_server.py (append to file)
import pytest


class TestOPCUAServerUpdateValues:
    def test_update_values_readable_by_client(self) -> None:
        """Start OPCUAServer, update values, connect OPCUAAdapter as client, verify."""
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
        from smart_pid_core.config import CoreSettings

        server = OPCUAServer(port=48430)
        server.register_controller(1)
        server.start()
        try:
            node_ids = server.controller_node_ids[1]

            # Connect OPCUAAdapter as client
            settings = CoreSettings(
                jwt_secret="test-secret-key-minimum-32-bytes!",
                opcua_endpoint="opc.tcp://localhost:48430",
            )  # type: ignore[call-arg]
            client = OPCUAAdapter(settings=settings)
            client.register_controller(
                controller_id=1,
                node_id_pv=node_ids["pv"],
                node_id_sp=node_ids["sp"],
                node_id_co=node_ids["co"],
            )
            client.start()
            try:
                assert client.wait_connected(timeout_s=5.0)

                # Update values on server side
                server.update_values(
                    controller_id=1, pv=72.5, sp=75.0, co=45.0, mode=4, status=0,
                )
                time.sleep(0.3)  # Allow async write to propagate

                frame = client.read_telemetry(1)
                assert frame.pv == pytest.approx(72.5, abs=0.5)
                assert frame.sp == pytest.approx(75.0, abs=0.5)
                assert frame.co == pytest.approx(45.0, abs=0.5)
            finally:
                client.stop()
        finally:
            server.stop()
```

- [ ] **Step 1.13: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_opcua_server.py::TestOPCUAServerUpdateValues -v`
Expected: Initially may FAIL if async timing is off; pass after implementation is verified.

- [ ] **Step 1.14: Adjust if needed and run green**

Run: `uv run pytest tests/core/unit/test_opcua_server.py -v`
Expected: PASS (all tests)

- [ ] **Step 1.15: Commit**

`test(opcua): add update_values read-back test with OPCUAAdapter client`

---

- [ ] **Step 1.16: Write the failing test — on_write callback fires when client writes CO**

```python
# tests/core/unit/test_opcua_server.py (append to file)
import threading


class TestOPCUAServerWriteCallback:
    def test_on_write_fires_when_client_writes_co(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
        from smart_pid_core.config import CoreSettings

        received: list[tuple[int, str, float]] = []
        event = threading.Event()

        def on_write(controller_id: int, param: str, value: float) -> None:
            received.append((controller_id, param, value))
            event.set()

        server = OPCUAServer(port=48431)
        server.set_on_write(on_write)
        server.register_controller(1)
        server.start()
        try:
            node_ids = server.controller_node_ids[1]

            settings = CoreSettings(
                jwt_secret="test-secret-key-minimum-32-bytes!",
                opcua_endpoint="opc.tcp://localhost:48431",
            )  # type: ignore[call-arg]
            client = OPCUAAdapter(settings=settings)
            client.register_controller(
                controller_id=1,
                node_id_pv=node_ids["pv"],
                node_id_sp=node_ids["sp"],
                node_id_co=node_ids["co"],
            )
            client.start()
            try:
                assert client.wait_connected(timeout_s=5.0)

                # Write CO from client side
                client.write_output(controller_id=1, co=88.0)
                assert event.wait(timeout=3.0), "on_write callback was not called"

                # Verify callback received the correct values
                co_writes = [(cid, p, v) for cid, p, v in received if p == "co"]
                assert len(co_writes) >= 1
                assert co_writes[-1][0] == 1
                assert co_writes[-1][2] == pytest.approx(88.0, abs=0.5)
            finally:
                client.stop()
        finally:
            server.stop()

    def test_on_write_fires_when_client_writes_sp(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
        from smart_pid_core.config import CoreSettings

        received: list[tuple[int, str, float]] = []
        event = threading.Event()

        def on_write(controller_id: int, param: str, value: float) -> None:
            received.append((controller_id, param, value))
            event.set()

        server = OPCUAServer(port=48432)
        server.set_on_write(on_write)
        server.register_controller(1)
        server.start()
        try:
            node_ids = server.controller_node_ids[1]

            settings = CoreSettings(
                jwt_secret="test-secret-key-minimum-32-bytes!",
                opcua_endpoint="opc.tcp://localhost:48432",
            )  # type: ignore[call-arg]
            client = OPCUAAdapter(settings=settings)
            client.register_controller(
                controller_id=1,
                node_id_pv=node_ids["pv"],
                node_id_sp=node_ids["sp"],
                node_id_co=node_ids["co"],
            )
            client.start()
            try:
                assert client.wait_connected(timeout_s=5.0)

                client.write_parameter(controller_id=1, param="sp", value=60.0)
                assert event.wait(timeout=3.0), "on_write callback was not called"

                sp_writes = [(cid, p, v) for cid, p, v in received if p == "sp"]
                assert len(sp_writes) >= 1
                assert sp_writes[-1][2] == pytest.approx(60.0, abs=0.5)
            finally:
                client.stop()
        finally:
            server.stop()
```

- [ ] **Step 1.17: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_opcua_server.py::TestOPCUAServerWriteCallback -v`
Expected: May need `_WriteHandler` reverse lookup rebuild after late-registration. If FAIL, fix `_WriteHandler` to lazily build the lookup.

- [ ] **Step 1.18: Fix _WriteHandler if needed**

The `_WriteHandler` builds its `_node_to_ctrl` reverse lookup at construction time (in `_setup_and_serve`). For controllers registered after start, the handler's lookup needs to be updated. Modify `_WriteHandler` to reference `controller_nodes` dict directly instead of snapshotting.

Replace the `_WriteHandler` class with a version that does live lookup:

```python
class _WriteHandler:
    """asyncua subscription handler that fires on_write callback when CO/SP changes."""

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
```

Also, in `_async_register_controller`, after creating nodes, subscribe the new CO and SP nodes to the existing subscription. Store the subscription object on `self._subscription`:

```python
    # In _setup_and_serve, after creating subscription:
    self._write_handler = handler
    self._subscription = sub

    # In _async_register_controller, after creating nodes and storing them:
    if self._subscription is not None:
        for param in ("co", "sp"):
            node = self._controller_nodes[controller_id].get(param)
            if node is not None:
                await self._subscription.subscribe_data_change(node)
```

- [ ] **Step 1.19: Run tests green**

Run: `uv run pytest tests/core/unit/test_opcua_server.py -v`
Expected: PASS (all tests)

- [ ] **Step 1.20: Commit**

`feat(opcua): add write callback support with live node lookup in OPCUAServer`

---

## Task 2: SimulatorAdapter Refactor — OPC-UA Integration

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`
- Modify: `tests/core/unit/test_simulator_adapter.py`

### Overview
Replace the `SimpleQueue[TelemetryFrame]` communication path with OPC-UA: start an embedded `OPCUAServer`, write PV/SP/CO to OPC-UA nodes after each `_tick()`, and receive CO updates via the `on_write` callback.

- [ ] **Step 2.1: Write the failing test — SimulatorAdapter now exposes OPCUAServer**

```python
# tests/core/unit/test_simulator_adapter.py (add new test class)

class TestSimulatorAdapterOPCUA:
    def test_has_opcua_server_attribute(self, adapter: SimulatorAdapter) -> None:
        assert hasattr(adapter, "opcua_server")

    def test_opcua_server_is_none_before_start(self, adapter: SimulatorAdapter) -> None:
        assert adapter.opcua_server is not None  # Server is created in __init__

    def test_opcua_server_port_from_settings(self, settings: CoreSettings) -> None:
        adapter = SimulatorAdapter(settings=settings)
        assert adapter.opcua_server.port == settings.simulator_port
```

- [ ] **Step 2.2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py::TestSimulatorAdapterOPCUA -v`
Expected: FAIL (SimulatorAdapter has no opcua_server attribute)

- [ ] **Step 2.3: Modify SimulatorAdapter — add OPCUAServer**

Modify `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`:

1. Add import at top:
```python
from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer
```

2. In `__init__`, create OPCUAServer and set up the write callback:
```python
    def __init__(self, settings: CoreSettings) -> None:
        self._settings = settings
        self._queue: SimpleQueue[TelemetryFrame] = SimpleQueue()
        self._controllers: dict[int, _ControllerSim] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._opcua_server = OPCUAServer(port=settings.simulator_port)
        self._opcua_server.set_on_write(self._on_opcua_write)
```

3. Add property:
```python
    @property
    def opcua_server(self) -> OPCUAServer:
        return self._opcua_server
```

4. Add write callback method:
```python
    def _on_opcua_write(self, controller_id: int, param: str, value: float) -> None:
        """Handle writes from OPC-UA clients (e.g., OPCUAAdapter writing CO)."""
        with self._lock:
            ctrl = self._controllers.get(controller_id)
            if ctrl is None:
                return
            if param == "co":
                ctrl.last_co = value
            elif param == "sp":
                ctrl.sp = value
```

- [ ] **Step 2.4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py::TestSimulatorAdapterOPCUA -v`
Expected: PASS

- [ ] **Step 2.5: Commit**

`feat(simulator): add OPCUAServer instance to SimulatorAdapter`

---

- [ ] **Step 2.6: Write the failing test — start/stop includes OPCUAServer lifecycle**

```python
# tests/core/unit/test_simulator_adapter.py (add to TestSimulatorAdapterOPCUA class)

    def test_start_starts_opcua_server(self, settings: CoreSettings) -> None:
        adapter = SimulatorAdapter(settings=settings)
        adapter.register_controller(1)
        adapter.start()
        try:
            assert adapter.opcua_server.is_running
        finally:
            adapter.stop()

    def test_stop_stops_opcua_server(self, settings: CoreSettings) -> None:
        adapter = SimulatorAdapter(settings=settings)
        adapter.register_controller(1)
        adapter.start()
        adapter.stop()
        assert not adapter.opcua_server.is_running
```

- [ ] **Step 2.7: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py::TestSimulatorAdapterOPCUA::test_start_starts_opcua_server -v`
Expected: FAIL (OPCUAServer not started in SimulatorAdapter.start())

- [ ] **Step 2.8: Modify start/stop to include OPCUAServer lifecycle**

Modify `SimulatorAdapter.start()`:

```python
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        # Start OPC-UA server first (so nodes are ready when tick writes values)
        self._opcua_server.start()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="simulator")
        self._thread.start()
        logger.info("Simulator started (interval=%dms)", self._settings.simulator_interval_ms)
```

Modify `SimulatorAdapter.stop()`:

```python
    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._opcua_server.stop()
        logger.info("Simulator stopped")
```

- [ ] **Step 2.9: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py::TestSimulatorAdapterOPCUA -v`
Expected: PASS

- [ ] **Step 2.10: Commit**

`feat(simulator): wire OPCUAServer start/stop into SimulatorAdapter lifecycle`

---

- [ ] **Step 2.11: Write the failing test — register_controller creates OPC-UA nodes**

```python
# tests/core/unit/test_simulator_adapter.py (add to TestSimulatorAdapterOPCUA class)

    def test_register_controller_creates_opcua_nodes(self, settings: CoreSettings) -> None:
        adapter = SimulatorAdapter(settings=settings)
        adapter.register_controller(1)
        adapter.start()
        try:
            node_ids = adapter.opcua_server.controller_node_ids[1]
            assert "pv" in node_ids
            assert "sp" in node_ids
            assert "co" in node_ids
        finally:
            adapter.stop()
```

- [ ] **Step 2.12: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py::TestSimulatorAdapterOPCUA::test_register_controller_creates_opcua_nodes -v`
Expected: FAIL (register_controller doesn't delegate to OPCUAServer yet)

- [ ] **Step 2.13: Modify register_controller to also register on OPCUAServer**

```python
    def register_controller(self, controller_id: int) -> None:
        with self._lock:
            if controller_id not in self._controllers:
                self._controllers[controller_id] = _ControllerSim(controller_id=controller_id)
        self._opcua_server.register_controller(controller_id)
```

- [ ] **Step 2.14: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py::TestSimulatorAdapterOPCUA -v`
Expected: PASS

- [ ] **Step 2.15: Commit**

`feat(simulator): delegate register_controller to OPCUAServer for node creation`

---

- [ ] **Step 2.16: Write the failing test — _tick publishes to OPC-UA nodes**

```python
# tests/core/unit/test_simulator_adapter.py (add to TestSimulatorAdapterOPCUA class)

    def test_tick_writes_values_to_opcua(self, settings: CoreSettings) -> None:
        """After tick runs, OPC-UA nodes should have updated PV values."""
        import time

        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        adapter = SimulatorAdapter(settings=settings)
        adapter.register_controller(1)
        adapter.write_output(1, 50.0)  # Set CO so PV moves
        adapter.start()
        try:
            node_ids = adapter.opcua_server.controller_node_ids[1]

            # Connect OPCUAAdapter as client to read back
            client_settings = CoreSettings(
                jwt_secret="test-secret-key-minimum-32-bytes!",
                opcua_endpoint=f"opc.tcp://localhost:{settings.simulator_port}",
            )  # type: ignore[call-arg]
            client = OPCUAAdapter(settings=client_settings)
            client.register_controller(
                controller_id=1,
                node_id_pv=node_ids["pv"],
                node_id_sp=node_ids["sp"],
                node_id_co=node_ids["co"],
            )
            client.start()
            try:
                assert client.wait_connected(timeout_s=5.0)
                time.sleep(0.3)  # Let a few ticks run

                frame = client.read_telemetry(1)
                # SP should be 50.0 (default), CO should be 50.0 (what we set)
                assert frame.co == pytest.approx(50.0, abs=1.0)
                assert frame.sp == pytest.approx(50.0, abs=1.0)
            finally:
                client.stop()
        finally:
            adapter.stop()
```

- [ ] **Step 2.17: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py::TestSimulatorAdapterOPCUA::test_tick_writes_values_to_opcua -v`
Expected: FAIL (_tick still writes to queue, not to OPC-UA nodes)

- [ ] **Step 2.18: Modify _tick to write to OPC-UA nodes**

Replace the `_tick` method:

```python
    def _tick(self, dt: float) -> None:
        with self._lock:
            for ctrl in self._controllers.values():
                pv = ctrl.model.step(co=ctrl.last_co, dt=dt)
                if ctrl.step_active:
                    pv += ctrl.step_amplitude
                if ctrl.noise_active:
                    pv += random.gauss(0, ctrl.noise_amplitude)

                # Write to OPC-UA nodes (non-blocking, fire-and-forget)
                self._opcua_server.update_values(
                    controller_id=ctrl.controller_id,
                    pv=pv,
                    sp=ctrl.sp,
                    co=ctrl.last_co,
                )

                # Also put on queue for backward compatibility
                frame = TelemetryFrame(
                    controller_id=ctrl.controller_id,
                    pv=pv,
                    sp=ctrl.sp,
                    co=ctrl.last_co,
                    integral_val=0.0,
                    timestamp=datetime.now(UTC),
                )
                self._queue.put(frame)
```

**Note:** We keep the queue for now to avoid breaking existing consumers. It will be removed in Task 3 when AdapterFactory is updated to use OPCUAAdapter as the sole telemetry source.

- [ ] **Step 2.19: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py -v`
Expected: PASS (all existing + new tests)

- [ ] **Step 2.20: Commit**

`feat(simulator): write PV/SP/CO to OPC-UA nodes on each tick`

---

- [ ] **Step 2.21: Write the failing test — OPC-UA write callback updates simulator CO**

```python
# tests/core/unit/test_simulator_adapter.py (add to TestSimulatorAdapterOPCUA class)

    def test_opcua_client_write_co_updates_simulator(self, settings: CoreSettings) -> None:
        """When OPCUAAdapter writes CO, SimulatorAdapter's _ControllerSim.last_co updates."""
        import time

        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        adapter = SimulatorAdapter(settings=settings)
        adapter.register_controller(1)
        adapter.start()
        try:
            node_ids = adapter.opcua_server.controller_node_ids[1]

            client_settings = CoreSettings(
                jwt_secret="test-secret-key-minimum-32-bytes!",
                opcua_endpoint=f"opc.tcp://localhost:{settings.simulator_port}",
            )  # type: ignore[call-arg]
            client = OPCUAAdapter(settings=client_settings)
            client.register_controller(
                controller_id=1,
                node_id_pv=node_ids["pv"],
                node_id_sp=node_ids["sp"],
                node_id_co=node_ids["co"],
            )
            client.start()
            try:
                assert client.wait_connected(timeout_s=5.0)

                # Write CO from client (this is what PID engine would do)
                client.write_output(controller_id=1, co=65.0)
                time.sleep(0.5)  # Wait for callback to fire

                # Verify SimulatorAdapter received the CO update
                with adapter._lock:
                    assert adapter._controllers[1].last_co == pytest.approx(65.0, abs=0.5)
            finally:
                client.stop()
        finally:
            adapter.stop()
```

- [ ] **Step 2.22: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py::TestSimulatorAdapterOPCUA::test_opcua_client_write_co_updates_simulator -v`
Expected: PASS (the `_on_opcua_write` callback from Step 2.3 handles this)

- [ ] **Step 2.23: Commit**

`test(simulator): verify OPC-UA write callback updates simulator CO`

---

- [ ] **Step 2.24: Fix existing tests that may break due to OPCUAServer startup**

The existing `TestSimulatorAdapterRunning` tests use the `adapter` fixture which will now try to start OPCUAServer. Ensure the fixture's `simulator_port` uses unique ports to avoid conflicts.

Update the `settings` fixture to use a unique port:

```python
@pytest.fixture
def settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
        simulator_port=48440,  # Unique port for unit tests
    )  # type: ignore[call-arg]
```

Also update the `TestSimulatorAdapterOPCUA` tests to use different ports per test (since module-scoped servers could conflict). Add a port counter fixture or use unique ports per test method:

```python
# At module level
_next_port = 48440

def _unique_port() -> int:
    global _next_port
    _next_port += 1
    return _next_port
```

Then in each `TestSimulatorAdapterOPCUA` test that creates its own adapter, use `simulator_port=_unique_port()`.

- [ ] **Step 2.25: Run all simulator tests**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py -v`
Expected: PASS

- [ ] **Step 2.26: Commit**

`fix(tests): use unique ports in simulator adapter tests to avoid conflicts`

---

## Task 3: AdapterFactory Update — Dual Adapter Mode

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/factory.py`
- Modify: `tests/core/unit/test_adapter_factory.py`

### Overview
When `simulator_enabled=True`, create BOTH SimulatorAdapter (process plant + OPC-UA server) AND OPCUAAdapter (client connecting to localhost). OPCUAAdapter becomes the unified I/O path for all modes.

- [ ] **Step 3.1: Write the failing test — simulator mode creates both adapters**

```python
# tests/core/unit/test_adapter_factory.py (replace TestAdapterFactorySimulator class)

class TestAdapterFactorySimulator:
    def test_creates_simulator_adapter(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        assert factory.simulator_adapter is not None

    def test_creates_opcua_adapter(self, sim_settings: CoreSettings) -> None:
        """In simulator mode, OPCUAAdapter is ALSO created (as the I/O client)."""
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        factory = AdapterFactory(sim_settings)
        assert factory.opcua_adapter is not None
        assert isinstance(factory.opcua_adapter, OPCUAAdapter)

    def test_telemetry_source_is_opcua(self, sim_settings: CoreSettings) -> None:
        """Telemetry always goes through OPCUAAdapter, even in simulator mode."""
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        factory = AdapterFactory(sim_settings)
        assert isinstance(factory.telemetry_source, OPCUAAdapter)

    def test_control_writer_is_opcua(self, sim_settings: CoreSettings) -> None:
        """Control writes always go through OPCUAAdapter, even in simulator mode."""
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        factory = AdapterFactory(sim_settings)
        assert isinstance(factory.control_writer, OPCUAAdapter)

    def test_tag_browser_available_in_simulator_mode(self, sim_settings: CoreSettings) -> None:
        """TagBrowser should now be available in simulator mode too."""
        factory = AdapterFactory(sim_settings)
        browser = factory.tag_browser  # Should NOT raise
        assert browser is not None

    def test_opcua_endpoint_points_to_simulator(self, sim_settings: CoreSettings) -> None:
        """OPCUAAdapter endpoint should point to the local simulator server."""
        factory = AdapterFactory(sim_settings)
        adapter = factory.opcua_adapter
        assert "4841" in adapter.endpoint  # Default simulator port
```

- [ ] **Step 3.2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_adapter_factory.py::TestAdapterFactorySimulator -v`
Expected: FAIL (current factory only creates SimulatorAdapter when simulator_enabled)

- [ ] **Step 3.3: Rewrite AdapterFactory**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/factory.py
"""AdapterFactory — centralized DI based on CoreSettings."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_core.config import CoreSettings


class AdapterFactory:
    """Creates and caches adapter instances based on configuration.

    When simulator is enabled:
    - SimulatorAdapter hosts the process model + embedded OPC-UA server
    - OPCUAAdapter connects to the local simulator OPC-UA server
    - All I/O (telemetry, control writes, tag browsing) goes through OPCUAAdapter

    When simulator is disabled:
    - OPCUAAdapter connects to an external OPC-UA server (real PLC/DCS)
    """

    def __init__(self, settings: CoreSettings) -> None:
        self._settings = settings
        self._simulator_adapter = None
        self._opcua_adapter = None

        if settings.simulator_enabled:
            from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
            from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

            self._simulator_adapter = SimulatorAdapter(settings=settings)

            # Override endpoint to point to local simulator OPC-UA server
            sim_endpoint = f"opc.tcp://localhost:{settings.simulator_port}"
            sim_settings = settings.model_copy(update={"opcua_endpoint": sim_endpoint})
            self._opcua_adapter = OPCUAAdapter(settings=sim_settings)
        else:
            from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

            self._opcua_adapter = OPCUAAdapter(settings=settings)

    @property
    def telemetry_source(self):
        """Return the TelemetrySource adapter (always OPCUAAdapter)."""
        return self._opcua_adapter

    @property
    def control_writer(self):
        """Return the ControlWriter adapter (always OPCUAAdapter)."""
        return self._opcua_adapter

    @property
    def tag_browser(self):
        """Return the TagBrowser adapter (always OPCUAAdapter)."""
        return self._opcua_adapter

    @property
    def simulator_adapter(self):
        """Return the SimulatorAdapter if simulator is enabled, else None."""
        return self._simulator_adapter

    @property
    def opcua_adapter(self):
        """Return the OPCUAAdapter (always available)."""
        return self._opcua_adapter
```

- [ ] **Step 3.4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_adapter_factory.py -v`
Expected: PASS

Note: Some existing tests in `TestAdapterFactoryOPCUA` should still pass since the OPC-UA-only path (simulator_enabled=False) is unchanged. The tests that checked `tag_browser` raises RuntimeError need to be removed since `tag_browser` is now always available.

- [ ] **Step 3.5: Update the OPC-UA mode tests**

The existing `TestAdapterFactoryOPCUA` tests should remain mostly unchanged. Remove or update the test that asserts `tag_browser` raises when simulator is enabled:

```python
class TestAdapterFactoryOPCUA:
    def test_telemetry_source_returns_opcua_when_simulator_disabled(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=False,
        )  # type: ignore[call-arg]
        factory = AdapterFactory(settings)
        source = factory.telemetry_source
        assert isinstance(source, OPCUAAdapter)

    def test_control_writer_returns_opcua_when_simulator_disabled(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=False,
        )  # type: ignore[call-arg]
        factory = AdapterFactory(settings)
        writer = factory.control_writer
        assert isinstance(writer, OPCUAAdapter)

    def test_tag_browser_returns_opcua(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=False,
        )  # type: ignore[call-arg]
        factory = AdapterFactory(settings)
        browser = factory.tag_browser
        assert isinstance(browser, OPCUAAdapter)

    def test_opcua_adapter_is_same_instance(self):
        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=False,
        )  # type: ignore[call-arg]
        factory = AdapterFactory(settings)
        assert factory.telemetry_source is factory.control_writer

    def test_simulator_adapter_is_none(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert factory.simulator_adapter is None

    def test_opcua_adapter_property(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert factory.opcua_adapter is not None
```

- [ ] **Step 3.6: Run all factory tests**

Run: `uv run pytest tests/core/unit/test_adapter_factory.py -v`
Expected: PASS

- [ ] **Step 3.7: Commit**

`feat(factory): create both SimulatorAdapter and OPCUAAdapter when simulator enabled`

---

## Task 4: Config Update — Add opcua_retry_max_s

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/config.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py`
- Test: `tests/core/unit/test_config.py` (or existing config test file)

### Overview
Add `opcua_retry_max_s` to `CoreSettings` and use it in `OPCUAAdapter._BACKOFF_MAX_S`.

- [ ] **Step 4.1: Write the failing test — config has opcua_retry_max_s**

```python
# tests/core/unit/test_config.py (append or create)
"""Tests for CoreSettings configuration."""
from smart_pid_core.config import CoreSettings


class TestCoreSettingsOPCUA:
    def test_opcua_retry_max_s_default(self) -> None:
        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
        )  # type: ignore[call-arg]
        assert settings.opcua_retry_max_s == 30.0

    def test_opcua_retry_max_s_override(self) -> None:
        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            opcua_retry_max_s=10.0,
        )  # type: ignore[call-arg]
        assert settings.opcua_retry_max_s == 10.0
```

- [ ] **Step 4.2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_config.py::TestCoreSettingsOPCUA -v`
Expected: FAIL (opcua_retry_max_s not in CoreSettings)

- [ ] **Step 4.3: Add opcua_retry_max_s to CoreSettings**

```python
# packages/smart_pid_core/src/smart_pid_core/config.py
# In CoreSettings class, under OPC-UA section:
    # OPC-UA
    opcua_endpoint: str = "opc.tcp://localhost:4840"
    opcua_timeout_s: int = 5
    opcua_retry_max_s: float = 30.0
```

- [ ] **Step 4.4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_config.py::TestCoreSettingsOPCUA -v`
Expected: PASS

- [ ] **Step 4.5: Write the failing test — OPCUAAdapter uses retry_max_s from settings**

```python
# tests/core/unit/test_opcua_adapter.py (append)

class TestOPCUAAdapterBackoff:
    def test_backoff_max_from_settings(self) -> None:
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings(opcua_retry_max_s=15.0)
        adapter = OPCUAAdapter(settings=settings)
        assert adapter._backoff_max_s == 15.0

    def test_backoff_max_default(self) -> None:
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings()
        adapter = OPCUAAdapter(settings=settings)
        assert adapter._backoff_max_s == 30.0
```

- [ ] **Step 4.6: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_opcua_adapter.py::TestOPCUAAdapterBackoff -v`
Expected: FAIL (OPCUAAdapter uses hardcoded _BACKOFF_MAX_S = 60.0)

- [ ] **Step 4.7: Modify OPCUAAdapter to use settings.opcua_retry_max_s**

In `OPCUAAdapter.__init__`, replace the class constant usage with an instance variable:

```python
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
        self._client = None
        self._controllers: dict[int, dict[str, str]] = {}
```

In `_connection_loop`, change `self._BACKOFF_MAX_S` to `self._backoff_max_s`:

```python
                backoff_s = min(backoff_s * 2, self._backoff_max_s)
```

- [ ] **Step 4.8: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_opcua_adapter.py -v`
Expected: PASS

- [ ] **Step 4.9: Commit**

`feat(config): add opcua_retry_max_s setting and use in OPCUAAdapter backoff`

---

## Task 5: main.py Wiring — Startup/Shutdown Order

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py`

### Overview
When simulator is enabled, the startup order must be:
1. Start SimulatorAdapter (which starts OPCUAServer on `:simulator_port`)
2. Register controllers on SimulatorAdapter (creates OPC-UA nodes)
3. Start OPCUAAdapter (connects to localhost:simulator_port)
4. Register controllers on OPCUAAdapter with node IDs from SimulatorAdapter's OPCUAServer

Shutdown: stop OPCUAAdapter first, then SimulatorAdapter.

- [ ] **Step 5.1: Write the failing test — main wiring integration**

```python
# tests/core/integration/test_main_wiring.py
"""Integration test for main.py adapter wiring."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from smart_pid_core.config import CoreSettings


class TestMainAdapterWiring:
    @pytest.mark.asyncio
    async def test_simulator_mode_starts_both_adapters(self, tmp_path) -> None:
        """Verify that in simulator mode, both SimulatorAdapter and OPCUAAdapter start."""
        settings = CoreSettings(
            jwt_secret="test-secret-key-minimum-32-bytes!",
            simulator_enabled=True,
            simulator_port=48450,
            db_path=tmp_path / "test.spid",
            api_port=18001,
            zmq_publish_port=15555,
        )  # type: ignore[call-arg]

        from smart_pid_core.adapters.factory import AdapterFactory

        factory = AdapterFactory(settings)
        assert factory.simulator_adapter is not None
        assert factory.opcua_adapter is not None

        # Verify OPCUAAdapter endpoint points to simulator
        assert f":{settings.simulator_port}" in factory.opcua_adapter.endpoint
```

- [ ] **Step 5.2: Run test to verify it passes (factory already wired)**

Run: `uv run pytest tests/core/integration/test_main_wiring.py -v`
Expected: PASS (factory from Task 3 already creates both)

- [ ] **Step 5.3: Modify main.py run_daemon — simulator + OPC-UA wiring**

Replace the adapter startup section (lines ~111-136) in `main.py`:

```python
    # Phase 3b+4b: Adapter factory (simulator or OPC-UA)
    adapter_factory = AdapterFactory(settings)
    simulator_adapter = adapter_factory.simulator_adapter
    opcua_adapter = adapter_factory.opcua_adapter

    if simulator_adapter is not None:
        # Register controllers on SimulatorAdapter FIRST (creates OPC-UA nodes)
        controllers = await repo.list_all()
        for ctrl in controllers:
            simulator_adapter.register_controller(ctrl.id)
        # Start SimulatorAdapter (starts embedded OPC-UA server)
        simulator_adapter.start()
        logger.info("simulator_started", port=settings.simulator_port)

        # Now register OPC-UA node IDs on OPCUAAdapter
        for ctrl in controllers:
            node_ids = simulator_adapter.opcua_server.controller_node_ids.get(ctrl.id, {})
            if node_ids:
                opcua_adapter.register_controller(
                    controller_id=ctrl.id,
                    node_id_pv=node_ids["pv"],
                    node_id_sp=node_ids["sp"],
                    node_id_co=node_ids["co"],
                )
        # Start OPCUAAdapter (connects to local simulator OPC-UA server)
        opcua_adapter.start()
        logger.info("opcua_adapter_started", endpoint=opcua_adapter.endpoint)
    elif opcua_adapter is not None:
        # Production mode: register from tag_bindings stored in DB
        controllers = await repo.list_all()
        for ctrl in controllers:
            tb = ctrl.tag_bindings
            if tb.node_id_pv:
                opcua_adapter.register_controller(
                    controller_id=ctrl.id,
                    node_id_pv=tb.node_id_pv,
                    node_id_sp=tb.node_id_sp,
                    node_id_co=tb.node_id_co,
                    node_id_integral=tb.node_id_integral,
                )
        opcua_adapter.start()
        logger.info("opcua_adapter_started", endpoint=settings.opcua_endpoint)
```

Update the shutdown section (after `await server_task`):

```python
    # Graceful shutdown in correct order
    server.should_exit = True
    await server_task
    await telemetry_pub.stop()
    # Stop OPC-UA client BEFORE simulator (client depends on server)
    if opcua_adapter is not None:
        opcua_adapter.stop()
    if simulator_adapter is not None:
        simulator_adapter.stop()
    alarm_worker.stop()
    loop_manager.stop_all()
    bus.stop()
    logger.info("daemon_stopped")
```

- [ ] **Step 5.4: Run test to verify wiring is correct**

Run: `uv run pytest tests/core/integration/test_main_wiring.py -v`
Expected: PASS

- [ ] **Step 5.5: Run all existing tests to verify nothing breaks**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: PASS (no regressions)

- [ ] **Step 5.6: Commit**

`feat(main): wire SimulatorAdapter + OPCUAAdapter startup/shutdown order`

---

## Task 6: Integration Test — Closed-Loop OPC-UA

**Files:**
- Create: `tests/core/integration/test_opcua_fullstack.py`

### Overview
End-to-end test: SimulatorAdapter running process model + OPCUAServer, OPCUAAdapter as client. Write CO via OPCUAAdapter, verify PV changes in OPC-UA nodes. This validates the complete signal path: `PID write_output → OPCUAAdapter → OPC-UA → SimulatorAdapter callback → ProcessModel → _tick → OPC-UA nodes → OPCUAAdapter read_telemetry`.

- [ ] **Step 6.1: Write the integration test**

```python
# tests/core/integration/test_opcua_fullstack.py
"""Integration test — closed-loop OPC-UA: Simulator + OPCUAServer + OPCUAAdapter."""
from __future__ import annotations

import time

import pytest

from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ConnectionState, ProcessPresetName


@pytest.fixture
def sim_settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
        simulator_port=48460,
    )  # type: ignore[call-arg]


@pytest.fixture
def client_settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        opcua_endpoint="opc.tcp://localhost:48460",
        opcua_retry_max_s=5.0,
    )  # type: ignore[call-arg]


@pytest.fixture
def simulator(sim_settings: CoreSettings):
    """Start SimulatorAdapter with embedded OPC-UA server."""
    sim = SimulatorAdapter(settings=sim_settings)
    sim.register_controller(1)
    sim.set_preset(1, ProcessPresetName.FLOW)
    sim.start()
    yield sim
    sim.stop()


@pytest.fixture
def opcua_client(simulator: SimulatorAdapter, client_settings: CoreSettings):
    """OPCUAAdapter connected to the SimulatorAdapter's OPC-UA server."""
    node_ids = simulator.opcua_server.controller_node_ids[1]
    client = OPCUAAdapter(settings=client_settings)
    client.register_controller(
        controller_id=1,
        node_id_pv=node_ids["pv"],
        node_id_sp=node_ids["sp"],
        node_id_co=node_ids["co"],
    )
    client.start()
    assert client.wait_connected(timeout_s=5.0), "OPCUAAdapter failed to connect"
    yield client
    client.stop()


class TestOPCUAFullStack:
    def test_client_connects_to_simulator_server(
        self, opcua_client: OPCUAAdapter,
    ) -> None:
        assert opcua_client.state == ConnectionState.ONLINE

    def test_read_telemetry_returns_valid_frame(
        self, opcua_client: OPCUAAdapter,
    ) -> None:
        time.sleep(0.2)  # Let a few ticks run
        frame = opcua_client.read_telemetry(1)
        assert frame.controller_id == 1
        assert isinstance(frame.pv, float)
        assert isinstance(frame.sp, float)
        assert isinstance(frame.co, float)

    def test_write_co_affects_pv(
        self, opcua_client: OPCUAAdapter,
    ) -> None:
        """Write a non-zero CO, wait for process model to respond, verify PV changes."""
        # Read initial PV
        time.sleep(0.2)
        initial_frame = opcua_client.read_telemetry(1)
        initial_pv = initial_frame.pv

        # Write a step change in CO
        opcua_client.write_output(controller_id=1, co=50.0)
        time.sleep(1.0)  # Wait for process model to respond

        # Read PV after step change
        frame = opcua_client.read_telemetry(1)
        # For FLOW preset (gain=1.2, tau1=3.0), PV should have moved from initial
        # After 1s with CO=50, PV should be noticeably different from initial (which was ~0)
        assert frame.pv != pytest.approx(initial_pv, abs=0.1), (
            f"PV should have changed from {initial_pv}, but got {frame.pv}"
        )

    def test_write_sp_affects_simulator(
        self, simulator: SimulatorAdapter, opcua_client: OPCUAAdapter,
    ) -> None:
        """Write SP via OPC-UA, verify SimulatorAdapter sees the new SP."""
        opcua_client.write_parameter(controller_id=1, param="sp", value=75.0)
        time.sleep(0.5)

        with simulator._lock:
            assert simulator._controllers[1].sp == pytest.approx(75.0, abs=0.5)

    def test_browse_simulator_namespace(
        self, opcua_client: OPCUAAdapter,
    ) -> None:
        """TagBrowser should see SmartPID namespace from simulator OPC-UA server."""
        # Browse Objects folder
        children = opcua_client.browse_children("i=85")
        names = [c["display_name"] for c in children]
        assert "SmartPID" in names

    def test_browse_controller_folder(
        self, opcua_client: OPCUAAdapter,
    ) -> None:
        """Browse into SmartPID/Controllers/CTRL_1 and see PV/SP/CO nodes."""
        children = opcua_client.browse_children("i=85")
        smartpid = next(c for c in children if c["display_name"] == "SmartPID")
        controllers = opcua_client.browse_children(smartpid["node_id"])
        ctrl_folder = next(
            c for c in controllers if c["display_name"] == "Controllers",
        )
        ctrl_nodes = opcua_client.browse_children(ctrl_folder["node_id"])
        ctrl1 = next(c for c in ctrl_nodes if c["display_name"] == "CTRL_1")
        tags = opcua_client.browse_children(ctrl1["node_id"])
        tag_names = {t["display_name"] for t in tags}
        assert {"PV", "SP", "CO", "Mode", "Status"} <= tag_names

    def test_search_finds_pv_node(
        self, opcua_client: OPCUAAdapter,
    ) -> None:
        """Search for 'PV' should find the simulator's PV node."""
        results = opcua_client.search("PV")
        assert len(results) >= 1
        assert any(r["display_name"] == "PV" for r in results)


class TestOPCUAFullStackMultiController:
    def test_two_controllers_independent(self, sim_settings: CoreSettings) -> None:
        """Register two controllers, verify independent PV/CO tracking."""
        sim = SimulatorAdapter(settings=sim_settings)
        sim.register_controller(1)
        sim.register_controller(2)
        sim.set_preset(1, ProcessPresetName.FLOW)
        sim.set_preset(2, ProcessPresetName.TEMPERATURE)
        sim.start()
        try:
            node_ids_1 = sim.opcua_server.controller_node_ids[1]
            node_ids_2 = sim.opcua_server.controller_node_ids[2]

            client_settings = CoreSettings(
                jwt_secret="test-secret-key-minimum-32-bytes!",
                opcua_endpoint=f"opc.tcp://localhost:{sim_settings.simulator_port}",
                opcua_retry_max_s=5.0,
            )  # type: ignore[call-arg]
            client = OPCUAAdapter(settings=client_settings)
            client.register_controller(
                controller_id=1,
                node_id_pv=node_ids_1["pv"],
                node_id_sp=node_ids_1["sp"],
                node_id_co=node_ids_1["co"],
            )
            client.register_controller(
                controller_id=2,
                node_id_pv=node_ids_2["pv"],
                node_id_sp=node_ids_2["sp"],
                node_id_co=node_ids_2["co"],
            )
            client.start()
            try:
                assert client.wait_connected(timeout_s=5.0)

                # Write different CO values
                client.write_output(controller_id=1, co=30.0)
                client.write_output(controller_id=2, co=70.0)
                time.sleep(1.0)

                frame1 = client.read_telemetry(1)
                frame2 = client.read_telemetry(2)

                # Both should show non-zero PV, but different values
                # (different presets, different CO)
                assert frame1.co == pytest.approx(30.0, abs=1.0)
                assert frame2.co == pytest.approx(70.0, abs=1.0)
            finally:
                client.stop()
        finally:
            sim.stop()
```

- [ ] **Step 6.2: Run test to verify it passes**

Run: `uv run pytest tests/core/integration/test_opcua_fullstack.py -v`
Expected: PASS (all 8 tests)

- [ ] **Step 6.3: Commit**

`test(integration): add closed-loop OPC-UA full-stack tests`

---

## Task 7: Remove SimpleQueue (Optional Cleanup)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`
- Modify: `tests/core/unit/test_simulator_adapter.py`

### Overview
Now that all I/O goes through OPC-UA, the `SimpleQueue[TelemetryFrame]` in SimulatorAdapter is redundant. Remove it to simplify the code. This task is optional and can be deferred if other consumers still depend on the queue.

- [ ] **Step 7.1: Check for queue consumers**

Search the codebase for references to `simulator_adapter.queue` or `SimulatorAdapter.queue`:

```bash
rg "\.queue" packages/ tests/ --glob "*.py" | grep -i simul
```

If no external consumers exist, proceed with removal.

- [ ] **Step 7.2: Write the test that verifies queue is gone**

```python
# tests/core/unit/test_simulator_adapter.py (replace TestSimulatorAdapterInit)

class TestSimulatorAdapterInit:
    def test_not_running_initially(self, adapter: SimulatorAdapter) -> None:
        assert not adapter.is_running

    def test_has_opcua_server(self, adapter: SimulatorAdapter) -> None:
        assert adapter.opcua_server is not None

    def test_no_queue_attribute(self, adapter: SimulatorAdapter) -> None:
        """SimpleQueue removed — all I/O goes through OPC-UA."""
        assert not hasattr(adapter, "queue")
```

- [ ] **Step 7.3: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py::TestSimulatorAdapterInit::test_no_queue_attribute -v`
Expected: FAIL (queue still exists)

- [ ] **Step 7.4: Remove SimpleQueue from SimulatorAdapter**

In `simulator_adapter.py`:
1. Remove `from queue import SimpleQueue` import
2. Remove `self._queue: SimpleQueue[TelemetryFrame] = SimpleQueue()` from `__init__`
3. Remove the `queue` property
4. In `_tick()`, remove the `self._queue.put(frame)` line and the `TelemetryFrame` construction (only keep the `update_values` call)
5. Remove `TelemetryFrame` and `datetime` imports if no longer needed

Updated `_tick`:
```python
    def _tick(self, dt: float) -> None:
        with self._lock:
            for ctrl in self._controllers.values():
                pv = ctrl.model.step(co=ctrl.last_co, dt=dt)
                if ctrl.step_active:
                    pv += ctrl.step_amplitude
                if ctrl.noise_active:
                    pv += random.gauss(0, ctrl.noise_amplitude)

                # Write to OPC-UA nodes (non-blocking, fire-and-forget)
                self._opcua_server.update_values(
                    controller_id=ctrl.controller_id,
                    pv=pv,
                    sp=ctrl.sp,
                    co=ctrl.last_co,
                )
```

- [ ] **Step 7.5: Update tests — remove queue-related assertions**

Remove `TestSimulatorAdapterInit.test_queue_is_simple_queue` and update
`TestSimulatorAdapterRunning.test_start_stop_produces_telemetry` to verify via OPC-UA
instead of queue:

```python
class TestSimulatorAdapterRunning:
    def test_start_stop_lifecycle(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.start()
        assert adapter.is_running
        assert adapter.opcua_server.is_running
        time.sleep(0.15)
        adapter.stop()
        assert not adapter.is_running
        assert not adapter.opcua_server.is_running

    def test_write_parameter_is_noop(self, adapter: SimulatorAdapter) -> None:
        """write_parameter satisfies ControlWriter protocol but is a no-op for simulator."""
        adapter.register_controller(1)
        adapter.write_parameter(1, "gain", 2.0)  # Should not raise
```

- [ ] **Step 7.6: Run all tests**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: PASS

- [ ] **Step 7.7: Commit**

`refactor(simulator): remove SimpleQueue, all I/O goes through OPC-UA`

---

## Task 8: Lint + Type-Check Sweep

**Files:**
- All modified files from Tasks 1-7

### Overview
Final pass: run ruff, mypy, and fix any issues.

- [ ] **Step 8.1: Run ruff**

```bash
uv run --with ruff ruff check packages/smart_pid_core/src/smart_pid_core/adapters/ tests/core/
```

Fix any issues (import ordering, line length, etc.)

- [ ] **Step 8.2: Run mypy**

```bash
uv run mypy packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py
uv run mypy packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py
uv run mypy packages/smart_pid_core/src/smart_pid_core/adapters/factory.py
uv run mypy packages/smart_pid_core/src/smart_pid_core/config.py
uv run mypy packages/smart_pid_core/src/smart_pid_core/main.py
```

Fix any type errors.

- [ ] **Step 8.3: Run full test suite**

```bash
uv run pytest tests/ -v --timeout=60
```

Expected: PASS (all tests including new ones)

- [ ] **Step 8.4: Commit**

`chore(phase3b4b): fix lint and type errors from OPC-UA full-stack implementation`

---

## Summary

| Task | Component | Tests | Files Created | Files Modified |
|------|-----------|-------|---------------|----------------|
| 1 | OPCUAServer wrapper | ~10 | 1 source + 1 test | — |
| 2 | SimulatorAdapter refactor | ~8 | — | 1 source + 1 test |
| 3 | AdapterFactory update | ~6 | — | 1 source + 1 test |
| 4 | Config + backoff | ~4 | — | 2 source + 2 test |
| 5 | main.py wiring | ~1 | 1 test | 1 source |
| 6 | Integration test | ~8 | 1 test | — |
| 7 | Remove SimpleQueue | ~3 | — | 1 source + 1 test |
| 8 | Lint + type sweep | — | — | All modified |

**Total: ~40 new tests, 1 new source file, 4 modified source files**

### Key Architecture Decisions

1. **OPCUAAdapter is the SOLE I/O path** — both in simulator and production mode. This eliminates the dual-path complexity and ensures the OPC-UA code path is always exercised.

2. **SimulatorAdapter owns the OPCUAServer** — the server lifecycle is tied to the simulator. When the simulator starts, the OPC-UA server starts. When it stops, the server stops.

3. **Callback-based CO/SP propagation** — when OPCUAAdapter writes CO to the OPC-UA server, the `_WriteHandler` fires a callback that updates `_ControllerSim.last_co`. This replaces the direct `write_output()` call path.

4. **SimpleQueue removal** — the queue was a transitional mechanism. With OPC-UA as the data path, it becomes redundant. Removal is a separate task to keep the diff clean.

5. **pydantic `model_copy`** — AdapterFactory uses `settings.model_copy(update={"opcua_endpoint": sim_endpoint})` to create a settings variant for the local OPCUAAdapter, avoiding mutation of the original settings.
