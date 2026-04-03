# Phase 3b — OPC-UA I/O Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an OPC-UA adapter that reads/writes real process data via asyncua, with auto-reconnect and tag browsing, replacing the NotImplementedError stub in AdapterFactory.

**Architecture:** OPCUAAdapter implements TelemetrySource + ControlWriter + TagBrowser protocols. Runs asyncua.Client in a daemon thread with its own asyncio event loop. Connection state machine with exponential backoff. Test fixture uses embedded asyncua.Server.

**Tech Stack:** asyncua>=1.1, asyncio, threading, pytest-asyncio

---

### Task 1: ConnectionState Enum Update + OPCUAAdapter Skeleton

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/enums.py:46-49`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py`
- Create: `tests/core/unit/test_opcua_adapter.py`

- [ ] **Step 1: Update ConnectionState enum to include CONNECTING**

The existing `ConnectionState` enum has OFFLINE, ONLINE, RECONNECTING. Add CONNECTING:

```python
# In packages/smart_pid_domain/src/smart_pid_domain/enums.py
# Replace the ConnectionState class:

class ConnectionState(StrEnum):
    OFFLINE = "OFFLINE"
    CONNECTING = "CONNECTING"
    ONLINE = "ONLINE"
    RECONNECTING = "RECONNECTING"
```

- [ ] **Step 2: Write failing test for OPCUAAdapter instantiation**

```python
# tests/core/unit/test_opcua_adapter.py
"""Unit tests for OPCUAAdapter."""
from __future__ import annotations

import pytest

from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ConnectionState


def _make_settings(**overrides) -> CoreSettings:
    defaults = {"jwt_secret": "test-secret-key-minimum-32-bytes!"}
    defaults.update(overrides)
    return CoreSettings(**defaults)  # type: ignore[call-arg]


class TestOPCUAAdapterInit:
    def test_initial_state_is_offline(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings(opcua_endpoint="opc.tcp://localhost:4840")
        adapter = OPCUAAdapter(settings=settings)
        assert adapter.state == ConnectionState.OFFLINE
        assert not adapter.is_connected

    def test_endpoint_from_settings(self):
        from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

        settings = _make_settings(opcua_endpoint="opc.tcp://10.0.0.1:4840")
        adapter = OPCUAAdapter(settings=settings)
        assert adapter.endpoint == "opc.tcp://10.0.0.1:4840"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_opcua_adapter.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError

- [ ] **Step 4: Implement OPCUAAdapter skeleton**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_opcua_adapter.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/enums.py \
  packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py \
  tests/core/unit/test_opcua_adapter.py
git commit -m "feat(opcua): add ConnectionState.CONNECTING + OPCUAAdapter skeleton"
```

---

### Task 2: OPC-UA Test Server Fixture

**Files:**
- Create: `tests/core/fixtures/__init__.py`
- Create: `tests/core/fixtures/opcua_server.py`
- Create: `tests/core/integration/test_opcua_connection.py`

- [ ] **Step 1: Write the test server fixture**

```python
# tests/core/fixtures/__init__.py
```

```python
# tests/core/fixtures/opcua_server.py
"""Embedded asyncua.Server for OPC-UA integration testing."""
from __future__ import annotations

import asyncio
import threading

from asyncua import Server, ua


class OPCUATestServer:
    """Lightweight OPC-UA server for testing.

    Creates a namespace with Float nodes (PV, SP, CO) and Int node (Mode)
    for one controller.
    """

    URI = "urn:smartpid:test"

    def __init__(self, port: int = 4841) -> None:
        self._port = port
        self._server: Server | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self.node_ids: dict[str, str] = {}

    @property
    def endpoint(self) -> str:
        return f"opc.tcp://localhost:{self._port}"

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="opcua-test-server")
        self._thread.start()
        if not self._ready.wait(timeout=10.0):
            raise RuntimeError("OPC-UA test server failed to start")

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._setup_and_serve())

    async def _setup_and_serve(self) -> None:
        self._server = Server()
        await self._server.init()
        self._server.set_endpoint(self.endpoint)
        self._server.set_server_name("SmartPID Test Server")

        idx = await self._server.register_namespace(self.URI)

        objects = self._server.nodes.objects
        ctrl_folder = await objects.add_folder(idx, "Controller1")

        pv_node = await ctrl_folder.add_variable(idx, "PV", 50.0, ua.VariantType.Float)
        sp_node = await ctrl_folder.add_variable(idx, "SP", 50.0, ua.VariantType.Float)
        co_node = await ctrl_folder.add_variable(idx, "CO", 0.0, ua.VariantType.Float)
        mode_node = await ctrl_folder.add_variable(idx, "Mode", 0, ua.VariantType.Int32)

        await pv_node.set_writable()
        await sp_node.set_writable()
        await co_node.set_writable()
        await mode_node.set_writable()

        self.node_ids = {
            "pv": pv_node.nodeid.to_string(),
            "sp": sp_node.nodeid.to_string(),
            "co": co_node.nodeid.to_string(),
            "mode": mode_node.nodeid.to_string(),
        }

        async with self._server:
            self._ready.set()
            while True:
                await asyncio.sleep(0.1)
```

- [ ] **Step 2: Write failing integration test for connect/disconnect**

```python
# tests/core/integration/test_opcua_connection.py
"""Integration tests for OPC-UA connection lifecycle."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ConnectionState
from tests.core.fixtures.opcua_server import OPCUATestServer


@pytest.fixture(scope="module")
def opcua_server():
    server = OPCUATestServer(port=48410)
    server.start()
    yield server
    server.stop()


def _make_settings(endpoint: str) -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        opcua_endpoint=endpoint,
    )  # type: ignore[call-arg]


class TestOPCUAConnection:
    def test_connect_reaches_online(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            # Wait for connection
            adapter.wait_connected(timeout_s=5.0)
            assert adapter.state == ConnectionState.ONLINE
            assert adapter.is_connected
        finally:
            adapter.stop()
        assert adapter.state == ConnectionState.OFFLINE

    def test_connect_to_bad_endpoint_stays_reconnecting(self):
        settings = _make_settings("opc.tcp://localhost:19999")
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            import time
            time.sleep(2.0)
            assert adapter.state in {ConnectionState.CONNECTING, ConnectionState.RECONNECTING}
        finally:
            adapter.stop()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/core/integration/test_opcua_connection.py -v`
Expected: FAIL — `start()`, `stop()`, `wait_connected()` not implemented

- [ ] **Step 4: Implement connect/disconnect lifecycle**

Add to `OPCUAAdapter` class in `opcua_adapter.py`:

```python
    def start(self) -> None:
        """Start the OPC-UA client in a background daemon thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_event_loop, daemon=True, name="opcua-client",
        )
        self._thread.start()
        logger.info("opcua_adapter_started", endpoint=self._endpoint)

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
        import time
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.state == ConnectionState.ONLINE:
                return True
            time.sleep(0.05)
        return False

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
                logger.info("opcua_connected", endpoint=self._endpoint)

                # Watchdog loop
                await self._watchdog_loop()

            except Exception as exc:
                logger.warning("opcua_connection_failed", error=str(exc), backoff=backoff_s)
                with self._lock:
                    self._state = ConnectionState.RECONNECTING
                if self._client is not None:
                    try:
                        await self._client.disconnect()
                    except Exception:
                        pass
                    self._client = None

                # Backoff wait
                for _ in range(int(backoff_s * 10)):
                    if self._stop_event.is_set():
                        return
                    await asyncio.sleep(0.1)
                backoff_s = min(backoff_s * 2, self._BACKOFF_MAX_S)

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
                logger.warning("opcua_watchdog_failed", error=str(exc))
                raise  # Triggers reconnect in _connection_loop
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/core/integration/test_opcua_connection.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add tests/core/fixtures/ \
  tests/core/integration/test_opcua_connection.py \
  packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py
git commit -m "feat(opcua): connection lifecycle with auto-reconnect and test server fixture"
```

---

### Task 3: Register Controllers + Batch Read (TelemetrySource)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py`
- Modify: `tests/core/integration/test_opcua_connection.py`

- [ ] **Step 1: Write failing test for register + read_telemetry**

Append to `tests/core/integration/test_opcua_connection.py`:

```python
class TestOPCUATelemetryRead:
    def test_read_telemetry_returns_frame(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv=opcua_server.node_ids["pv"],
            node_id_sp=opcua_server.node_ids["sp"],
            node_id_co=opcua_server.node_ids["co"],
        )
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            frame = adapter.read_telemetry(controller_id=1)
            assert frame.controller_id == 1
            assert isinstance(frame.pv, float)
            assert isinstance(frame.sp, float)
            assert isinstance(frame.co, float)
            assert frame.pv == pytest.approx(50.0, abs=0.1)
            assert frame.sp == pytest.approx(50.0, abs=0.1)
        finally:
            adapter.stop()

    def test_read_telemetry_unknown_controller_raises(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            with pytest.raises(KeyError):
                adapter.read_telemetry(controller_id=999)
        finally:
            adapter.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/integration/test_opcua_connection.py::TestOPCUATelemetryRead -v`
Expected: FAIL — `register_controller` / `read_telemetry` not found

- [ ] **Step 3: Implement register_controller and read_telemetry**

Add to `OPCUAAdapter`:

```python
    def register_controller(
        self,
        controller_id: int,
        node_id_pv: str,
        node_id_sp: str,
        node_id_co: str,
        node_id_integral: str = "",
    ) -> None:
        """Register a controller's OPC-UA node mappings."""
        with self._lock:
            self._controllers[controller_id] = {
                "pv": node_id_pv,
                "sp": node_id_sp,
                "co": node_id_co,
                "integral": node_id_integral,
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
        self, client, controller_id: int, nodes: dict[str, str]
    ) -> TelemetryFrame:
        """Async batch read of OPC-UA nodes."""
        from asyncua import ua

        node_ids_to_read = []
        keys = []
        for key in ("pv", "sp", "co"):
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
        result = dict(zip(keys, values))

        return TelemetryFrame(
            controller_id=controller_id,
            pv=float(result.get("pv", 0.0)),
            sp=float(result.get("sp", 0.0)),
            co=float(result.get("co", 0.0)),
            integral_val=float(result.get("integral", 0.0)),
            timestamp=datetime.now(UTC),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/integration/test_opcua_connection.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py \
  tests/core/integration/test_opcua_connection.py
git commit -m "feat(opcua): register controllers + batch read TelemetrySource"
```

---

### Task 4: ControlWriter — write_output and write_parameter

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py`
- Modify: `tests/core/integration/test_opcua_connection.py`

- [ ] **Step 1: Write failing test for write_output**

Append to `tests/core/integration/test_opcua_connection.py`:

```python
class TestOPCUAControlWriter:
    def test_write_output_updates_co_node(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv=opcua_server.node_ids["pv"],
            node_id_sp=opcua_server.node_ids["sp"],
            node_id_co=opcua_server.node_ids["co"],
        )
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            adapter.write_output(controller_id=1, co=75.5)
            # Read back to verify
            frame = adapter.read_telemetry(controller_id=1)
            assert frame.co == pytest.approx(75.5, abs=0.1)
        finally:
            adapter.stop()

    def test_write_parameter_updates_sp_node(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.register_controller(
            controller_id=1,
            node_id_pv=opcua_server.node_ids["pv"],
            node_id_sp=opcua_server.node_ids["sp"],
            node_id_co=opcua_server.node_ids["co"],
        )
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            adapter.write_parameter(controller_id=1, param="sp", value=65.0)
            frame = adapter.read_telemetry(controller_id=1)
            assert frame.sp == pytest.approx(65.0, abs=0.1)
        finally:
            adapter.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/integration/test_opcua_connection.py::TestOPCUAControlWriter -v`
Expected: FAIL — `write_output` / `write_parameter` not found

- [ ] **Step 3: Implement write_output and write_parameter**

Add to `OPCUAAdapter`:

```python
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

    async def _async_write_value(self, client, node_id: str, value: float) -> None:
        """Write a float value to an OPC-UA node."""
        from asyncua import ua

        node = client.get_node(node_id)
        dv = ua.DataValue(ua.Variant(value, ua.VariantType.Float))
        await node.write_value(dv)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/integration/test_opcua_connection.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py \
  tests/core/integration/test_opcua_connection.py
git commit -m "feat(opcua): ControlWriter — write_output and write_parameter"
```

---

### Task 5: TagBrowser — browse_children and search

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py`
- Create: `tests/core/integration/test_opcua_browse.py`

- [ ] **Step 1: Write failing test for browse_children and search**

```python
# tests/core/integration/test_opcua_browse.py
"""Integration tests for OPC-UA tag browsing."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
from smart_pid_core.config import CoreSettings
from tests.core.fixtures.opcua_server import OPCUATestServer


@pytest.fixture(scope="module")
def opcua_server():
    server = OPCUATestServer(port=48411)
    server.start()
    yield server
    server.stop()


def _make_settings(endpoint: str) -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        opcua_endpoint=endpoint,
    )  # type: ignore[call-arg]


class TestTagBrowser:
    def test_browse_root_objects(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            # Browse Objects folder (i=85)
            children = adapter.browse_children("i=85")
            names = [c["display_name"] for c in children]
            assert "Controller1" in names
        finally:
            adapter.stop()

    def test_browse_controller_folder(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            children = adapter.browse_children("i=85")
            ctrl_folder = next(c for c in children if c["display_name"] == "Controller1")
            tags = adapter.browse_children(ctrl_folder["node_id"])
            tag_names = {t["display_name"] for t in tags}
            assert {"PV", "SP", "CO", "Mode"} <= tag_names
        finally:
            adapter.stop()

    def test_search_by_name(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            results = adapter.search("PV")
            assert len(results) >= 1
            assert any(r["display_name"] == "PV" for r in results)
        finally:
            adapter.stop()

    def test_search_no_results(self, opcua_server: OPCUATestServer):
        settings = _make_settings(opcua_server.endpoint)
        adapter = OPCUAAdapter(settings=settings)
        adapter.start()
        try:
            adapter.wait_connected(timeout_s=5.0)
            results = adapter.search("NONEXISTENT_TAG_XYZ")
            assert results == []
        finally:
            adapter.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/integration/test_opcua_browse.py -v`
Expected: FAIL — `browse_children` / `search` not found

- [ ] **Step 3: Implement browse_children and search**

Add to `OPCUAAdapter`:

```python
    def browse_children(self, node_id: str) -> list[dict[str, str]]:
        """List children of an OPC-UA node. Returns list of {node_id, display_name, node_class}."""
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
                if query_lower in display_name.lower():
                    node_class = await child.read_node_class()
                    results.append({
                        "node_id": child.nodeid.to_string(),
                        "display_name": display_name,
                        "node_class": node_class.name,
                    })
                # Recurse into folders/objects
                node_class = await child.read_node_class()
                if node_class in {ua.NodeClass.Object, ua.NodeClass.ObjectType}:
                    await _walk(child, depth + 1)

        objects = client.get_node(ua.ObjectIds.ObjectsFolder)
        await _walk(objects)
        return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/integration/test_opcua_browse.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py \
  tests/core/integration/test_opcua_browse.py
git commit -m "feat(opcua): TagBrowser — browse_children and recursive search"
```

---

### Task 6: AdapterFactory Integration

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/factory.py`
- Modify: `tests/core/unit/test_adapter_factory.py`

- [ ] **Step 1: Write failing test for OPC-UA factory path**

Append to `tests/core/unit/test_adapter_factory.py` (read existing file first to understand patterns):

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_adapter_factory.py::TestAdapterFactoryOPCUA -v`
Expected: FAIL — factory still raises NotImplementedError

- [ ] **Step 3: Update AdapterFactory**

Replace the contents of `packages/smart_pid_core/src/smart_pid_core/adapters/factory.py`:

```python
"""AdapterFactory — centralized DI based on CoreSettings."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_core.config import CoreSettings


class AdapterFactory:
    """Creates and caches adapter instances based on configuration.

    When simulator is enabled, SimulatorAdapter serves as TelemetrySource + ControlWriter.
    Otherwise, OPCUAAdapter serves as TelemetrySource + ControlWriter + TagBrowser.
    """

    def __init__(self, settings: CoreSettings) -> None:
        self._settings = settings
        self._simulator_adapter = None
        self._opcua_adapter = None

        if settings.simulator_enabled:
            from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter

            self._simulator_adapter = SimulatorAdapter(settings=settings)
        else:
            from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter

            self._opcua_adapter = OPCUAAdapter(settings=settings)

    @property
    def telemetry_source(self):
        """Return the TelemetrySource adapter."""
        if self._settings.simulator_enabled:
            return self._simulator_adapter
        return self._opcua_adapter

    @property
    def control_writer(self):
        """Return the ControlWriter adapter."""
        if self._settings.simulator_enabled:
            return self._simulator_adapter
        return self._opcua_adapter

    @property
    def tag_browser(self):
        """Return the TagBrowser adapter (OPC-UA only)."""
        if self._opcua_adapter is None:
            raise RuntimeError("TagBrowser only available when OPC-UA is active (simulator disabled)")
        return self._opcua_adapter

    @property
    def simulator_adapter(self):
        """Return the SimulatorAdapter if simulator is enabled, else None."""
        return self._simulator_adapter

    @property
    def opcua_adapter(self):
        """Return the OPCUAAdapter if OPC-UA is active, else None."""
        return self._opcua_adapter
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_adapter_factory.py -v`
Expected: all passed (both old simulator tests and new OPCUA tests)

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/factory.py \
  tests/core/unit/test_adapter_factory.py
git commit -m "feat(opcua): wire OPCUAAdapter into AdapterFactory"
```

---

### Task 7: REST Endpoints for OPC-UA Status + Browse

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/opcua.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`
- Create: `packages/smart_pid_domain/src/smart_pid_domain/dtos/opcua.py`
- Create: `tests/core/integration/test_api_opcua.py`

- [ ] **Step 1: Create OPC-UA DTOs**

```python
# packages/smart_pid_domain/src/smart_pid_domain/dtos/opcua.py
"""OPC-UA request/response DTOs."""
from __future__ import annotations

from pydantic import BaseModel

from smart_pid_domain.enums import ConnectionState  # noqa: TC001


class OPCUAStatusResponse(BaseModel):
    state: ConnectionState
    endpoint: str


class OPCUANodeInfo(BaseModel):
    node_id: str
    display_name: str
    node_class: str


class OPCUABrowseResponse(BaseModel):
    parent_node_id: str
    children: list[OPCUANodeInfo]


class OPCUASearchResponse(BaseModel):
    query: str
    results: list[OPCUANodeInfo]
```

- [ ] **Step 2: Create opcua router**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/opcua.py
"""OPC-UA browse and status router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_current_user,
    get_opcua_adapter,
)
from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001
from smart_pid_domain.dtos.opcua import (
    OPCUABrowseResponse,
    OPCUANodeInfo,
    OPCUASearchResponse,
    OPCUAStatusResponse,
)

router = APIRouter()


@router.get("/status", response_model=OPCUAStatusResponse)
async def get_status(
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
) -> OPCUAStatusResponse:
    return OPCUAStatusResponse(state=adapter.state, endpoint=adapter.endpoint)


@router.get("/browse/{node_id:path}", response_model=OPCUABrowseResponse)
async def browse_children(
    node_id: str,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
) -> OPCUABrowseResponse:
    try:
        children = adapter.browse_children(node_id)
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return OPCUABrowseResponse(
        parent_node_id=node_id,
        children=[OPCUANodeInfo(**c) for c in children],
    )


@router.get("/search", response_model=OPCUASearchResponse)
async def search_tags(
    q: Annotated[str, Query(min_length=1, max_length=200)],
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
) -> OPCUASearchResponse:
    try:
        results = adapter.search(q)
    except ConnectionError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return OPCUASearchResponse(
        query=q,
        results=[OPCUANodeInfo(**r) for r in results],
    )


@router.post("/connect")
async def force_reconnect(
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[OPCUAAdapter, Depends(get_opcua_adapter)],
) -> dict[str, str]:
    adapter.stop()
    adapter.start()
    return {"detail": "Reconnection initiated"}
```

- [ ] **Step 3: Add get_opcua_adapter dependency**

Add to `dependencies.py`:

```python
def get_opcua_adapter(request: Request):
    adapter = getattr(request.app.state, "opcua_adapter", None)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OPC-UA not available (simulator mode active)",
        )
    return adapter
```

- [ ] **Step 4: Register opcua router in app.py**

Add import and router registration in `app.py`:

```python
# In imports section, add:
from smart_pid_core.adapters.inbound.api.routers import opcua

# In create_app function signature, add parameter:
def create_app(
    *,
    repo: SQLiteRepository,
    historian: SQLiteHistorian,
    user_repo: UserRepository,
    loop_manager: LoopManager,
    settings: CoreSettings,
    simulator_adapter=None,
    opcua_adapter=None,
) -> FastAPI:

# After app.state.simulator_adapter, add:
    app.state.opcua_adapter = opcua_adapter

# After simulator router, add:
    app.include_router(opcua.router, prefix="/opcua", tags=["opcua"])
```

- [ ] **Step 5: Write integration test for REST endpoints**

```python
# tests/core/integration/test_api_opcua.py
"""Integration tests for OPC-UA REST API."""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token, hash_password
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ConnectionState


@pytest.fixture
def mock_opcua_adapter():
    adapter = MagicMock()
    adapter.state = ConnectionState.ONLINE
    adapter.endpoint = "opc.tcp://localhost:4840"
    adapter.browse_children.return_value = [
        {"node_id": "ns=2;i=1", "display_name": "PV", "node_class": "Variable"},
        {"node_id": "ns=2;i=2", "display_name": "SP", "node_class": "Variable"},
    ]
    adapter.search.return_value = [
        {"node_id": "ns=2;i=1", "display_name": "PV", "node_class": "Variable"},
    ]
    return adapter


@pytest.fixture
async def opcua_api_deps(tmp_path, mock_opcua_adapter):
    import uuid

    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    user_repo = UserRepository(repo.db)
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(jwt_secret="test-secret-key-minimum-32-bytes!")  # type: ignore[call-arg]

    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, "admin")

    app = create_app(
        repo=repo,
        historian=historian,
        user_repo=user_repo,
        loop_manager=loop_manager,
        settings=settings,
        opcua_adapter=mock_opcua_adapter,
    )
    token = create_access_token(
        user_id=1, username="admin", role="admin", secret=settings.jwt_secret,
    )
    headers = {"Authorization": f"Bearer {token}"}

    yield app, headers, mock_opcua_adapter
    loop_manager.stop_all()
    bus.stop()


@pytest.fixture
async def opcua_client(opcua_api_deps):
    app, headers, _ = opcua_api_deps
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, headers


class TestOPCUAAPI:
    @pytest.mark.asyncio
    async def test_get_status(self, opcua_client):
        client, headers = opcua_client
        resp = await client.get("/opcua/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "ONLINE"
        assert data["endpoint"] == "opc.tcp://localhost:4840"

    @pytest.mark.asyncio
    async def test_browse_children(self, opcua_client):
        client, headers = opcua_client
        resp = await client.get("/opcua/browse/i=85", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["parent_node_id"] == "i=85"
        assert len(data["children"]) == 2

    @pytest.mark.asyncio
    async def test_search(self, opcua_client):
        client, headers = opcua_client
        resp = await client.get("/opcua/search", params={"q": "PV"}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "PV"
        assert len(data["results"]) == 1
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_api_opcua.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/opcua.py \
  packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/opcua.py \
  packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py \
  packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py \
  tests/core/integration/test_api_opcua.py
git commit -m "feat(opcua): REST endpoints for status, browse, search + DTOs"
```

---

### Task 8: Wire OPCUAAdapter into Daemon Lifecycle

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py`

- [ ] **Step 1: Update main.py to start/stop OPCUAAdapter and register controllers**

In `main.py`, update the `run_daemon` function. After the `adapter_factory` creation block, add OPC-UA lifecycle:

```python
    # Phase 3b: OPC-UA adapter lifecycle
    opcua_adapter = adapter_factory.opcua_adapter
    if opcua_adapter is not None:
        controllers = await repo.list_all()
        for ctrl in controllers:
            tb = ctrl.tag_bindings
            if tb.node_id_pv:  # Only register if tags are configured
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

Update the `create_app` call to pass `opcua_adapter`:

```python
    app = create_app(
        repo=repo,
        historian=historian,
        user_repo=user_repo,
        loop_manager=loop_manager,
        settings=settings,
        simulator_adapter=simulator_adapter,
        opcua_adapter=opcua_adapter,
    )
```

Update shutdown section:

```python
    # Graceful shutdown in correct order
    server.should_exit = True
    await server_task
    await telemetry_pub.stop()
    if simulator_adapter is not None:
        simulator_adapter.stop()
    if opcua_adapter is not None:
        opcua_adapter.stop()
    loop_manager.stop_all()
    bus.stop()
    logger.info("daemon_stopped")
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 3: Lint**

Run: `uv run --with ruff ruff check .`
Expected: no errors

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/main.py
git commit -m "feat(opcua): wire OPCUAAdapter into daemon lifecycle (start/stop/register)"
```
