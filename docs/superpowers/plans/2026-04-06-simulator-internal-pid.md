# Simulator Internal PID — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an internal PID controller to the simulator that reuses the existing `PIDEngine`, with OPC-UA exposure for SUPERVISORY mode testing.

**Architecture:** The `SimulatorAdapter` gains a `PIDEngine` instance and per-controller PID state. When enabled and in AUTO, the tick loop computes PID before the process model. Five new OPC-UA nodes per controller (Kp, Ti, Td, PID_Mode, PID_SP) allow external tuning. REST endpoints and HMI controls provide manual configuration.

**Tech Stack:** Python 3.13, PIDEngine (existing), asyncua (OPC-UA server), FastAPI (REST), PySide6 (HMI), pytest

**Spec:** `docs/superpowers/specs/2026-04-06-simulator-internal-pid-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py` | Modify | Add PID fields to `ControllerSimStatus`, new request DTOs |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py` | Modify | PIDEngine integration, new methods, tick loop |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py` | Modify | 5 new nodes, write handler expansion |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py` | Modify | 4 new REST endpoints |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py` | Modify | New simulator PID method signatures |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py` | Modify | New simulator PID API calls |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py` | Modify | Mock implementations |
| `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py` | Modify | "Internal PID" group |
| `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` | Modify | Wire new signals to API calls |
| `tests/core/unit/test_simulator_adapter.py` | Modify | PID-related unit tests |
| `tests/core/unit/test_opcua_server.py` | Create | OPC-UA node tests for PID params |
| `tests/core/integration/test_api_simulator.py` | Modify | REST endpoint tests |
| `tests/hmi/test_simulator_page.py` | Create | HMI PID group tests |

---

### Task 1: DTOs — Add PID fields to ControllerSimStatus and new request models

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py`
- Test: `tests/domain/test_simulator_dtos.py`

- [ ] **Step 1: Write the failing test**

Create `tests/domain/test_simulator_dtos.py`:

```python
"""Tests for simulator DTOs — PID fields."""
from __future__ import annotations

from smart_pid_domain.dtos.simulator import (
    ControllerSimStatus,
    SimulatorPIDEnableRequest,
    SimulatorPIDModeRequest,
    SimulatorPIDParamsRequest,
    SimulatorPIDStatusResponse,
)


class TestControllerSimStatusPIDFields:
    def test_defaults(self) -> None:
        status = ControllerSimStatus(
            preset="FLOW", gain=1.2, tau1=3.0, tau2=None, dead_time=1.0,
            step_active=False, step_amplitude=0.0,
            noise_active=False, noise_amplitude=0.0,
        )
        assert status.pid_enabled is False
        assert status.pid_kp == 1.0
        assert status.pid_ti == 10.0
        assert status.pid_td == 0.0
        assert status.pid_mode == 0
        assert status.pid_cv == 0.0

    def test_with_pid_values(self) -> None:
        status = ControllerSimStatus(
            preset="FLOW", gain=1.2, tau1=3.0, tau2=None, dead_time=1.0,
            step_active=False, step_amplitude=0.0,
            noise_active=False, noise_amplitude=0.0,
            pid_enabled=True, pid_kp=2.0, pid_ti=5.0, pid_td=1.0,
            pid_mode=1, pid_cv=42.0,
        )
        assert status.pid_enabled is True
        assert status.pid_kp == 2.0
        assert status.pid_cv == 42.0


class TestSimulatorPIDRequestDTOs:
    def test_enable_request(self) -> None:
        req = SimulatorPIDEnableRequest(controller_id=1, enabled=True)
        assert req.controller_id == 1
        assert req.enabled is True

    def test_params_request(self) -> None:
        req = SimulatorPIDParamsRequest(controller_id=1, kp=2.0, ti=5.0, td=1.0)
        assert req.kp == 2.0
        assert req.ti == 5.0

    def test_mode_request(self) -> None:
        req = SimulatorPIDModeRequest(controller_id=1, mode="AUTO")
        assert req.mode == "AUTO"

    def test_status_response(self) -> None:
        resp = SimulatorPIDStatusResponse(
            enabled=True, kp=1.0, ti=10.0, td=0.0, mode=1, cv=50.0,
        )
        assert resp.enabled is True
        assert resp.cv == 50.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_simulator_dtos.py -v`
Expected: FAIL — `SimulatorPIDEnableRequest` not found, `pid_enabled` field missing.

- [ ] **Step 3: Write the implementation**

Edit `packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py` — add PID fields to `ControllerSimStatus` and new request/response models:

```python
"""Simulator request/response DTOs."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from smart_pid_domain.enums import ProcessPresetName  # noqa: TC001 - pydantic needs runtime


class SimulatorPresetRequest(BaseModel):
    controller_id: int
    preset: ProcessPresetName


class SimulatorParametersRequest(BaseModel):
    controller_id: int
    gain: float
    tau1: float
    tau2: float | None = None
    dead_time: float


class SimulatorDisturbanceRequest(BaseModel):
    controller_id: int
    type: Literal["step", "noise"]
    amplitude: float


class ControllerSimStatus(BaseModel):
    preset: str
    gain: float
    tau1: float
    tau2: float | None
    dead_time: float
    step_active: bool
    step_amplitude: float
    noise_active: bool
    noise_amplitude: float
    # PID internal state
    pid_enabled: bool = False
    pid_kp: float = 1.0
    pid_ti: float = 10.0
    pid_td: float = 0.0
    pid_mode: int = 0  # 0=MAN, 1=AUTO
    pid_cv: float = 0.0


class SimulatorStatusResponse(BaseModel):
    enabled: bool
    controllers: dict[int, ControllerSimStatus] = {}


# --- PID control request/response DTOs ---

class SimulatorPIDEnableRequest(BaseModel):
    controller_id: int
    enabled: bool


class SimulatorPIDParamsRequest(BaseModel):
    controller_id: int
    kp: float
    ti: float
    td: float


class SimulatorPIDModeRequest(BaseModel):
    controller_id: int
    mode: Literal["MAN", "AUTO"]


class SimulatorPIDStatusResponse(BaseModel):
    enabled: bool
    kp: float
    ti: float
    td: float
    mode: int  # 0=MAN, 1=AUTO
    cv: float
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/test_simulator_dtos.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/domain/test_simulator_dtos.py packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py
git commit -m "feat(sim): add PID fields to ControllerSimStatus and new PID request DTOs"
```

---

### Task 2: SimulatorAdapter — PIDEngine integration and new methods

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`
- Modify: `tests/core/unit/test_simulator_adapter.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/unit/test_simulator_adapter.py`:

```python
from smart_pid_domain.models.controller import PIDParams


class TestSimulatorPIDInternal:
    """Tests for internal PID controller in simulator."""

    def test_pid_disabled_by_default(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        assert adapter._controllers[1].pid_enabled is False

    def test_enable_pid(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.enable_pid(1, enabled=True)
        assert adapter._controllers[1].pid_enabled is True

    def test_disable_pid(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.enable_pid(1, enabled=True)
        adapter.enable_pid(1, enabled=False)
        assert adapter._controllers[1].pid_enabled is False

    def test_set_pid_params(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_pid_params(1, kp=2.0, ti=5.0, td=1.0)
        p = adapter._controllers[1].pid_params
        assert p.gain == 2.0
        assert p.reset == 5.0
        assert p.rate == 1.0

    def test_set_pid_mode_auto(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_pid_mode(1, mode=1)
        assert adapter._controllers[1].pid_mode == 1

    def test_set_pid_mode_man(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_pid_mode(1, mode=1)
        adapter.set_pid_mode(1, mode=0)
        assert adapter._controllers[1].pid_mode == 0

    def test_get_pid_status(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.enable_pid(1, enabled=True)
        adapter.set_pid_params(1, kp=3.0, ti=8.0, td=0.5)
        adapter.set_pid_mode(1, mode=1)
        status = adapter.get_pid_status(1)
        assert status["enabled"] is True
        assert status["kp"] == 3.0
        assert status["ti"] == 8.0
        assert status["td"] == 0.5
        assert status["mode"] == 1

    def test_tick_pid_disabled_co_unchanged(self, adapter: SimulatorAdapter) -> None:
        """When PID disabled, CO is not modified by tick."""
        adapter.register_controller(1)
        adapter.write_output(1, 25.0)
        adapter._tick(0.1)
        assert adapter._controllers[1].last_co == 25.0

    def test_tick_pid_man_mode_co_unchanged(self, adapter: SimulatorAdapter) -> None:
        """When PID enabled but in MAN mode, CO is not modified by tick."""
        adapter.register_controller(1)
        adapter.enable_pid(1, enabled=True)
        adapter.set_pid_mode(1, mode=0)  # MAN
        adapter.write_output(1, 25.0)
        adapter._tick(0.1)
        assert adapter._controllers[1].last_co == 25.0

    def test_tick_pid_auto_computes_co(self, adapter: SimulatorAdapter) -> None:
        """When PID enabled in AUTO, CO is computed by PIDEngine."""
        adapter.register_controller(1)
        adapter.enable_pid(1, enabled=True)
        adapter.set_pid_mode(1, mode=1)  # AUTO
        adapter._controllers[1].sp = 50.0
        adapter._controllers[1].last_co = 0.0
        # Run several ticks — CO should move toward correcting the error
        for _ in range(10):
            adapter._tick(0.1)
        co = adapter._controllers[1].last_co
        assert co > 0.0, f"Expected CO > 0 after PID AUTO ticks, got {co}"

    def test_controller_sim_status_includes_pid(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.enable_pid(1, enabled=True)
        adapter.set_pid_params(1, kp=2.0, ti=5.0, td=0.5)
        status = adapter.get_controller_status(1)
        assert status.pid_enabled is True
        assert status.pid_kp == 2.0
        assert status.pid_ti == 5.0
        assert status.pid_td == 0.5

    def test_on_opcua_write_kp(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter._on_opcua_write(1, "kp", 3.5)
        assert adapter._controllers[1].pid_params.gain == 3.5

    def test_on_opcua_write_ti(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter._on_opcua_write(1, "ti", 8.0)
        assert adapter._controllers[1].pid_params.reset == 8.0

    def test_on_opcua_write_td(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter._on_opcua_write(1, "td", 2.0)
        assert adapter._controllers[1].pid_params.rate == 2.0

    def test_on_opcua_write_pid_mode(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter._on_opcua_write(1, "pid_mode", 1.0)
        assert adapter._controllers[1].pid_mode == 1

    def test_on_opcua_write_pid_sp(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter._on_opcua_write(1, "pid_sp", 75.0)
        assert adapter._controllers[1].sp == 75.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py::TestSimulatorPIDInternal -v`
Expected: FAIL — `pid_enabled` not an attribute of `_ControllerSim`, `enable_pid` method doesn't exist.

- [ ] **Step 3: Implement _ControllerSim changes and SimulatorAdapter methods**

Edit `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`:

Add imports at the top:

```python
from smart_pid_core.domain.services.pid_engine import PIDEngine, PIDState
from smart_pid_domain.models.controller import PIDParams
from smart_pid_domain.models.signal import FFSignal
```

Add fields to `_ControllerSim`:

```python
@dataclass
class _ControllerSim:
    """Mutable state for one simulated controller."""

    controller_id: int
    model: ProcessModel = field(default_factory=lambda: ProcessModel(
        gain=1.2, tau1=3.0, tau2=None, dead_time=1.0,
    ))
    preset_name: str = "FLOW"
    gain: float = 1.2
    tau1: float = 3.0
    tau2: float | None = None
    dead_time: float = 1.0
    last_co: float = 0.0
    sp: float = 50.0
    step_active: bool = False
    step_amplitude: float = 0.0
    noise_active: bool = False
    noise_amplitude: float = 0.0
    # Internal PID
    pid_enabled: bool = False
    pid_params: PIDParams = field(default_factory=PIDParams)
    pid_state: PIDState = field(default_factory=PIDState)
    pid_mode: int = 0  # 0=MAN, 1=AUTO
```

Add `self._pid_engine = PIDEngine()` in `SimulatorAdapter.__init__()`.

Add new methods to `SimulatorAdapter`:

```python
def enable_pid(self, controller_id: int, enabled: bool) -> None:
    with self._lock:
        ctrl = self._controllers[controller_id]
        ctrl.pid_enabled = enabled
        if enabled:
            # Bumpless: initialize PID state to current CO
            ctrl.pid_state = self._pid_engine.bumpless_transfer(
                ctrl.pid_state, current_pv=0.0, current_co=ctrl.last_co,
                params=ctrl.pid_params,
            )

def set_pid_params(self, controller_id: int, kp: float, ti: float, td: float) -> None:
    with self._lock:
        ctrl = self._controllers[controller_id]
        ctrl.pid_params.gain = kp
        ctrl.pid_params.reset = ti
        ctrl.pid_params.rate = td

def set_pid_mode(self, controller_id: int, mode: int) -> None:
    with self._lock:
        ctrl = self._controllers[controller_id]
        ctrl.pid_mode = mode

def get_pid_status(self, controller_id: int) -> dict:
    with self._lock:
        ctrl = self._controllers[controller_id]
        return {
            "enabled": ctrl.pid_enabled,
            "kp": ctrl.pid_params.gain,
            "ti": ctrl.pid_params.reset,
            "td": ctrl.pid_params.rate,
            "mode": ctrl.pid_mode,
            "cv": ctrl.pid_state.cv,
        }
```

Expand `_on_opcua_write` to handle new params:

```python
def _on_opcua_write(self, controller_id: int, param: str, value: float) -> None:
    """Handle writes from OPC-UA clients."""
    with self._lock:
        ctrl = self._controllers.get(controller_id)
        if ctrl is None:
            return
        if param == "co":
            ctrl.last_co = value
        elif param == "sp":
            ctrl.sp = value
        elif param == "kp":
            ctrl.pid_params.gain = value
        elif param == "ti":
            ctrl.pid_params.reset = value
        elif param == "td":
            ctrl.pid_params.rate = value
        elif param == "pid_mode":
            ctrl.pid_mode = int(value)
        elif param == "pid_sp":
            ctrl.sp = value
```

Modify `_tick` to include PID computation:

```python
def _tick(self, dt: float) -> None:
    with self._lock:
        for ctrl in self._controllers.values():
            pv = ctrl.model.step(co=ctrl.last_co, dt=dt)
            if ctrl.step_active:
                pv += ctrl.step_amplitude
            if ctrl.noise_active:
                pv += random.gauss(0, ctrl.noise_amplitude)

            # Internal PID: compute CO when enabled and AUTO
            if ctrl.pid_enabled and ctrl.pid_mode == 1:
                result = self._pid_engine.compute(
                    params=ctrl.pid_params,
                    state=ctrl.pid_state,
                    pv=FFSignal.good(pv),
                    sp=FFSignal.good(ctrl.sp),
                    bkcal_in=FFSignal.good(ctrl.pid_state.cv),
                    dt=dt,
                    out_limits=(0.0, 100.0),
                )
                ctrl.pid_state = result.new_state
                ctrl.last_co = result.cv

            self._opcua_server.update_values(
                controller_id=ctrl.controller_id,
                pv=pv,
                sp=ctrl.sp,
                co=ctrl.last_co,
            )
```

Update `get_controller_status` and `get_status` to include PID fields in the returned `ControllerSimStatus`:

```python
def get_controller_status(self, controller_id: int) -> ControllerSimStatus:
    with self._lock:
        ctrl = self._controllers[controller_id]
        return ControllerSimStatus(
            preset=ctrl.preset_name,
            gain=ctrl.gain,
            tau1=ctrl.tau1,
            tau2=ctrl.tau2,
            dead_time=ctrl.dead_time,
            step_active=ctrl.step_active,
            step_amplitude=ctrl.step_amplitude,
            noise_active=ctrl.noise_active,
            noise_amplitude=ctrl.noise_amplitude,
            pid_enabled=ctrl.pid_enabled,
            pid_kp=ctrl.pid_params.gain,
            pid_ti=ctrl.pid_params.reset,
            pid_td=ctrl.pid_params.rate,
            pid_mode=ctrl.pid_mode,
            pid_cv=ctrl.pid_state.cv,
        )
```

Apply the same change to `get_status` (the dict comprehension version).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py -v`
Expected: All tests PASS (existing + 16 new).

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py tests/core/unit/test_simulator_adapter.py
git commit -m "feat(sim): integrate PIDEngine into SimulatorAdapter with enable/disable and OPC-UA write handling"
```

---

### Task 3: OPC-UA Server — Add PID nodes (Kp, Ti, Td, PID_Mode, PID_SP)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py`
- Create: `tests/core/unit/test_opcua_server.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/core/unit/test_opcua_server.py`:

```python
"""Tests for OPCUAServer — PID node registration and write handling."""
from __future__ import annotations

from unittest.mock import MagicMock

from smart_pid_core.adapters.inbound.opcua_server import OPCUAServer


class TestOPCUAServerPIDWriteHandler:
    """Test that _WriteHandler resolves PID param nodes correctly."""

    def test_write_handler_resolves_kp(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import _WriteHandler

        kp_node = MagicMock()
        kp_node.nodeid.to_string.return_value = "ns=2;s=Kp_1"
        controller_nodes = {
            1: {"kp": kp_node, "ti": MagicMock(), "td": MagicMock()},
        }
        callback = MagicMock()
        handler = _WriteHandler(callback, controller_nodes)
        result = handler._resolve_node("ns=2;s=Kp_1")
        assert result == (1, "kp")

    def test_write_handler_resolves_ti(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import _WriteHandler

        ti_node = MagicMock()
        ti_node.nodeid.to_string.return_value = "ns=2;s=Ti_1"
        controller_nodes = {
            1: {"ti": ti_node, "kp": MagicMock(), "td": MagicMock()},
        }
        callback = MagicMock()
        handler = _WriteHandler(callback, controller_nodes)
        result = handler._resolve_node("ns=2;s=Ti_1")
        assert result == (1, "ti")

    def test_write_handler_resolves_pid_mode(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import _WriteHandler

        mode_node = MagicMock()
        mode_node.nodeid.to_string.return_value = "ns=2;s=PIDMode_1"
        controller_nodes = {
            1: {"pid_mode": mode_node},
        }
        callback = MagicMock()
        handler = _WriteHandler(callback, controller_nodes)
        result = handler._resolve_node("ns=2;s=PIDMode_1")
        assert result == (1, "pid_mode")

    def test_write_handler_resolves_pid_sp(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import _WriteHandler

        sp_node = MagicMock()
        sp_node.nodeid.to_string.return_value = "ns=2;s=PIDSP_1"
        controller_nodes = {
            1: {"pid_sp": sp_node},
        }
        callback = MagicMock()
        handler = _WriteHandler(callback, controller_nodes)
        result = handler._resolve_node("ns=2;s=PIDSP_1")
        assert result == (1, "pid_sp")

    def test_write_handler_calls_callback_on_datachange(self) -> None:
        from smart_pid_core.adapters.inbound.opcua_server import _WriteHandler

        kp_node = MagicMock()
        kp_node.nodeid.to_string.return_value = "ns=2;s=Kp_1"
        controller_nodes = {1: {"kp": kp_node}}
        callback = MagicMock()
        handler = _WriteHandler(callback, controller_nodes)
        handler.datachange_notification(kp_node, 3.5, None)
        callback.assert_called_once_with(1, "kp", 3.5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_opcua_server.py -v`
Expected: FAIL — `_resolve_node` only checks `co` and `sp`, not `kp`/`ti`/`td`/`pid_mode`/`pid_sp`.

- [ ] **Step 3: Implement OPC-UA server changes**

Edit `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py`:

In `_async_register_controller`, add 5 new nodes after the existing 5:

```python
# PID tuning nodes (all writable)
kp_node = await ctrl_folder.add_variable(
    self._ns_idx, "Kp", 1.0, ua.VariantType.Float,
)
ti_node = await ctrl_folder.add_variable(
    self._ns_idx, "Ti", 10.0, ua.VariantType.Float,
)
td_node = await ctrl_folder.add_variable(
    self._ns_idx, "Td", 0.0, ua.VariantType.Float,
)
pid_mode_node = await ctrl_folder.add_variable(
    self._ns_idx, "PID_Mode", 0, ua.VariantType.Int32,
)
pid_sp_node = await ctrl_folder.add_variable(
    self._ns_idx, "PID_SP", 50.0, ua.VariantType.Float,
)
await kp_node.set_writable()
await ti_node.set_writable()
await td_node.set_writable()
await pid_mode_node.set_writable()
await pid_sp_node.set_writable()
```

Add them to `node_ids` and `self._controller_nodes[controller_id]`:

```python
node_ids = {
    "pv": pv_node.nodeid.to_string(),
    "sp": sp_node.nodeid.to_string(),
    "co": co_node.nodeid.to_string(),
    "mode": mode_node.nodeid.to_string(),
    "status": status_node.nodeid.to_string(),
    "kp": kp_node.nodeid.to_string(),
    "ti": ti_node.nodeid.to_string(),
    "td": td_node.nodeid.to_string(),
    "pid_mode": pid_mode_node.nodeid.to_string(),
    "pid_sp": pid_sp_node.nodeid.to_string(),
}
self._controller_nodes[controller_id] = {
    "pv": pv_node,
    "sp": sp_node,
    "co": co_node,
    "mode": mode_node,
    "status": status_node,
    "kp": kp_node,
    "ti": ti_node,
    "td": td_node,
    "pid_mode": pid_mode_node,
    "pid_sp": pid_sp_node,
}
```

Update the subscription to monitor new writable nodes. Change the subscription loop in `_setup_and_serve` and the late-registration block in `_async_register_controller`:

```python
_WRITABLE_PARAMS = ("co", "sp", "kp", "ti", "td", "pid_mode", "pid_sp")
```

Use `_WRITABLE_PARAMS` instead of `("co", "sp")` in both subscription loops.

Expand `_WriteHandler._resolve_node` to check all writable params:

```python
def _resolve_node(self, node_id_str: str) -> tuple[int, str] | None:
    """Find controller_id and param name from a node_id string."""
    for cid, nodes in self._controller_nodes.items():
        for param in _WRITABLE_PARAMS:
            node = nodes.get(param)
            if node is not None and node.nodeid.to_string() == node_id_str:
                return (cid, param)
    return None
```

Move `_WRITABLE_PARAMS` to module level so both `_WriteHandler` and `_setup_and_serve` can reference it.

Add `update_values` to also write PID-related node values. Add new parameters with defaults:

```python
def update_values(
    self,
    controller_id: int,
    pv: float,
    sp: float,
    co: float,
    mode: int = 0,
    status: int = 0,
    *,
    kp: float | None = None,
    ti: float | None = None,
    td: float | None = None,
    pid_mode: int | None = None,
    pid_sp: float | None = None,
) -> None:
    """Update OPC-UA node values for a controller. Thread-safe."""
    if self._loop is None or not self._loop.is_running():
        return
    asyncio.run_coroutine_threadsafe(
        self._async_update_values(
            controller_id, pv, sp, co, mode, status,
            kp=kp, ti=ti, td=td, pid_mode=pid_mode, pid_sp=pid_sp,
        ),
        self._loop,
    )
```

Update `_async_update_values` to write new nodes when values are provided:

```python
async def _async_update_values(
    self,
    controller_id: int,
    pv: float,
    sp: float,
    co: float,
    mode: int,
    status: int,
    *,
    kp: float | None = None,
    ti: float | None = None,
    td: float | None = None,
    pid_mode: int | None = None,
    pid_sp: float | None = None,
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
    if kp is not None:
        await nodes["kp"].write_value(ua.DataValue(ua.Variant(kp, ua.VariantType.Float)))
    if ti is not None:
        await nodes["ti"].write_value(ua.DataValue(ua.Variant(ti, ua.VariantType.Float)))
    if td is not None:
        await nodes["td"].write_value(ua.DataValue(ua.Variant(td, ua.VariantType.Float)))
    if pid_mode is not None:
        await nodes["pid_mode"].write_value(
            ua.DataValue(ua.Variant(pid_mode, ua.VariantType.Int32)),
        )
    if pid_sp is not None:
        await nodes["pid_sp"].write_value(
            ua.DataValue(ua.Variant(pid_sp, ua.VariantType.Float)),
        )
```

- [ ] **Step 4: Update SimulatorAdapter._tick to pass PID values to update_values**

In `simulator_adapter.py`, update the `update_values` call in `_tick`:

```python
self._opcua_server.update_values(
    controller_id=ctrl.controller_id,
    pv=pv,
    sp=ctrl.sp,
    co=ctrl.last_co,
    kp=ctrl.pid_params.gain,
    ti=ctrl.pid_params.reset,
    td=ctrl.pid_params.rate,
    pid_mode=ctrl.pid_mode,
    pid_sp=ctrl.sp,
)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_opcua_server.py tests/core/unit/test_simulator_adapter.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/opcua_server.py packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py
git commit -m "feat(sim): add Kp/Ti/Td/PID_Mode/PID_SP OPC-UA nodes with write subscription"
```

---

### Task 4: REST endpoints — PID enable, params, mode, status

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py`
- Modify: `tests/core/integration/test_api_simulator.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/core/integration/test_api_simulator.py`:

```python
class TestSimulatorPIDEndpoints:
    def test_enable_pid(self, client, auth_header, sim_adapter):
        sim_adapter.register_controller(1)
        resp = client.post(
            "/simulator/1/pid/enable",
            json={"controller_id": 1, "enabled": True},
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_set_pid_params(self, client, auth_header, sim_adapter):
        sim_adapter.register_controller(1)
        resp = client.post(
            "/simulator/1/pid/params",
            json={"controller_id": 1, "kp": 2.0, "ti": 5.0, "td": 1.0},
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_set_pid_mode(self, client, auth_header, sim_adapter):
        sim_adapter.register_controller(1)
        resp = client.post(
            "/simulator/1/pid/mode",
            json={"controller_id": 1, "mode": "AUTO"},
            headers=auth_header,
        )
        assert resp.status_code == 200

    def test_get_pid_status(self, client, auth_header, sim_adapter):
        sim_adapter.register_controller(1)
        sim_adapter.enable_pid(1, enabled=True)
        sim_adapter.set_pid_params(1, kp=3.0, ti=8.0, td=0.5)
        resp = client.get("/simulator/1/pid/status", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["kp"] == 3.0
        assert data["ti"] == 8.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_api_simulator.py::TestSimulatorPIDEndpoints -v`
Expected: FAIL — 404, routes don't exist.

- [ ] **Step 3: Implement REST endpoints**

Edit `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py` — add imports and 4 new endpoints:

```python
from smart_pid_domain.dtos.simulator import (
    SimulatorDisturbanceRequest,
    SimulatorParametersRequest,
    SimulatorPIDEnableRequest,
    SimulatorPIDModeRequest,
    SimulatorPIDParamsRequest,
    SimulatorPIDStatusResponse,
    SimulatorPresetRequest,
    SimulatorStatusResponse,
)


@router.post("/{controller_id}/pid/enable", response_model=CommandResponse)
async def enable_pid(
    controller_id: int,
    body: SimulatorPIDEnableRequest,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.enable_pid(controller_id, body.enabled)
    state = "enabled" if body.enabled else "disabled"
    return CommandResponse(ok=True, controller_id=controller_id, detail=f"PID {state}")


@router.post("/{controller_id}/pid/params", response_model=CommandResponse)
async def set_pid_params(
    controller_id: int,
    body: SimulatorPIDParamsRequest,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.set_pid_params(controller_id, body.kp, body.ti, body.td)
    return CommandResponse(ok=True, controller_id=controller_id, detail="PID params updated")


@router.post("/{controller_id}/pid/mode", response_model=CommandResponse)
async def set_pid_mode(
    controller_id: int,
    body: SimulatorPIDModeRequest,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    mode_int = 1 if body.mode == "AUTO" else 0
    adapter.set_pid_mode(controller_id, mode_int)
    return CommandResponse(ok=True, controller_id=controller_id, detail=f"PID mode={body.mode}")


@router.get("/{controller_id}/pid/status", response_model=SimulatorPIDStatusResponse)
async def get_pid_status(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> SimulatorPIDStatusResponse:
    status = adapter.get_pid_status(controller_id)
    return SimulatorPIDStatusResponse(**status)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_api_simulator.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py tests/core/integration/test_api_simulator.py
git commit -m "feat(sim): add REST endpoints for simulator internal PID control"
```

---

### Task 5: HMI service layer — ports, api_client, mock_service

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py`

- [ ] **Step 1: Add method signatures to ports.py**

Add after the `clear_simulator_disturbance` method in `ports.py`:

```python
    # Simulator PID
    def enable_simulator_pid(
        self, controller_id: int, enabled: bool,
    ) -> CommandResponse: ...
    def set_simulator_pid_params(
        self, controller_id: int, kp: float, ti: float, td: float,
    ) -> CommandResponse: ...
    def set_simulator_pid_mode(
        self, controller_id: int, mode: str,
    ) -> CommandResponse: ...
    def get_simulator_pid_status(
        self, controller_id: int,
    ) -> dict: ...
```

- [ ] **Step 2: Implement in api_client.py**

Add after `clear_simulator_disturbance` in `api_client.py`:

```python
    def enable_simulator_pid(
        self, controller_id: int, enabled: bool,
    ) -> CommandResponse:
        resp = self._http.post(
            f"/simulator/{controller_id}/pid/enable",
            json={"controller_id": controller_id, "enabled": enabled},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def set_simulator_pid_params(
        self, controller_id: int, kp: float, ti: float, td: float,
    ) -> CommandResponse:
        resp = self._http.post(
            f"/simulator/{controller_id}/pid/params",
            json={"controller_id": controller_id, "kp": kp, "ti": ti, "td": td},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def set_simulator_pid_mode(
        self, controller_id: int, mode: str,
    ) -> CommandResponse:
        resp = self._http.post(
            f"/simulator/{controller_id}/pid/mode",
            json={"controller_id": controller_id, "mode": mode},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def get_simulator_pid_status(self, controller_id: int) -> dict:
        resp = self._http.get(
            f"/simulator/{controller_id}/pid/status",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 3: Implement in mock_service.py**

Add after `clear_simulator_disturbance` in `mock_service.py`:

```python
    def enable_simulator_pid(
        self, controller_id: int, enabled: bool,
    ) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id, detail="mock")

    def set_simulator_pid_params(
        self, controller_id: int, kp: float, ti: float, td: float,
    ) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id, detail="mock")

    def set_simulator_pid_mode(
        self, controller_id: int, mode: str,
    ) -> CommandResponse:
        return CommandResponse(ok=True, controller_id=controller_id, detail="mock")

    def get_simulator_pid_status(self, controller_id: int) -> dict:
        return {"enabled": False, "kp": 1.0, "ti": 10.0, "td": 0.0, "mode": 0, "cv": 0.0}
```

- [ ] **Step 4: Run existing HMI tests to verify no regressions**

Run: `uv run pytest tests/hmi/ -v`
Expected: All existing tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py
git commit -m "feat(hmi): add simulator PID methods to service layer (ports, api_client, mock)"
```

---

### Task 6: HMI — SimulatorPage "Internal PID" group

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`
- Create: `tests/hmi/test_simulator_page.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/hmi/test_simulator_page.py`:

```python
"""Tests for SimulatorPage — Internal PID group."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QGroupBox, QPushButton

from smart_pid_hmi.pages.simulator_page import SimulatorPage
from smart_pid_hmi.themes.dark_room import DarkRoomTheme


@pytest.fixture
def page(qtbot) -> SimulatorPage:
    theme = DarkRoomTheme()
    p = SimulatorPage(theme=theme)
    qtbot.addWidget(p)
    return p


class TestSimulatorPagePIDGroup:
    def test_pid_group_exists(self, page: SimulatorPage) -> None:
        groups = page.findChildren(QGroupBox)
        names = [g.title() for g in groups]
        assert "Internal PID" in names

    def test_pid_enable_checkbox(self, page: SimulatorPage) -> None:
        cb = page.findChild(QCheckBox, "pid_enable_cb")
        assert cb is not None
        assert cb.isChecked() is False

    def test_pid_mode_combo(self, page: SimulatorPage) -> None:
        combo = page.findChild(QComboBox, "pid_mode_combo")
        assert combo is not None
        assert combo.currentText() == "MAN"
        assert combo.count() == 2

    def test_pid_kp_spinbox(self, page: SimulatorPage) -> None:
        spin = page.findChild(QDoubleSpinBox, "pid_kp_spin")
        assert spin is not None
        assert spin.value() == 1.0

    def test_pid_ti_spinbox(self, page: SimulatorPage) -> None:
        spin = page.findChild(QDoubleSpinBox, "pid_ti_spin")
        assert spin is not None
        assert spin.value() == 10.0
        assert spin.suffix() == " s"

    def test_pid_td_spinbox(self, page: SimulatorPage) -> None:
        spin = page.findChild(QDoubleSpinBox, "pid_td_spin")
        assert spin is not None
        assert spin.value() == 0.0
        assert spin.suffix() == " s"

    def test_pid_apply_button(self, page: SimulatorPage) -> None:
        btn = page.findChild(QPushButton, "pid_apply_btn")
        assert btn is not None

    def test_controls_disabled_when_unchecked(self, page: SimulatorPage) -> None:
        combo = page.findChild(QComboBox, "pid_mode_combo")
        spin_kp = page.findChild(QDoubleSpinBox, "pid_kp_spin")
        btn = page.findChild(QPushButton, "pid_apply_btn")
        assert not combo.isEnabled()
        assert not spin_kp.isEnabled()
        assert not btn.isEnabled()

    def test_controls_enabled_when_checked(self, page: SimulatorPage, qtbot) -> None:
        cb = page.findChild(QCheckBox, "pid_enable_cb")
        cb.setChecked(True)
        combo = page.findChild(QComboBox, "pid_mode_combo")
        spin_kp = page.findChild(QDoubleSpinBox, "pid_kp_spin")
        btn = page.findChild(QPushButton, "pid_apply_btn")
        assert combo.isEnabled()
        assert spin_kp.isEnabled()
        assert btn.isEnabled()


class TestSimulatorPagePIDSignals:
    def test_enable_signal(self, page: SimulatorPage, qtbot) -> None:
        with qtbot.waitSignal(page.pid_enabled_changed, timeout=1000) as blocker:
            cb = page.findChild(QCheckBox, "pid_enable_cb")
            cb.setChecked(True)
        assert blocker.args == [True]

    def test_params_signal(self, page: SimulatorPage, qtbot) -> None:
        cb = page.findChild(QCheckBox, "pid_enable_cb")
        cb.setChecked(True)
        with qtbot.waitSignal(page.pid_params_changed, timeout=1000) as blocker:
            btn = page.findChild(QPushButton, "pid_apply_btn")
            qtbot.mouseClick(btn, Qt.MouseButton.LeftButton)
        kp, ti, td = blocker.args
        assert kp == 1.0
        assert ti == 10.0
        assert td == 0.0

    def test_mode_signal(self, page: SimulatorPage, qtbot) -> None:
        cb = page.findChild(QCheckBox, "pid_enable_cb")
        cb.setChecked(True)
        with qtbot.waitSignal(page.pid_mode_changed, timeout=1000) as blocker:
            combo = page.findChild(QComboBox, "pid_mode_combo")
            combo.setCurrentText("AUTO")
        assert blocker.args == ["AUTO"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/test_simulator_page.py -v`
Expected: FAIL — no `pid_enable_cb`, no `pid_enabled_changed` signal.

- [ ] **Step 3: Implement the "Internal PID" group**

Edit `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`:

Add new signals to the class:

```python
pid_enabled_changed = Signal(bool)
pid_params_changed = Signal(float, float, float)  # Kp, Ti, Td
pid_mode_changed = Signal(str)  # "MAN" or "AUTO"
```

Add `QCheckBox` to imports:

```python
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    ...
)
```

In `__init__`, after the Parameters group and before the Disturbances group, add:

```python
# Internal PID group
pid_group = QGroupBox("Internal PID")
pid_layout = QVBoxLayout(pid_group)

# Enable + Mode row
pid_top_row = QHBoxLayout()
self._pid_enable_cb = QCheckBox("Enable PID")
self._pid_enable_cb.setObjectName("pid_enable_cb")
self._pid_enable_cb.setChecked(False)
self._pid_enable_cb.toggled.connect(self._on_pid_enable_toggled)
pid_top_row.addWidget(self._pid_enable_cb)
pid_top_row.addWidget(QLabel("Mode:"))
self._pid_mode_combo = QComboBox()
self._pid_mode_combo.setObjectName("pid_mode_combo")
self._pid_mode_combo.addItems(["MAN", "AUTO"])
self._pid_mode_combo.currentTextChanged.connect(self._on_pid_mode_changed)
pid_top_row.addWidget(self._pid_mode_combo)
pid_layout.addLayout(pid_top_row)

# Kp row
kp_row = QHBoxLayout()
kp_row.addWidget(QLabel("Kp:"))
self._pid_kp_spin = QDoubleSpinBox()
self._pid_kp_spin.setObjectName("pid_kp_spin")
self._pid_kp_spin.setRange(0.01, 50.0)
self._pid_kp_spin.setValue(1.0)
self._pid_kp_spin.setDecimals(2)
kp_row.addWidget(self._pid_kp_spin, stretch=1)
pid_layout.addLayout(kp_row)

# Ti row
ti_row = QHBoxLayout()
ti_row.addWidget(QLabel("Ti:"))
self._pid_ti_spin = QDoubleSpinBox()
self._pid_ti_spin.setObjectName("pid_ti_spin")
self._pid_ti_spin.setRange(0.1, 999.0)
self._pid_ti_spin.setValue(10.0)
self._pid_ti_spin.setDecimals(1)
self._pid_ti_spin.setSuffix(" s")
ti_row.addWidget(self._pid_ti_spin, stretch=1)
pid_layout.addLayout(ti_row)

# Td row
td_row = QHBoxLayout()
td_row.addWidget(QLabel("Td:"))
self._pid_td_spin = QDoubleSpinBox()
self._pid_td_spin.setObjectName("pid_td_spin")
self._pid_td_spin.setRange(0.0, 999.0)
self._pid_td_spin.setValue(0.0)
self._pid_td_spin.setDecimals(1)
self._pid_td_spin.setSuffix(" s")
td_row.addWidget(self._pid_td_spin, stretch=1)
pid_layout.addLayout(td_row)

# Apply button
pid_apply_btn = QPushButton("Apply PID Parameters")
pid_apply_btn.setObjectName("pid_apply_btn")
pid_apply_btn.clicked.connect(self._on_pid_apply)
pid_layout.addWidget(pid_apply_btn)

layout.addWidget(pid_group)

# Initial state: PID controls disabled
self._pid_controls = [
    self._pid_mode_combo, self._pid_kp_spin,
    self._pid_ti_spin, self._pid_td_spin, pid_apply_btn,
]
for ctrl in self._pid_controls:
    ctrl.setEnabled(False)
```

Add handler methods:

```python
def _on_pid_enable_toggled(self, checked: bool) -> None:
    for ctrl in self._pid_controls:
        ctrl.setEnabled(checked)
    self.pid_enabled_changed.emit(checked)

def _on_pid_apply(self) -> None:
    self.pid_params_changed.emit(
        self._pid_kp_spin.value(),
        self._pid_ti_spin.value(),
        self._pid_td_spin.value(),
    )

def _on_pid_mode_changed(self, mode: str) -> None:
    self.pid_mode_changed.emit(mode)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/hmi/test_simulator_page.py -v`
Expected: All 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py tests/hmi/test_simulator_page.py
git commit -m "feat(hmi): add Internal PID group to SimulatorPage with enable/disable, Kp/Ti/Td, mode"
```

---

### Task 7: HMI — Wire SimulatorPage PID signals in main.py

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`

- [ ] **Step 1: Add signal connections in `_connect_signals`**

In `main.py`, find the block where simulator signals are connected (around line 274-278) and add after `clear_disturbance_requested`:

```python
self._simulator_page.pid_enabled_changed.connect(self._send_sim_pid_enable)
self._simulator_page.pid_params_changed.connect(self._send_sim_pid_params)
self._simulator_page.pid_mode_changed.connect(self._send_sim_pid_mode)
```

- [ ] **Step 2: Add handler methods**

Add after the `_send_sim_clear` method (around line 545):

```python
def _send_sim_pid_enable(self, enabled: bool) -> None:
    cid = self._simulator_page.current_controller_id
    if cid is None:
        return
    self._safe_api_call(self._api_client.enable_simulator_pid, cid, enabled)

def _send_sim_pid_params(self, kp: float, ti: float, td: float) -> None:
    cid = self._simulator_page.current_controller_id
    if cid is None:
        return
    self._safe_api_call(self._api_client.set_simulator_pid_params, cid, kp, ti, td)

def _send_sim_pid_mode(self, mode: str) -> None:
    cid = self._simulator_page.current_controller_id
    if cid is None:
        return
    self._safe_api_call(self._api_client.set_simulator_pid_mode, cid, mode)
```

- [ ] **Step 3: Run all HMI tests to verify no regressions**

Run: `uv run pytest tests/hmi/ -v`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/main.py
git commit -m "feat(hmi): wire SimulatorPage PID signals to API client in MainWindow"
```

---

### Task 8: Integration test — PID closes the loop

**Files:**
- Create: `tests/core/integration/test_simulator_pid_loop.py`

- [ ] **Step 1: Write the integration test**

Create `tests/core/integration/test_simulator_pid_loop.py`:

```python
"""Integration test — simulator PID closes the loop and PV converges to SP."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ProcessPresetName


def _mock_opcua_server() -> MagicMock:
    mock = MagicMock()
    mock.is_running = False
    mock.controller_node_ids = {}

    def _register(cid: int) -> dict[str, str]:
        mock.controller_node_ids[cid] = {
            "pv": f"ns=2;s=PV_{cid}", "sp": f"ns=2;s=SP_{cid}",
            "co": f"ns=2;s=CO_{cid}",
        }
        return mock.controller_node_ids[cid]

    mock.start.side_effect = lambda: setattr(mock, "is_running", True)
    mock.stop.side_effect = lambda: setattr(mock, "is_running", False)
    mock.register_controller.side_effect = _register
    return mock


@pytest.fixture
def adapter() -> SimulatorAdapter:
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]
    with patch(
        "smart_pid_core.adapters.inbound.simulator_adapter.OPCUAServer",
        return_value=_mock_opcua_server(),
    ):
        a = SimulatorAdapter(settings=settings)
        yield a
        a.stop()


class TestSimulatorPIDClosesLoop:
    def test_pv_converges_to_sp_flow_preset(self, adapter: SimulatorAdapter) -> None:
        """With FLOW preset and PID in AUTO, PV should converge toward SP."""
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.FLOW)
        adapter._controllers[1].sp = 50.0
        adapter._controllers[1].last_co = 0.0

        # Enable PID in AUTO with tuning suitable for FLOW (K=1.2, tau1=3, L=1)
        adapter.enable_pid(1, enabled=True)
        adapter.set_pid_params(1, kp=0.8, ti=4.0, td=0.5)
        adapter.set_pid_mode(1, mode=1)  # AUTO

        # Run 500 ticks at 100ms = 50 seconds of simulation
        dt = 0.1
        for _ in range(500):
            adapter._tick(dt)

        # Capture final PV from the last update_values call
        last_call = adapter._opcua_server.update_values.call_args
        final_pv = last_call.kwargs.get("pv", last_call[1].get("pv", 0.0) if len(last_call[1]) > 1 else 0.0)
        final_co = adapter._controllers[1].last_co

        # PV should be close to SP (within 10% of SP)
        assert abs(final_pv - 50.0) < 5.0, f"PV={final_pv} did not converge to SP=50.0"
        assert final_co > 0.0, f"CO={final_co} should be positive"

    def test_pid_disabled_does_not_close_loop(self, adapter: SimulatorAdapter) -> None:
        """With PID disabled, CO stays at initial value."""
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.FLOW)
        adapter._controllers[1].sp = 50.0
        adapter._controllers[1].last_co = 0.0

        for _ in range(100):
            adapter._tick(0.1)

        assert adapter._controllers[1].last_co == 0.0

    def test_opcua_write_ti_affects_pid(self, adapter: SimulatorAdapter) -> None:
        """Writing Ti via OPC-UA callback changes PID behavior."""
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.FLOW)
        adapter.enable_pid(1, enabled=True)
        adapter.set_pid_params(1, kp=0.8, ti=4.0, td=0.0)
        adapter.set_pid_mode(1, mode=1)
        adapter._controllers[1].sp = 50.0

        # Run 100 ticks
        for _ in range(100):
            adapter._tick(0.1)
        co_before = adapter._controllers[1].last_co

        # Write new Ti via OPC-UA (simulating smartPID SUPERVISORY write)
        adapter._on_opcua_write(1, "ti", 2.0)
        assert adapter._controllers[1].pid_params.reset == 2.0

        # Run more ticks — behavior should differ (faster integral)
        for _ in range(100):
            adapter._tick(0.1)
        co_after = adapter._controllers[1].last_co

        # Both should have moved, confirming PID is computing
        assert co_before > 0.0
        assert co_after > 0.0
```

- [ ] **Step 2: Run the integration test**

Run: `uv run pytest tests/core/integration/test_simulator_pid_loop.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/core/integration/test_simulator_pid_loop.py
git commit -m "test(sim): add integration tests for simulator PID closed-loop convergence"
```

---

### Task 9: Lint, type-check, and full test suite

- [ ] **Step 1: Run ruff**

Run: `uv run --with ruff ruff check .`
Fix any issues.

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit any fixes**

```bash
git add -u
git commit -m "chore: fix lint and type issues from simulator PID feature"
```

---

### Task 10: Update spec documents

Per CLAUDE.md convention: "Toda nova feature DEVE ser documentada nas specs do projeto."

**Files:**
- Modify: `docs/superpowers/specs/2026-04-03-phase4-simulator-design.md` — add "Internal PID" section
- Modify: `docs/smartPIDv2.md` — add simulator PID reference (if simulator is documented there)

- [ ] **Step 1: Update Phase 4 spec with Internal PID section**

Add a new section to `docs/superpowers/specs/2026-04-03-phase4-simulator-design.md` documenting the internal PID: its purpose, OPC-UA nodes, REST endpoints, and HMI controls. Reference the detailed spec at `docs/superpowers/specs/2026-04-06-simulator-internal-pid-design.md`.

- [ ] **Step 2: Update any other docs that reference the simulator**

Search `docs/` for references to the simulator and add a note about the internal PID where relevant.

- [ ] **Step 3: Commit**

```bash
git add docs/
git commit -m "docs: update specs with simulator internal PID feature"
```
