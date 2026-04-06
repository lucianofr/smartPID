# OPC-UA Server Independent Control — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple OPC-UA server lifecycle from simulator loop, fix default port to 4849, and add UI controls/indicator for OPC-UA server status.

**Architecture:** The `SimulatorAdapter` gains separate `start_opcua()`/`stop_opcua()` methods. Backend `main.py` calls them independently. New REST endpoints expose OPC-UA start/stop/status. HMI simulator page gets indicator + buttons wired through `APIClient`.

**Tech Stack:** Python 3.13, PySide6, FastAPI, pydantic v2, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-04-06-opcua-server-independent-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `packages/smart_pid_core/src/smart_pid_core/config.py` | Fix default port 4841→4849 |
| Modify | `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py` | Fix default port 4841→4849 |
| Modify | `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py` | Decouple OPC-UA lifecycle from sim loop |
| Modify | `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py` | Add OPC-UA start/stop/status endpoints |
| Modify | `packages/smart_pid_core/src/smart_pid_core/main.py` | Call start_opcua() and stop_opcua() independently |
| Modify | `packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py` | Add OPCUAServerStatus DTO |
| Modify | `packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py` | Re-export OPCUAServerStatus |
| Modify | `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py` | Add OPC-UA indicator + start/stop buttons, fix port default |
| Modify | `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py` | Add OPC-UA start/stop/status client methods |
| Modify | `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` | Wire new signals to API calls |
| Modify | `tests/hmi/pages/test_simulator_page.py` | Fix port assertion + new OPC-UA UI tests |
| Modify | `tests/core/unit/test_simulator_adapter.py` | Tests for decoupled lifecycle |
| Modify | `CLAUDE.md` | Fix documented default port |

---

### Task 1: Fix Default Port (4841 → 4849)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/config.py:44`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py:26`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py:206`
- Modify: `tests/hmi/pages/test_simulator_page.py:228`
- Modify: `CLAUDE.md:99`

- [ ] **Step 1: Update config.py default**

In `packages/smart_pid_core/src/smart_pid_core/config.py`, change line 44:

```python
# Before:
simulator_port: int = 4841
# After:
simulator_port: int = 4849
```

- [ ] **Step 2: Update opcua_server.py default**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py`, change line 26:

```python
# Before:
def __init__(self, port: int = 4841) -> None:
# After:
def __init__(self, port: int = 4849) -> None:
```

- [ ] **Step 3: Update simulator_page.py default**

In `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`, change line 206:

```python
# Before:
self._opcua_port_spin.setValue(4841)
# After:
self._opcua_port_spin.setValue(4849)
```

- [ ] **Step 4: Update test assertion**

In `tests/hmi/pages/test_simulator_page.py`, change line 228:

```python
# Before:
assert spin.value() == 4841
# After:
assert spin.value() == 4849
```

- [ ] **Step 5: Update CLAUDE.md**

In `CLAUDE.md`, change line 99:

```markdown
# Before:
- `SPID_SIMULATOR_ENABLED` / `SPID_SIMULATOR_PORT` — Default: false / 4841
# After:
- `SPID_SIMULATOR_ENABLED` / `SPID_SIMULATOR_PORT` — Default: false / 4849
```

- [ ] **Step 6: Run affected tests**

Run: `uv run pytest tests/hmi/pages/test_simulator_page.py -v -k "opcua_port"`
Expected: PASS — `test_opcua_port_default` passes with 4849

Run: `uv run pytest tests/core/unit/test_config.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/config.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py \
       tests/hmi/pages/test_simulator_page.py \
       CLAUDE.md
git commit -m "fix: align default simulator port to 4849 across codebase"
```

---

### Task 2: Add OPCUAServerStatus DTO

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py`
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py`
- Test: `tests/domain/test_simulator_dtos.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/domain/test_simulator_dtos.py`:

```python
def test_opcua_server_status_dto():
    from smart_pid_domain.dtos.simulator import OPCUAServerStatus

    status = OPCUAServerStatus(running=True, port=4849, endpoint="opc.tcp://0.0.0.0:4849")
    assert status.running is True
    assert status.port == 4849
    assert status.endpoint == "opc.tcp://0.0.0.0:4849"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_simulator_dtos.py::test_opcua_server_status_dto -v`
Expected: FAIL — `ImportError: cannot import name 'OPCUAServerStatus'`

- [ ] **Step 3: Add the DTO**

At the end of `packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py`, add:

```python
class OPCUAServerStatus(BaseModel):
    running: bool
    port: int
    endpoint: str
```

- [ ] **Step 4: Re-export in `__init__.py`**

In `packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py`:

Add to the import block (after the existing simulator imports around line 49):
```python
from smart_pid_domain.dtos.simulator import (
    ControllerSimStatus,
    OPCUAServerStatus,  # ← ADD THIS
    SimulatorDisturbanceRequest,
    ...
)
```

Add `"OPCUAServerStatus"` to the `__all__` list (alphabetically, between `"OPCUABrowseResponse"` and `"OPCUANodeInfo"`).

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/domain/test_simulator_dtos.py::test_opcua_server_status_dto -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py \
       packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py \
       tests/domain/test_simulator_dtos.py
git commit -m "feat(domain): add OPCUAServerStatus DTO"
```

---

### Task 3: Decouple OPC-UA Lifecycle in SimulatorAdapter

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`
- Test: `tests/core/unit/test_simulator_adapter.py`

- [ ] **Step 1: Write failing tests for decoupled lifecycle**

Add to `tests/core/unit/test_simulator_adapter.py`:

```python
def test_start_opcua_independent(sim_adapter):
    """OPC-UA server can be started without simulation loop."""
    sim_adapter.start_opcua()
    assert sim_adapter.opcua_running is True
    assert sim_adapter.is_running is False  # sim loop NOT started
    sim_adapter.stop_opcua()
    assert sim_adapter.opcua_running is False


def test_stop_opcua_independent(sim_adapter):
    """Stopping OPC-UA does not stop simulation loop."""
    sim_adapter.start_opcua()
    sim_adapter.start()
    assert sim_adapter.is_running is True
    assert sim_adapter.opcua_running is True
    sim_adapter.stop_opcua()
    assert sim_adapter.opcua_running is False
    assert sim_adapter.is_running is True  # sim loop still running
    sim_adapter.stop()


def test_start_stop_sim_loop_independent(sim_adapter):
    """Starting/stopping sim loop does not affect OPC-UA server."""
    sim_adapter.start_opcua()
    assert sim_adapter.opcua_running is True
    sim_adapter.start()
    assert sim_adapter.is_running is True
    sim_adapter.stop()
    assert sim_adapter.is_running is False
    assert sim_adapter.opcua_running is True  # OPC-UA still running
    sim_adapter.stop_opcua()


def test_opcua_port_property(sim_adapter):
    assert sim_adapter.opcua_port == sim_adapter._settings.simulator_port


def test_opcua_endpoint_property(sim_adapter):
    port = sim_adapter._settings.simulator_port
    assert sim_adapter.opcua_endpoint == f"opc.tcp://0.0.0.0:{port}"
```

Note: `sim_adapter` fixture should already exist in the test file. If not, check and use the existing fixture name.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py -v -k "opcua_independent or opcua_port or opcua_endpoint or sim_loop_independent"`
Expected: FAIL — `AttributeError: 'SimulatorAdapter' object has no attribute 'start_opcua'`

- [ ] **Step 3: Implement decoupled lifecycle**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`, add these methods to `SimulatorAdapter`:

```python
def start_opcua(self) -> None:
    """Start only the OPC-UA server (without simulation loop)."""
    self._opcua_server.start()

def stop_opcua(self) -> None:
    """Stop only the OPC-UA server (without affecting simulation loop)."""
    self._opcua_server.stop()

@property
def opcua_running(self) -> bool:
    return self._opcua_server.is_running

@property
def opcua_port(self) -> int:
    return self._opcua_server.port

@property
def opcua_endpoint(self) -> str:
    return self._opcua_server.endpoint
```

Then modify `start()` (line 81-88) to **remove** the `self._opcua_server.start()` call:

```python
def start(self) -> None:
    if self._thread is not None and self._thread.is_alive():
        return
    self._stop_event.clear()
    # OPC-UA server is managed independently via start_opcua()/stop_opcua()
    self._thread = threading.Thread(target=self._run_loop, daemon=True, name="simulator")
    self._thread.start()
    logger.info("Simulator started (interval=%dms)", self._settings.simulator_interval_ms)
```

And modify `stop()` (line 90-96) to **remove** the `self._opcua_server.stop()` call:

```python
def stop(self) -> None:
    self._stop_event.set()
    if self._thread is not None:
        self._thread.join(timeout=2.0)
        self._thread = None
    # OPC-UA server is managed independently via start_opcua()/stop_opcua()
    logger.info("Simulator stopped")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py \
       tests/core/unit/test_simulator_adapter.py
git commit -m "feat(core): decouple OPC-UA server lifecycle from simulator loop"
```

---

### Task 4: Update Backend main.py for Independent Lifecycle

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py:191-202` (startup) and `357-360` (shutdown)

- [ ] **Step 1: Update startup sequence**

In `packages/smart_pid_core/src/smart_pid_core/main.py`, replace lines 191-200 (the `if simulator_adapter is not None` block):

```python
    if simulator_adapter is not None:
        controllers = await repo.list_all()
        for ctrl in controllers:
            simulator_adapter.register_controller(
                ctrl.id,
                pv_min=ctrl.pv_scale.eu_min,
                pv_max=ctrl.pv_scale.eu_max,
            )
        simulator_adapter.start_opcua()
        logger.info("opcua_server_started", port=settings.simulator_port)
        simulator_adapter.start()
        logger.info("simulator_started", port=settings.simulator_port)
    else:
        logger.info("simulator_disabled", hint="set SPID_SIMULATOR_ENABLED=true to enable")
```

- [ ] **Step 2: Update shutdown sequence**

In `packages/smart_pid_core/src/smart_pid_core/main.py`, replace lines 357-360:

```python
    # Before:
    if opcua_adapter is not None:
        opcua_adapter.stop()
    if simulator_adapter is not None:
        simulator_adapter.stop()

    # After:
    if opcua_adapter is not None:
        opcua_adapter.stop()
    if simulator_adapter is not None:
        simulator_adapter.stop()
        simulator_adapter.stop_opcua()
```

- [ ] **Step 3: Run integration test**

Run: `uv run pytest tests/core/integration/test_main_wiring.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/main.py
git commit -m "feat(core): use independent OPC-UA lifecycle in daemon startup/shutdown"
```

---

### Task 5: Add OPC-UA REST Endpoints

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py`
- Test: `tests/core/integration/test_api_simulator.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/core/integration/test_api_simulator.py`:

```python
def test_opcua_status(auth_client, sim_adapter):
    """GET /simulator/opcua/status returns OPC-UA server status."""
    resp = auth_client.get("/simulator/opcua/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "running" in data
    assert "port" in data
    assert "endpoint" in data


def test_opcua_start_stop(auth_client, sim_adapter):
    """POST /simulator/opcua/start and /stop control OPC-UA server."""
    resp = auth_client.post("/simulator/opcua/start")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    status = auth_client.get("/simulator/opcua/status")
    assert status.json()["running"] is True

    resp = auth_client.post("/simulator/opcua/stop")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
```

Note: Check the existing test file fixtures (`auth_client`, `sim_adapter`) and adapt the test to match. The key assertion patterns remain the same.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_api_simulator.py -v -k "opcua_status or opcua_start"`
Expected: FAIL — 404 Not Found (endpoints don't exist yet)

- [ ] **Step 3: Add endpoints to simulator router**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py`, add the import at the top:

```python
from smart_pid_domain.dtos.simulator import (
    AutoDisturbanceRequest,
    AutoSPRequest,
    ControllerSimStatus,
    OPCUAServerStatus,  # ← ADD
    SimulatorDisturbanceRequest,
    ...
)
```

Then add these endpoints at the end of the file (before any auto-sp/auto-disturbance endpoints, or at the very end):

```python
@router.get("/opcua/status", response_model=OPCUAServerStatus)
async def get_opcua_status(
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> OPCUAServerStatus:
    return OPCUAServerStatus(
        running=adapter.opcua_running,
        port=adapter.opcua_port,
        endpoint=adapter.opcua_endpoint,
    )


@router.post("/opcua/start", response_model=CommandResponse)
async def start_opcua_server(
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.start_opcua()
    return CommandResponse(ok=True, detail="OPC-UA server started")


@router.post("/opcua/stop", response_model=CommandResponse)
async def stop_opcua_server(
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.stop_opcua()
    return CommandResponse(ok=True, detail="OPC-UA server stopped")
```

**IMPORTANT:** These `/opcua/*` routes MUST be defined BEFORE any `/{controller_id}/*` routes in the file, otherwise FastAPI will match `opcua` as a `controller_id` path parameter. Move them above the `/{controller_id}/pid/enable` route.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_api_simulator.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py \
       tests/core/integration/test_api_simulator.py
git commit -m "feat(api): add OPC-UA server start/stop/status endpoints"
```

---

### Task 6: Add APIClient Methods for OPC-UA Control

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`
- Test: `tests/hmi/services/test_api_client.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/hmi/services/test_api_client.py`:

```python
def test_start_opcua_server(api_client, mock_transport):
    """APIClient.start_opcua_server() calls POST /simulator/opcua/start."""
    mock_transport.add_response(200, {"ok": True, "detail": "OPC-UA server started"})
    result = api_client.start_opcua_server()
    assert result.ok is True


def test_stop_opcua_server(api_client, mock_transport):
    """APIClient.stop_opcua_server() calls POST /simulator/opcua/stop."""
    mock_transport.add_response(200, {"ok": True, "detail": "OPC-UA server stopped"})
    result = api_client.stop_opcua_server()
    assert result.ok is True


def test_get_opcua_status(api_client, mock_transport):
    """APIClient.get_opcua_status() calls GET /simulator/opcua/status."""
    mock_transport.add_response(200, {
        "running": True, "port": 4849, "endpoint": "opc.tcp://0.0.0.0:4849",
    })
    result = api_client.get_opcua_status()
    assert result["running"] is True
    assert result["port"] == 4849
```

Note: Adapt fixture names (`api_client`, `mock_transport`) to match the existing test file patterns. Check the file to see how other similar tests (like `test_start_simulator`) are structured and follow the same pattern.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/services/test_api_client.py -v -k "opcua_server or opcua_status"`
Expected: FAIL — `AttributeError: 'APIClient' object has no attribute 'start_opcua_server'`

- [ ] **Step 3: Add API client methods**

In `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`, add after the existing `stop_simulator` method (around line 148):

```python
    def start_opcua_server(self) -> CommandResponse:
        resp = self._http.post("/simulator/opcua/start", headers=self._headers())
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def stop_opcua_server(self) -> CommandResponse:
        resp = self._http.post("/simulator/opcua/stop", headers=self._headers())
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def get_opcua_status(self) -> dict:
        resp = self._http.get("/simulator/opcua/status", headers=self._headers())
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/hmi/services/test_api_client.py -v -k "opcua"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py \
       tests/hmi/services/test_api_client.py
git commit -m "feat(hmi): add APIClient methods for OPC-UA server control"
```

---

### Task 7: Add OPC-UA Indicator and Controls to SimulatorPage

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`
- Test: `tests/hmi/pages/test_simulator_page.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/hmi/pages/test_simulator_page.py`:

```python
class TestSimulatorPageOPCUAControls:
    def test_opcua_status_label_exists(self, pid_page: SimulatorPage) -> None:
        label = pid_page.findChild(QLabel, "opcua_status_label")
        assert label is not None
        assert "Stopped" in label.text()

    def test_opcua_start_button_exists(self, pid_page: SimulatorPage) -> None:
        btn = pid_page.findChild(QPushButton, "opcua_start_btn")
        assert btn is not None
        assert btn.isEnabled()

    def test_opcua_stop_button_exists(self, pid_page: SimulatorPage) -> None:
        btn = pid_page.findChild(QPushButton, "opcua_stop_btn")
        assert btn is not None
        assert not btn.isEnabled()

    def test_set_opcua_running_true(self, pid_page: SimulatorPage) -> None:
        pid_page.set_opcua_running(True)
        label = pid_page.findChild(QLabel, "opcua_status_label")
        assert "Running" in label.text()
        start_btn = pid_page.findChild(QPushButton, "opcua_start_btn")
        stop_btn = pid_page.findChild(QPushButton, "opcua_stop_btn")
        assert not start_btn.isEnabled()
        assert stop_btn.isEnabled()

    def test_set_opcua_running_false(self, pid_page: SimulatorPage) -> None:
        pid_page.set_opcua_running(True)
        pid_page.set_opcua_running(False)
        label = pid_page.findChild(QLabel, "opcua_status_label")
        assert "Stopped" in label.text()
        start_btn = pid_page.findChild(QPushButton, "opcua_start_btn")
        stop_btn = pid_page.findChild(QPushButton, "opcua_stop_btn")
        assert start_btn.isEnabled()
        assert not stop_btn.isEnabled()

    def test_opcua_start_signal(self, pid_page: SimulatorPage, qtbot) -> None:
        with qtbot.waitSignal(pid_page.opcua_start_requested, timeout=1000):
            pid_page._on_opcua_start()

    def test_opcua_stop_signal(self, pid_page: SimulatorPage, qtbot) -> None:
        with qtbot.waitSignal(pid_page.opcua_stop_requested, timeout=1000):
            pid_page._on_opcua_stop()
```

Add `QLabel` to the imports at top of test file if not already imported:
```python
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QGroupBox, QLabel, QPushButton
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/pages/test_simulator_page.py -v -k "TestSimulatorPageOPCUAControls"`
Expected: FAIL — `findChild` returns None or missing signals/methods

- [ ] **Step 3: Add signals, widgets, and methods to SimulatorPage**

In `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`:

**Add new signals** (after `opcua_config_changed` on line 52):

```python
    opcua_start_requested = Signal()
    opcua_stop_requested = Signal()
```

**Replace the OPC-UA Server group** (lines 196-213) with the enhanced version that includes status indicator and start/stop buttons:

```python
        # OPC-UA Server Config group
        opcua_group = QGroupBox("OPC-UA Server")
        opcua_layout = QVBoxLayout(opcua_group)

        # Status indicator row
        opcua_status_row = QHBoxLayout()
        opcua_status_row.addWidget(QLabel("Status:"))
        self._opcua_status_label = QLabel("Stopped")
        self._opcua_status_label.setObjectName("opcua_status_label")
        self._opcua_status_label.setStyleSheet(
            f"font-weight: bold; color: {theme.alarm_critical};"
        )
        opcua_status_row.addWidget(self._opcua_status_label)
        opcua_status_row.addStretch()
        opcua_layout.addLayout(opcua_status_row)

        # Start/Stop buttons row
        opcua_btn_row = QHBoxLayout()
        self._opcua_start_btn = QPushButton("Start")
        self._opcua_start_btn.setObjectName("opcua_start_btn")
        self._opcua_start_btn.clicked.connect(self._on_opcua_start)
        opcua_btn_row.addWidget(self._opcua_start_btn)
        self._opcua_stop_btn = QPushButton("Stop")
        self._opcua_stop_btn.setObjectName("opcua_stop_btn")
        self._opcua_stop_btn.setEnabled(False)
        self._opcua_stop_btn.clicked.connect(self._on_opcua_stop)
        opcua_btn_row.addWidget(self._opcua_stop_btn)
        opcua_layout.addLayout(opcua_btn_row)

        # Endpoint config row
        endpoint_row = QHBoxLayout()
        endpoint_row.addWidget(QLabel("Endpoint:"))
        self._opcua_endpoint_label = QLabel("opc.tcp://0.0.0.0:")
        self._opcua_endpoint_label.setObjectName("opcua_endpoint_label")
        endpoint_row.addWidget(self._opcua_endpoint_label)
        self._opcua_port_spin = QDoubleSpinBox()
        self._opcua_port_spin.setObjectName("opcua_port_spin")
        self._opcua_port_spin.setRange(1024, 65535)
        self._opcua_port_spin.setValue(4849)
        self._opcua_port_spin.setDecimals(0)
        endpoint_row.addWidget(self._opcua_port_spin, stretch=1)
        opcua_layout.addLayout(endpoint_row)
        opcua_apply = QPushButton("Apply")
        opcua_apply.setObjectName("opcua_apply_btn")
        opcua_apply.clicked.connect(self._on_opcua_apply)
        opcua_layout.addWidget(opcua_apply)
        right_col.addWidget(opcua_group)
```

**Add handler methods** (after `_on_opcua_apply` around line 548):

```python
    def _on_opcua_start(self) -> None:
        self.opcua_start_requested.emit()

    def _on_opcua_stop(self) -> None:
        self.opcua_stop_requested.emit()

    @Slot(bool)
    def set_opcua_running(self, running: bool) -> None:
        """Update OPC-UA status indicator and button states."""
        self._opcua_start_btn.setEnabled(not running)
        self._opcua_stop_btn.setEnabled(running)
        if running:
            self._opcua_status_label.setText("Running")
            self._opcua_status_label.setStyleSheet(
                f"font-weight: bold; color: {self._theme.bar_pv};"
            )
        else:
            self._opcua_status_label.setText("Stopped")
            self._opcua_status_label.setStyleSheet(
                f"font-weight: bold; color: {self._theme.alarm_critical};"
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/hmi/pages/test_simulator_page.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py \
       tests/hmi/pages/test_simulator_page.py
git commit -m "feat(hmi): add OPC-UA server status indicator and start/stop controls"
```

---

### Task 8: Wire OPC-UA Controls in MainWindow

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`

- [ ] **Step 1: Connect new signals**

In `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`, find the signal connections block (around lines 280-292) and add after `self._simulator_page.sim_stop_requested.connect(self._send_sim_stop)`:

```python
        self._simulator_page.opcua_start_requested.connect(self._send_opcua_start)
        self._simulator_page.opcua_stop_requested.connect(self._send_opcua_stop)
```

- [ ] **Step 2: Add handler methods**

Add after `_send_sim_stop` method (around line 609):

```python
    def _send_opcua_start(self) -> None:
        def do_start():
            try:
                self._api_client.start_opcua_server()
                QMetaObject.invokeMethod(
                    self._simulator_page, "set_opcua_running",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(bool, True),
                )
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_start, daemon=True).start()

    def _send_opcua_stop(self) -> None:
        def do_stop():
            try:
                self._api_client.stop_opcua_server()
                QMetaObject.invokeMethod(
                    self._simulator_page, "set_opcua_running",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(bool, False),
                )
            except Exception as e:
                self._api_error_signal.emit(str(e))
        threading.Thread(target=do_stop, daemon=True).start()
```

- [ ] **Step 3: Update `_check_simulator_available` to also set OPC-UA status**

Find `_check_simulator_available` (line 494) and update the inner logic to also check OPC-UA status. After the line that invokes `_enable_simulator`, add:

```python
                opcua_status = self._api_client.get_opcua_status()
                if opcua_status.get("running"):
                    QMetaObject.invokeMethod(
                        self._simulator_page, "set_opcua_running",
                        Qt.ConnectionType.QueuedConnection,
                        Q_ARG(bool, True),
                    )
```

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/main.py
git commit -m "feat(hmi): wire OPC-UA start/stop controls in MainWindow"
```

---

### Task 9: Final Integration Verification

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 2: Run linter**

Run: `uv run --with ruff ruff check .`
Expected: No errors

- [ ] **Step 3: Commit any lint fixes if needed**

```bash
git add -u
git commit -m "chore: lint fixes"
```
