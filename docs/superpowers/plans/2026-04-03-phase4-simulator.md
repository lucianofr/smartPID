# Phase 4: Simulator (Digital Twin) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a digital twin simulator with process models, OPC-UA server, REST endpoints, and basic HMI page for PID testing without physical hardware.

**Architecture:** SimulatorAdapter implements both TelemetrySource and ControlWriter ports, running a ProcessModel per controller in a daemon thread. An embedded asyncua.Server exposes simulated values on OPC-UA. REST endpoints control presets, parameters, and disturbances. HMI gets a SimulatorPage with preset selection and disturbance injection.

**Tech Stack:** Python 3.13, scipy.signal (transfer functions), asyncua (OPC-UA), FastAPI, PySide6, pydantic v2

---

## File Structure

### New files

| Package | Path | Responsibility |
|---------|------|----------------|
| domain | `packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py` | Simulator request/response DTOs |
| domain | `packages/smart_pid_domain/src/smart_pid_domain/models/process_preset.py` | ProcessPreset frozen dataclass + PRESETS registry |
| core | `packages/smart_pid_core/src/smart_pid_core/domain/services/process_models.py` | ProcessModel (scipy.signal simulation engine) |
| core | `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py` | SimulatorAdapter (TelemetrySource + ControlWriter) |
| core | `packages/smart_pid_core/src/smart_pid_core/adapters/factory.py` | AdapterFactory for DI based on settings |
| core | `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py` | REST endpoints under /simulator |
| hmi | `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py` | Simulator UI page |
| tests | `tests/core/unit/test_process_models.py` | ProcessModel unit tests |
| tests | `tests/core/unit/test_simulator_adapter.py` | SimulatorAdapter unit tests |
| tests | `tests/core/integration/test_api_simulator.py` | REST simulator endpoint tests |
| tests | `tests/domain/test_simulator_dtos.py` | Simulator DTO tests |
| tests | `tests/hmi/pages/test_simulator_page.py` | SimulatorPage widget tests |

### Modified files

| Package | Path | Change |
|---------|------|--------|
| domain | `packages/smart_pid_domain/src/smart_pid_domain/enums.py` | Add `ProcessPresetName` enum |
| domain | `packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py` | Export new simulator DTOs |
| core | `packages/smart_pid_core/src/smart_pid_core/config.py` | Add `simulator_interval_ms` setting |
| core | `packages/smart_pid_core/pyproject.toml` | Add `asyncua`, `scipy` dependencies |
| core | `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py` | Register simulator router + store simulator_adapter on app.state |
| core | `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py` | Add `get_simulator_adapter` dependency |
| core | `packages/smart_pid_core/src/smart_pid_core/main.py` | Wire AdapterFactory, pass simulator_adapter to create_app |
| hmi | `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py` | Add simulator API methods |
| hmi | `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` | Add Simulator toolbar button + page |

---

## Task 1: Add ProcessPresetName enum and simulator_interval_ms config

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/enums.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/config.py`
- Modify: `packages/smart_pid_core/pyproject.toml`
- Test: `tests/domain/test_dtos.py` (existing — verify enum round-trips)
- Test: `tests/core/unit/test_config.py` (existing — verify new setting)

- [ ] **Step 1: Add ProcessPresetName enum**

In `packages/smart_pid_domain/src/smart_pid_domain/enums.py`, add after the `AlarmType` class:

```python
class ProcessPresetName(StrEnum):
    """Simulator process model presets."""
    FLOW = "FLOW"
    PRESSURE = "PRESSURE"
    LEVEL = "LEVEL"
    TEMPERATURE = "TEMPERATURE"
    CUSTOM = "CUSTOM"
```

- [ ] **Step 2: Add simulator_interval_ms to CoreSettings**

In `packages/smart_pid_core/src/smart_pid_core/config.py`, add after `simulator_port`:

```python
    simulator_interval_ms: int = 100
```

- [ ] **Step 3: Add scipy and asyncua dependencies**

In `packages/smart_pid_core/pyproject.toml`, add to the `dependencies` list:

```toml
    "scipy>=1.11",
    "asyncua>=1.1",
```

- [ ] **Step 4: Sync workspace**

Run: `uv sync --all-packages`
Expected: resolves successfully, installs scipy and asyncua

- [ ] **Step 5: Verify existing tests still pass**

Run: `uv run pytest tests/domain/test_dtos.py tests/core/unit/test_config.py -v`
Expected: all existing tests PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/enums.py \
       packages/smart_pid_core/src/smart_pid_core/config.py \
       packages/smart_pid_core/pyproject.toml \
       uv.lock
git commit -m "feat(domain): add ProcessPresetName enum and simulator_interval_ms config"
```

---

## Task 2: ProcessPreset + PRESETS registry in domain package

**Files:**
- Create: `packages/smart_pid_domain/src/smart_pid_domain/models/process_preset.py`
- Create: `tests/domain/test_process_preset.py`

The `ProcessPreset` dataclass and `PRESETS` registry live in the **domain** package (zero infra deps) so both `smart_pid_core` and `smart_pid_hmi` can import them without violating hexagonal boundaries. The `ProcessModel` (which depends on scipy) stays in core (Task 3).

- [ ] **Step 1: Write failing tests for ProcessPreset and PRESETS**

Create `tests/domain/test_process_preset.py`:

```python
"""Tests for ProcessPreset frozen dataclass and PRESETS registry."""
from __future__ import annotations

import pytest

from smart_pid_domain.enums import ProcessPresetName
from smart_pid_domain.models.process_preset import PRESETS, ProcessPreset


class TestProcessPreset:
    def test_all_presets_registered(self) -> None:
        for name in ProcessPresetName:
            if name == ProcessPresetName.CUSTOM:
                continue
            assert name in PRESETS, f"Preset {name} not registered"

    def test_preset_is_frozen(self) -> None:
        preset = PRESETS[ProcessPresetName.FLOW]
        with pytest.raises(AttributeError):
            preset.gain = 999.0  # type: ignore[misc]

    def test_flow_preset_is_foptd(self) -> None:
        p = PRESETS[ProcessPresetName.FLOW]
        assert p.tau2 is None
        assert p.gain == 1.2
        assert p.tau1 == 3.0
        assert p.dead_time == 1.0

    def test_pressure_preset_is_foptd(self) -> None:
        p = PRESETS[ProcessPresetName.PRESSURE]
        assert p.tau2 is None
        assert p.gain == 0.8

    def test_level_preset_is_soptd(self) -> None:
        p = PRESETS[ProcessPresetName.LEVEL]
        assert p.tau2 is not None
        assert p.gain == 2.0
        assert p.tau1 == 30.0
        assert p.tau2 == 15.0

    def test_temperature_preset_is_soptd(self) -> None:
        p = PRESETS[ProcessPresetName.TEMPERATURE]
        assert p.tau2 is not None
        assert p.gain == 1.5
        assert p.tau2 == 20.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_process_preset.py -v`
Expected: ImportError — `models.process_preset` does not exist yet

- [ ] **Step 3: Implement ProcessPreset and PRESETS**

Create `packages/smart_pid_domain/src/smart_pid_domain/models/process_preset.py`:

```python
"""Process model presets — shared between core (ProcessModel) and HMI (SimulatorPage)."""
from __future__ import annotations

from dataclasses import dataclass

from smart_pid_domain.enums import ProcessPresetName


@dataclass(frozen=True)
class ProcessPreset:
    """Immutable process model parameters for a simulator preset."""

    name: ProcessPresetName
    gain: float
    tau1: float
    tau2: float | None
    dead_time: float


PRESETS: dict[ProcessPresetName, ProcessPreset] = {
    ProcessPresetName.FLOW: ProcessPreset(
        name=ProcessPresetName.FLOW, gain=1.2, tau1=3.0, tau2=None, dead_time=1.0,
    ),
    ProcessPresetName.PRESSURE: ProcessPreset(
        name=ProcessPresetName.PRESSURE, gain=0.8, tau1=10.0, tau2=None, dead_time=2.0,
    ),
    ProcessPresetName.LEVEL: ProcessPreset(
        name=ProcessPresetName.LEVEL, gain=2.0, tau1=30.0, tau2=15.0, dead_time=5.0,
    ),
    ProcessPresetName.TEMPERATURE: ProcessPreset(
        name=ProcessPresetName.TEMPERATURE, gain=1.5, tau1=60.0, tau2=20.0, dead_time=10.0,
    ),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_process_preset.py -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/models/process_preset.py \
       tests/domain/test_process_preset.py
git commit -m "feat(domain): add ProcessPreset dataclass and PRESETS registry"
```

---

## Task 3: ProcessModel — step response simulation with scipy.signal

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/services/process_models.py`
- Create: `tests/core/unit/test_process_models.py`

- [ ] **Step 1: Write failing tests for ProcessModel**

Create `tests/core/unit/test_process_models.py`:

```python
"""Tests for ProcessModel — FOPTD/SOPTD step response simulation."""
from __future__ import annotations

from smart_pid_core.domain.services.process_models import ProcessModel
from smart_pid_domain.enums import ProcessPresetName
from smart_pid_domain.models.process_preset import PRESETS


class TestProcessModel:
    def test_initial_pv_is_zero(self) -> None:
        model = ProcessModel(gain=1.0, tau1=5.0, tau2=None, dead_time=0.0)
        assert model.pv == 0.0

    def test_step_response_foptd_converges_to_gain(self) -> None:
        """FOPTD with K=2, tau=5, L=0: after many steps at CO=1.0, PV -> K*CO = 2.0."""
        model = ProcessModel(gain=2.0, tau1=5.0, tau2=None, dead_time=0.0)
        dt = 0.1
        for _ in range(500):
            model.step(co=1.0, dt=dt)
        assert abs(model.pv - 2.0) < 0.05

    def test_step_response_soptd_converges_to_gain(self) -> None:
        """SOPTD with K=1.5, tau1=10, tau2=5, L=0: PV -> 1.5."""
        model = ProcessModel(gain=1.5, tau1=10.0, tau2=5.0, dead_time=0.0)
        dt = 0.1
        for _ in range(1000):
            model.step(co=1.0, dt=dt)
        assert abs(model.pv - 1.5) < 0.05

    def test_dead_time_delays_response(self) -> None:
        """With L=2s, after 1s of simulation PV should still be near zero."""
        model = ProcessModel(gain=1.0, tau1=5.0, tau2=None, dead_time=2.0)
        dt = 0.1
        for _ in range(10):  # 1.0 seconds
            model.step(co=1.0, dt=dt)
        assert abs(model.pv) < 0.15  # still delayed

    def test_reset_returns_to_zero(self) -> None:
        model = ProcessModel(gain=1.0, tau1=5.0, tau2=None, dead_time=0.0)
        for _ in range(100):
            model.step(co=1.0, dt=0.1)
        assert model.pv > 0.5
        model.reset()
        assert model.pv == 0.0

    def test_zero_co_stays_at_zero(self) -> None:
        model = ProcessModel(gain=1.0, tau1=5.0, tau2=None, dead_time=0.0)
        for _ in range(50):
            model.step(co=0.0, dt=0.1)
        assert abs(model.pv) < 1e-10

    def test_from_preset_creates_model(self) -> None:
        preset = PRESETS[ProcessPresetName.TEMPERATURE]
        model = ProcessModel.from_preset(preset)
        assert model.pv == 0.0
        # Should use Temperature params
        for _ in range(2000):
            model.step(co=1.0, dt=0.1)
        assert abs(model.pv - preset.gain) < 0.1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_process_models.py -v`
Expected: ImportError — `process_models` module does not exist yet

- [ ] **Step 3: Implement ProcessModel**

Create `packages/smart_pid_core/src/smart_pid_core/domain/services/process_models.py`:

```python
"""Process models for simulator — FOPTD/SOPTD via scipy.signal."""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from scipy import signal

if TYPE_CHECKING:
    from smart_pid_domain.models.process_preset import ProcessPreset

_PADE_ORDER = 3


def _build_tf(
    gain: float, tau1: float, tau2: float | None, dead_time: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Build continuous-time transfer function numerator/denominator arrays.

    FOPTD: G(s) = K / (tau1*s + 1) * Pade(L)
    SOPTD: G(s) = K / ((tau1*s + 1)(tau2*s + 1)) * Pade(L)
    """
    # Process part
    if tau2 is not None and tau2 > 0:
        num_p = [gain]
        den_p = np.polymul([tau1, 1.0], [tau2, 1.0])
    else:
        num_p = [gain]
        den_p = [tau1, 1.0]

    # Dead time via Padé approximation
    if dead_time > 0:
        num_d, den_d = signal.pade(dead_time, _PADE_ORDER)
        num = np.polymul(num_p, num_d)
        den = np.polymul(den_p, den_d)
    else:
        num = np.array(num_p, dtype=float)
        den = np.array(den_p, dtype=float)

    return num, den


class ProcessModel:
    """Continuous-time process model simulated step-by-step.

    Uses scipy.signal.cont2discrete to convert the transfer function to
    a discrete-time state-space representation, then advances one sample
    per call to step().
    """

    def __init__(
        self,
        gain: float,
        tau1: float,
        tau2: float | None,
        dead_time: float,
    ) -> None:
        self._gain = gain
        self._tau1 = tau1
        self._tau2 = tau2
        self._dead_time = dead_time
        self._dt: float = 0.0  # will be set on first step()
        self._state: np.ndarray | None = None
        self._Ad: np.ndarray | None = None
        self._Bd: np.ndarray | None = None
        self._Cd: np.ndarray | None = None
        self._Dd: np.ndarray | None = None
        self._pv: float = 0.0

    @classmethod
    def from_preset(cls, preset: ProcessPreset) -> ProcessModel:
        return cls(
            gain=preset.gain, tau1=preset.tau1,
            tau2=preset.tau2, dead_time=preset.dead_time,
        )

    @property
    def pv(self) -> float:
        return self._pv

    def _discretize(self, dt: float) -> None:
        """(Re-)discretize the continuous TF at the given sample period."""
        num, den = _build_tf(self._gain, self._tau1, self._tau2, self._dead_time)
        sys_c = signal.tf2ss(num, den)
        sys_d = signal.cont2discrete(sys_c, dt, method="zoh")
        self._Ad, self._Bd, self._Cd, self._Dd = (
            np.asarray(sys_d[0]),
            np.asarray(sys_d[1]),
            np.asarray(sys_d[2]),
            np.asarray(sys_d[3]),
        )
        n = self._Ad.shape[0]
        if self._state is None or self._state.shape[0] != n:
            self._state = np.zeros((n, 1))
        self._dt = dt

    def step(self, co: float, dt: float) -> float:
        """Advance one time step. Returns the new PV value."""
        if dt != self._dt or self._Ad is None:
            self._discretize(dt)

        u = np.array([[co]])
        y = self._Cd @ self._state + self._Dd @ u
        self._state = self._Ad @ self._state + self._Bd @ u
        self._pv = float(y[0, 0])
        return self._pv

    def reset(self) -> None:
        """Reset internal state to initial conditions (PV=0)."""
        if self._state is not None:
            self._state[:] = 0.0
        self._pv = 0.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_process_models.py -v`
Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/services/process_models.py \
       tests/core/unit/test_process_models.py
git commit -m "feat(core): add ProcessModel with FOPTD/SOPTD step simulation via scipy.signal"
```

---

## Task 4: Simulator DTOs

**Files:**
- Create: `packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py`
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py`
- Create: `tests/domain/test_simulator_dtos.py`

- [ ] **Step 1: Write failing tests for simulator DTOs**

Create `tests/domain/test_simulator_dtos.py`:

```python
"""Tests for simulator request/response DTOs."""
from __future__ import annotations

from smart_pid_domain.dtos.simulator import (
    ControllerSimStatus,
    SimulatorDisturbanceRequest,
    SimulatorParametersRequest,
    SimulatorPresetRequest,
    SimulatorStatusResponse,
)
from smart_pid_domain.enums import ProcessPresetName


class TestSimulatorPresetRequest:
    def test_valid(self) -> None:
        req = SimulatorPresetRequest(controller_id=1, preset=ProcessPresetName.FLOW)
        assert req.controller_id == 1
        assert req.preset == ProcessPresetName.FLOW

    def test_from_json(self) -> None:
        req = SimulatorPresetRequest.model_validate(
            {"controller_id": 1, "preset": "FLOW"}
        )
        assert req.preset == ProcessPresetName.FLOW


class TestSimulatorParametersRequest:
    def test_foptd_no_tau2(self) -> None:
        req = SimulatorParametersRequest(
            controller_id=1, gain=1.0, tau1=5.0, dead_time=1.0,
        )
        assert req.tau2 is None

    def test_soptd_with_tau2(self) -> None:
        req = SimulatorParametersRequest(
            controller_id=1, gain=1.0, tau1=5.0, tau2=3.0, dead_time=1.0,
        )
        assert req.tau2 == 3.0


class TestSimulatorDisturbanceRequest:
    def test_step_type(self) -> None:
        req = SimulatorDisturbanceRequest(
            controller_id=1, type="step", amplitude=5.0,
        )
        assert req.type == "step"

    def test_noise_type(self) -> None:
        req = SimulatorDisturbanceRequest(
            controller_id=1, type="noise", amplitude=0.5,
        )
        assert req.type == "noise"


class TestControllerSimStatus:
    def test_no_disturbances(self) -> None:
        s = ControllerSimStatus(
            preset="FLOW", gain=1.2, tau1=3.0, tau2=None, dead_time=1.0,
            step_active=False, step_amplitude=0.0,
            noise_active=False, noise_amplitude=0.0,
        )
        assert not s.step_active
        assert not s.noise_active


class TestSimulatorStatusResponse:
    def test_enabled(self) -> None:
        s = SimulatorStatusResponse(enabled=True, controllers={})
        assert s.enabled
        assert s.controllers == {}

    def test_with_controllers(self) -> None:
        ctrl = ControllerSimStatus(
            preset="FLOW", gain=1.2, tau1=3.0, tau2=None, dead_time=1.0,
            step_active=True, step_amplitude=5.0,
            noise_active=False, noise_amplitude=0.0,
        )
        s = SimulatorStatusResponse(enabled=True, controllers={1: ctrl})
        assert s.controllers[1].step_active
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_simulator_dtos.py -v`
Expected: ImportError — `dtos.simulator` does not exist yet

- [ ] **Step 3: Implement simulator DTOs**

Create `packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py`:

```python
"""Simulator request/response DTOs."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from smart_pid_domain.enums import ProcessPresetName


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


class SimulatorStatusResponse(BaseModel):
    enabled: bool
    controllers: dict[int, ControllerSimStatus]
```

- [ ] **Step 4: Export DTOs from __init__.py**

In `packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py`, add the imports:

```python
from smart_pid_domain.dtos.simulator import (
    ControllerSimStatus,
    SimulatorDisturbanceRequest,
    SimulatorParametersRequest,
    SimulatorPresetRequest,
    SimulatorStatusResponse,
)
```

And add to `__all__`:

```python
    "ControllerSimStatus",
    "SimulatorDisturbanceRequest",
    "SimulatorParametersRequest",
    "SimulatorPresetRequest",
    "SimulatorStatusResponse",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_simulator_dtos.py -v`
Expected: all 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py \
       packages/smart_pid_domain/src/smart_pid_domain/dtos/__init__.py \
       tests/domain/test_simulator_dtos.py
git commit -m "feat(domain): add simulator request/response DTOs"
```

---

## Task 5: SimulatorAdapter — core closed-loop simulation

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`
- Create: `tests/core/unit/test_simulator_adapter.py`

- [ ] **Step 1: Write failing tests for SimulatorAdapter**

Create `tests/core/unit/test_simulator_adapter.py`:

```python
"""Tests for SimulatorAdapter — TelemetrySource + ControlWriter."""
from __future__ import annotations

import time
from queue import SimpleQueue

import pytest

from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import ProcessPresetName


@pytest.fixture
def settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]


@pytest.fixture
def adapter(settings: CoreSettings) -> SimulatorAdapter:
    a = SimulatorAdapter(settings=settings)
    yield a
    a.stop()


class TestSimulatorAdapterInit:
    def test_queue_is_simple_queue(self, adapter: SimulatorAdapter) -> None:
        assert isinstance(adapter.queue, SimpleQueue)

    def test_not_running_initially(self, adapter: SimulatorAdapter) -> None:
        assert not adapter.is_running


class TestSimulatorAdapterPresets:
    def test_set_preset_flow(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.FLOW)
        status = adapter.get_controller_status(1)
        assert status.preset == "FLOW"
        assert status.gain == 1.2
        assert status.tau1 == 3.0
        assert status.tau2 is None

    def test_set_preset_temperature(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.TEMPERATURE)
        status = adapter.get_controller_status(1)
        assert status.preset == "TEMPERATURE"
        assert status.tau2 == 20.0

    def test_set_parameters_custom(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_parameters(1, gain=3.0, tau1=15.0, tau2=8.0, dead_time=4.0)
        status = adapter.get_controller_status(1)
        assert status.gain == 3.0
        assert status.tau2 == 8.0
        assert status.preset == "CUSTOM"


class TestSimulatorAdapterDisturbances:
    def test_inject_step(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.inject_step(1, amplitude=5.0)
        status = adapter.get_controller_status(1)
        assert status.step_active is True
        assert status.step_amplitude == 5.0

    def test_inject_noise(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.inject_noise(1, amplitude=0.5)
        status = adapter.get_controller_status(1)
        assert status.noise_active is True
        assert status.noise_amplitude == 0.5

    def test_clear_disturbance(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.inject_step(1, amplitude=5.0)
        adapter.inject_noise(1, amplitude=0.5)
        adapter.clear_disturbance(1)
        status = adapter.get_controller_status(1)
        assert status.step_active is False
        assert status.noise_active is False


class TestSimulatorAdapterWriteOutput:
    def test_write_output_stores_co(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.write_output(1, 42.0)
        # CO is stored internally, reflected on next cycle
        assert adapter._controllers[1].last_co == 42.0


class TestSimulatorAdapterRunning:
    def test_start_stop_produces_telemetry(self, adapter: SimulatorAdapter) -> None:
        adapter.register_controller(1)
        adapter.set_preset(1, ProcessPresetName.FLOW)
        adapter.start()
        assert adapter.is_running
        # Wait for at least 2 cycles
        time.sleep(0.15)
        adapter.stop()
        assert not adapter.is_running
        # Should have produced telemetry frames
        frames = []
        while not adapter.queue.empty():
            frames.append(adapter.queue.get_nowait())
        assert len(frames) >= 1
        assert frames[0].controller_id == 1

    def test_write_parameter_is_noop(self, adapter: SimulatorAdapter) -> None:
        """write_parameter satisfies ControlWriter protocol but is a no-op for simulator."""
        adapter.register_controller(1)
        adapter.write_parameter(1, "gain", 2.0)  # Should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py -v`
Expected: ImportError — `simulator_adapter` module does not exist yet

- [ ] **Step 3: Implement SimulatorAdapter**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py`:

```python
"""SimulatorAdapter — digital twin implementing TelemetrySource + ControlWriter."""
from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from queue import SimpleQueue
from typing import TYPE_CHECKING

from smart_pid_core.domain.services.process_models import ProcessModel
from smart_pid_domain.dtos.simulator import ControllerSimStatus
from smart_pid_domain.enums import ProcessPresetName, SignalStatus
from smart_pid_domain.models.process_preset import PRESETS
from smart_pid_domain.models.telemetry import TelemetryFrame

if TYPE_CHECKING:
    from smart_pid_core.config import CoreSettings

logger = logging.getLogger(__name__)


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


class SimulatorAdapter:
    """Digital twin adapter — TelemetrySource + ControlWriter.

    Runs a daemon thread that steps each registered ProcessModel at a
    configurable interval, producing TelemetryFrames on a SimpleQueue.
    """

    def __init__(self, settings: CoreSettings) -> None:
        self._settings = settings
        self._queue: SimpleQueue[TelemetryFrame] = SimpleQueue()
        self._controllers: dict[int, _ControllerSim] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ── TelemetrySource protocol ─────────────────────────────────────

    @property
    def queue(self) -> SimpleQueue[TelemetryFrame]:
        return self._queue

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="simulator")
        self._thread.start()
        logger.info("Simulator started (interval=%dms)", self._settings.simulator_interval_ms)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        logger.info("Simulator stopped")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ── ControlWriter protocol ───────────────────────────────────────

    def write_output(self, controller_id: int, co: float) -> None:
        with self._lock:
            ctrl = self._controllers.get(controller_id)
            if ctrl is not None:
                ctrl.last_co = co

    def write_parameter(self, controller_id: int, param: str, value: float) -> None:
        """No-op for simulator — satisfies ControlWriter protocol."""

    # ── Simulator control (REST layer calls these) ───────────────────

    def register_controller(self, controller_id: int) -> None:
        with self._lock:
            if controller_id not in self._controllers:
                self._controllers[controller_id] = _ControllerSim(
                    controller_id=controller_id,
                )

    def set_preset(self, controller_id: int, preset: ProcessPresetName) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            p = PRESETS[preset]
            ctrl.model = ProcessModel.from_preset(p)
            ctrl.preset_name = preset.value
            ctrl.gain = p.gain
            ctrl.tau1 = p.tau1
            ctrl.tau2 = p.tau2
            ctrl.dead_time = p.dead_time

    def set_parameters(
        self, controller_id: int, gain: float, tau1: float,
        tau2: float | None, dead_time: float,
    ) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.model = ProcessModel(gain=gain, tau1=tau1, tau2=tau2, dead_time=dead_time)
            ctrl.preset_name = "CUSTOM"
            ctrl.gain = gain
            ctrl.tau1 = tau1
            ctrl.tau2 = tau2
            ctrl.dead_time = dead_time

    def inject_step(self, controller_id: int, amplitude: float) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.step_active = True
            ctrl.step_amplitude = amplitude

    def inject_noise(self, controller_id: int, amplitude: float) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.noise_active = True
            ctrl.noise_amplitude = amplitude

    def clear_disturbance(self, controller_id: int) -> None:
        with self._lock:
            ctrl = self._controllers[controller_id]
            ctrl.step_active = False
            ctrl.step_amplitude = 0.0
            ctrl.noise_active = False
            ctrl.noise_amplitude = 0.0

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
            )

    def get_status(self) -> dict[int, ControllerSimStatus]:
        with self._lock:
            return {
                cid: ControllerSimStatus(
                    preset=ctrl.preset_name,
                    gain=ctrl.gain,
                    tau1=ctrl.tau1,
                    tau2=ctrl.tau2,
                    dead_time=ctrl.dead_time,
                    step_active=ctrl.step_active,
                    step_amplitude=ctrl.step_amplitude,
                    noise_active=ctrl.noise_active,
                    noise_amplitude=ctrl.noise_amplitude,
                )
                for cid, ctrl in self._controllers.items()
            }

    # ── Simulation loop ──────────────────────────────────────────────

    def _run_loop(self) -> None:
        interval_s = self._settings.simulator_interval_ms / 1000.0
        while not self._stop_event.is_set():
            start = time.monotonic()
            self._tick(interval_s)
            elapsed = time.monotonic() - start
            sleep_time = interval_s - elapsed
            if sleep_time > 0:
                self._stop_event.wait(timeout=sleep_time)

    def _tick(self, dt: float) -> None:
        with self._lock:
            for ctrl in self._controllers.values():
                pv = ctrl.model.step(co=ctrl.last_co, dt=dt)

                # Apply disturbances
                if ctrl.step_active:
                    pv += ctrl.step_amplitude
                if ctrl.noise_active:
                    pv += random.gauss(0, ctrl.noise_amplitude)

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_simulator_adapter.py -v`
Expected: all 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py \
       tests/core/unit/test_simulator_adapter.py
git commit -m "feat(core): add SimulatorAdapter implementing TelemetrySource + ControlWriter"
```

---

## Task 6: AdapterFactory — conditional DI based on settings

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/factory.py`
- Create: `tests/core/unit/test_adapter_factory.py`

- [ ] **Step 1: Write failing tests for AdapterFactory**

Create `tests/core/unit/test_adapter_factory.py`:

```python
"""Tests for AdapterFactory — conditional dependency injection."""
from __future__ import annotations

import pytest

from smart_pid_core.adapters.factory import AdapterFactory
from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_core.config import CoreSettings


@pytest.fixture
def sim_settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]


@pytest.fixture
def prod_settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=False,
    )  # type: ignore[call-arg]


class TestAdapterFactorySimulator:
    def test_creates_simulator_adapter(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        adapter = factory.telemetry_source
        assert isinstance(adapter, SimulatorAdapter)

    def test_same_instance_for_both_ports(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        assert factory.telemetry_source is factory.control_writer

    def test_simulator_adapter_property(self, sim_settings: CoreSettings) -> None:
        factory = AdapterFactory(sim_settings)
        assert factory.simulator_adapter is not None


class TestAdapterFactoryProduction:
    def test_telemetry_source_raises(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        with pytest.raises(NotImplementedError, match="OPC-UA"):
            _ = factory.telemetry_source

    def test_control_writer_raises(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        with pytest.raises(NotImplementedError, match="OPC-UA"):
            _ = factory.control_writer

    def test_simulator_adapter_is_none(self, prod_settings: CoreSettings) -> None:
        factory = AdapterFactory(prod_settings)
        assert factory.simulator_adapter is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_adapter_factory.py -v`
Expected: ImportError — `factory` module does not exist yet

- [ ] **Step 3: Implement AdapterFactory**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/factory.py`:

```python
"""AdapterFactory — centralized DI based on CoreSettings."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_core.config import CoreSettings


class AdapterFactory:
    """Creates and caches adapter instances based on configuration.

    When simulator is enabled, the same SimulatorAdapter serves as both
    TelemetrySource and ControlWriter.
    """

    def __init__(self, settings: CoreSettings) -> None:
        self._settings = settings
        self._simulator_adapter = None

        if settings.simulator_enabled:
            from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter

            self._simulator_adapter = SimulatorAdapter(settings=settings)

    @property
    def telemetry_source(self):
        """Return the TelemetrySource adapter."""
        if self._settings.simulator_enabled:
            return self._simulator_adapter
        raise NotImplementedError("OPC-UA client not yet implemented (Phase 3b)")

    @property
    def control_writer(self):
        """Return the ControlWriter adapter."""
        if self._settings.simulator_enabled:
            return self._simulator_adapter
        raise NotImplementedError("OPC-UA writer not yet implemented (Phase 3b)")

    @property
    def simulator_adapter(self):
        """Return the SimulatorAdapter if simulator is enabled, else None."""
        return self._simulator_adapter
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_adapter_factory.py -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/factory.py \
       tests/core/unit/test_adapter_factory.py
git commit -m "feat(core): add AdapterFactory for conditional DI (simulator vs production)"
```

---

## Task 7: REST simulator endpoints

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
- Create: `tests/core/integration/test_api_simulator.py`

- [ ] **Step 1: Write failing tests for simulator REST endpoints**

Create `tests/core/integration/test_api_simulator.py`:

```python
"""Tests for /simulator REST endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_core.config import CoreSettings


@pytest.fixture
def sim_settings() -> CoreSettings:
    return CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]


@pytest.fixture
def simulator_adapter(sim_settings: CoreSettings) -> SimulatorAdapter:
    adapter = SimulatorAdapter(settings=sim_settings)
    adapter.register_controller(1)
    yield adapter
    adapter.stop()


class TestGetStatus:
    @pytest.mark.asyncio
    async def test_status_returns_enabled(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        resp = await client_with_simulator.get("/simulator/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_status_requires_auth(
        self, client_with_simulator: AsyncClient,
    ) -> None:
        resp = await client_with_simulator.get("/simulator/status")
        assert resp.status_code == 401


class TestSetPreset:
    @pytest.mark.asyncio
    async def test_set_flow_preset(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        resp = await client_with_simulator.post(
            "/simulator/preset",
            json={"controller_id": 1, "preset": "FLOW"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestSetParameters:
    @pytest.mark.asyncio
    async def test_set_custom_parameters(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        resp = await client_with_simulator.put(
            "/simulator/parameters",
            json={"controller_id": 1, "gain": 3.0, "tau1": 15.0, "tau2": 8.0, "dead_time": 4.0},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestDisturbance:
    @pytest.mark.asyncio
    async def test_inject_step(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        resp = await client_with_simulator.post(
            "/simulator/disturbance",
            json={"controller_id": 1, "type": "step", "amplitude": 5.0},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_clear_disturbance(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        # Inject first
        await client_with_simulator.post(
            "/simulator/disturbance",
            json={"controller_id": 1, "type": "step", "amplitude": 5.0},
            headers=admin_headers,
        )
        # Clear
        resp = await client_with_simulator.delete(
            "/simulator/disturbance/1",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
```

- [ ] **Step 2: Add `client_with_simulator` fixture to conftest.py**

In `tests/conftest.py`, add these fixtures after the existing ones:

```python
@pytest.fixture
async def sim_api_deps(tmp_path):
    """Create all dependencies for API testing with simulator enabled."""
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    user_repo = UserRepository(repo.db)
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(
        jwt_secret="test-secret-key-minimum-32-bytes!",
        simulator_enabled=True,
        simulator_interval_ms=50,
    )  # type: ignore[call-arg]

    # Seed admin user
    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, "admin")

    from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter

    simulator_adapter = SimulatorAdapter(settings=settings)
    simulator_adapter.register_controller(1)

    yield {
        "repo": repo,
        "historian": historian,
        "user_repo": user_repo,
        "loop_manager": loop_manager,
        "settings": settings,
        "bus": bus,
        "simulator_adapter": simulator_adapter,
    }
    simulator_adapter.stop()
    loop_manager.stop_all()
    bus.stop()


@pytest.fixture
async def app_with_simulator(sim_api_deps):
    """Create FastAPI app with simulator enabled."""
    return create_app(
        repo=sim_api_deps["repo"],
        historian=sim_api_deps["historian"],
        user_repo=sim_api_deps["user_repo"],
        loop_manager=sim_api_deps["loop_manager"],
        settings=sim_api_deps["settings"],
        simulator_adapter=sim_api_deps["simulator_adapter"],
    )


@pytest.fixture
async def client_with_simulator(app_with_simulator):
    """httpx AsyncClient with simulator-enabled ASGI transport."""
    transport = httpx.ASGITransport(app=app_with_simulator)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

Note: the `admin_headers` fixture from the existing `api_deps` won't be available here since `sim_api_deps` is a separate fixture. We need to also add:

```python
@pytest.fixture
def admin_headers_sim(sim_api_deps) -> dict[str, str]:
    """Pre-authenticated admin JWT headers for simulator tests."""
    token = create_access_token(
        user_id=1, username="admin", role="admin",
        secret=sim_api_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}
```

**Important:** Update the test file to use `admin_headers_sim` OR make `admin_headers` work with both fixtures. The simplest approach: update tests to request `sim_api_deps` directly and generate the token inline. However, the cleaner approach is to update tests to use a shared pattern.

**Actually, the simplest fix:** update test_api_simulator.py fixtures to be self-contained. Replace the `admin_headers` references with a local fixture:

In `tests/core/integration/test_api_simulator.py`, add at the top:

```python
from smart_pid_core.adapters.inbound.api.auth import create_access_token

@pytest.fixture
def admin_headers(sim_api_deps) -> dict[str, str]:
    token = create_access_token(
        user_id=1, username="admin", role="admin",
        secret=sim_api_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}
```

Wait — this creates a circular dependency issue because `client_with_simulator` depends on `sim_api_deps` and `admin_headers` also depends on `sim_api_deps`. That's fine, pytest resolves this correctly.

**Revised complete test file** `tests/core/integration/test_api_simulator.py`:

```python
"""Tests for /simulator REST endpoints."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from smart_pid_core.adapters.inbound.api.auth import create_access_token


@pytest.fixture
def admin_headers(sim_api_deps) -> dict[str, str]:
    token = create_access_token(
        user_id=1, username="admin", role="admin",
        secret=sim_api_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}


class TestGetStatus:
    @pytest.mark.asyncio
    async def test_status_returns_enabled(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        resp = await client_with_simulator.get("/simulator/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_status_requires_auth(
        self, client_with_simulator: AsyncClient,
    ) -> None:
        resp = await client_with_simulator.get("/simulator/status")
        assert resp.status_code == 401


class TestSetPreset:
    @pytest.mark.asyncio
    async def test_set_flow_preset(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        resp = await client_with_simulator.post(
            "/simulator/preset",
            json={"controller_id": 1, "preset": "FLOW"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestSetParameters:
    @pytest.mark.asyncio
    async def test_set_custom_parameters(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        resp = await client_with_simulator.put(
            "/simulator/parameters",
            json={"controller_id": 1, "gain": 3.0, "tau1": 15.0, "tau2": 8.0, "dead_time": 4.0},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


class TestDisturbance:
    @pytest.mark.asyncio
    async def test_inject_step(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        resp = await client_with_simulator.post(
            "/simulator/disturbance",
            json={"controller_id": 1, "type": "step", "amplitude": 5.0},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_clear_disturbance(
        self,
        client_with_simulator: AsyncClient,
        admin_headers: dict[str, str],
    ) -> None:
        await client_with_simulator.post(
            "/simulator/disturbance",
            json={"controller_id": 1, "type": "step", "amplitude": 5.0},
            headers=admin_headers,
        )
        resp = await client_with_simulator.delete(
            "/simulator/disturbance/1",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_api_simulator.py -v`
Expected: ImportError or fixture errors — router and fixtures don't exist yet

- [ ] **Step 4: Add get_simulator_adapter dependency**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`, add:

```python
from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter

def get_simulator_adapter(request: Request) -> SimulatorAdapter:
    adapter = getattr(request.app.state, "simulator_adapter", None)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulator not enabled",
        )
    return adapter
```

Note: the import of `SimulatorAdapter` should be under `TYPE_CHECKING` to avoid import at module level. Update to:

```python
if TYPE_CHECKING:
    from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
    ...

def get_simulator_adapter(request: Request) -> SimulatorAdapter:
    adapter = getattr(request.app.state, "simulator_adapter", None)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Simulator not enabled",
        )
    return adapter
```

- [ ] **Step 5: Implement simulator router**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py`:

```python
"""Simulator control router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_current_user,
    get_simulator_adapter,
)
from smart_pid_core.adapters.inbound.simulator_adapter import SimulatorAdapter
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.commands import CommandResponse
from smart_pid_domain.dtos.simulator import (
    SimulatorDisturbanceRequest,
    SimulatorParametersRequest,
    SimulatorPresetRequest,
    SimulatorStatusResponse,
)

router = APIRouter()


@router.get("/status", response_model=SimulatorStatusResponse)
async def get_status(
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> SimulatorStatusResponse:
    return SimulatorStatusResponse(
        enabled=True,
        controllers=adapter.get_status(),
    )


@router.post("/preset", response_model=CommandResponse)
async def set_preset(
    body: SimulatorPresetRequest,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.set_preset(body.controller_id, body.preset)
    return CommandResponse(ok=True, controller_id=body.controller_id, detail="Preset applied")


@router.put("/parameters", response_model=CommandResponse)
async def set_parameters(
    body: SimulatorParametersRequest,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.set_parameters(
        body.controller_id, body.gain, body.tau1, body.tau2, body.dead_time,
    )
    return CommandResponse(ok=True, controller_id=body.controller_id, detail="Parameters updated")


@router.post("/disturbance", response_model=CommandResponse)
async def inject_disturbance(
    body: SimulatorDisturbanceRequest,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    if body.type == "step":
        adapter.inject_step(body.controller_id, body.amplitude)
    else:
        adapter.inject_noise(body.controller_id, body.amplitude)
    return CommandResponse(
        ok=True, controller_id=body.controller_id,
        detail=f"{body.type} disturbance injected",
    )


@router.delete("/disturbance/{controller_id}", response_model=CommandResponse)
async def clear_disturbance(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    adapter: Annotated[SimulatorAdapter, Depends(get_simulator_adapter)],
) -> CommandResponse:
    adapter.clear_disturbance(controller_id)
    return CommandResponse(ok=True, controller_id=controller_id, detail="Disturbances cleared")
```

- [ ] **Step 6: Register simulator router in app.py**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`:

Add import:
```python
from smart_pid_core.adapters.inbound.api.routers import (
    auth,
    commands,
    controllers,
    history,
    simulator,
    system,
)
```

Update `create_app` signature to accept optional `simulator_adapter`:

```python
def create_app(
    *,
    repo: SQLiteRepository,
    historian: SQLiteHistorian,
    user_repo: UserRepository,
    loop_manager: LoopManager,
    settings: CoreSettings,
    simulator_adapter: object | None = None,
) -> FastAPI:
```

Add after `app.state.settings = settings`:

```python
    app.state.simulator_adapter = simulator_adapter
```

Add after the history router registration:

```python
    app.include_router(simulator.router, prefix="/simulator", tags=["simulator"])
```

- [ ] **Step 7: Add conftest fixtures for simulator tests**

In `tests/conftest.py`, add the `sim_api_deps`, `app_with_simulator`, and `client_with_simulator` fixtures as described in Step 2 above.

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_api_simulator.py -v`
Expected: all 5 tests PASS

- [ ] **Step 9: Verify existing tests still pass**

Run: `uv run pytest tests/ -v`
Expected: all existing + new tests PASS. The existing `create_app` calls don't pass `simulator_adapter`, which defaults to `None`.

- [ ] **Step 10: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py \
       tests/core/integration/test_api_simulator.py \
       tests/conftest.py
git commit -m "feat(core): add REST /simulator endpoints with AdapterFactory integration"
```

---

## Task 8: Wire SimulatorAdapter into backend daemon main.py

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py`

- [ ] **Step 1: Update run_daemon to use AdapterFactory**

In `packages/smart_pid_core/src/smart_pid_core/main.py`, add import:

```python
from smart_pid_core.adapters.factory import AdapterFactory
```

After the `loop_manager` creation and before `create_app`, add:

```python
    # Phase 4: Adapter factory (simulator or OPC-UA)
    adapter_factory = AdapterFactory(settings)
    simulator_adapter = adapter_factory.simulator_adapter
    if simulator_adapter is not None:
        # Register all controllers from DB for simulation
        controllers = await repo.list_all()
        for ctrl in controllers:
            simulator_adapter.register_controller(ctrl.id)
        simulator_adapter.start()
        logger.info("simulator_started", port=settings.simulator_port)
```

Update `create_app` call to pass `simulator_adapter`:

```python
    app = create_app(
        repo=repo,
        historian=historian,
        user_repo=user_repo,
        loop_manager=loop_manager,
        settings=settings,
        simulator_adapter=simulator_adapter,
    )
```

In the shutdown section, before `loop_manager.stop_all()`, add:

```python
    if simulator_adapter is not None:
        simulator_adapter.stop()
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `uv run pytest tests/ -v`
Expected: all tests PASS (main.py isn't directly tested by unit tests, but API tests should still work)

- [ ] **Step 3: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/main.py
git commit -m "feat(core): wire SimulatorAdapter into backend daemon lifecycle"
```

---

## Task 9: HMI APIClient — simulator methods

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`
- Modify: `tests/hmi/services/test_api_client.py`

- [ ] **Step 1: Write failing tests for new API client methods**

In `tests/hmi/services/test_api_client.py`, add tests. First read the existing file to understand the pattern, then add:

```python
class TestSimulatorMethods:
    def test_get_simulator_status(self, api_client, mock_transport):
        mock_transport.add_response(
            url="http://test/simulator/status",
            method="GET",
            json={"enabled": True, "controllers": {}},
        )
        result = api_client.get_simulator_status()
        assert result.enabled is True

    def test_set_simulator_preset(self, api_client, mock_transport):
        mock_transport.add_response(
            url="http://test/simulator/preset",
            method="POST",
            json={"ok": True, "controller_id": 1, "detail": "Preset applied"},
        )
        result = api_client.set_simulator_preset(1, "FLOW")
        assert result.ok is True

    def test_set_simulator_parameters(self, api_client, mock_transport):
        mock_transport.add_response(
            url="http://test/simulator/parameters",
            method="PUT",
            json={"ok": True, "controller_id": 1, "detail": "Updated"},
        )
        result = api_client.set_simulator_parameters(1, 3.0, 15.0, 8.0, 4.0)
        assert result.ok is True

    def test_inject_simulator_disturbance(self, api_client, mock_transport):
        mock_transport.add_response(
            url="http://test/simulator/disturbance",
            method="POST",
            json={"ok": True, "controller_id": 1, "detail": "step injected"},
        )
        result = api_client.inject_simulator_disturbance(1, "step", 5.0)
        assert result.ok is True

    def test_clear_simulator_disturbance(self, api_client, mock_transport):
        mock_transport.add_response(
            url="http://test/simulator/disturbance/1",
            method="DELETE",
            json={"ok": True, "controller_id": 1, "detail": "Cleared"},
        )
        result = api_client.clear_simulator_disturbance(1)
        assert result.ok is True
```

Note: Check the existing test_api_client.py for the exact mock transport pattern. The tests above assume a `mock_transport` fixture. If the existing tests use a different pattern (like `httpx.MockTransport`), adapt accordingly.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/services/test_api_client.py -v -k simulator`
Expected: AttributeError — methods don't exist on APIClient yet

- [ ] **Step 3: Add simulator methods to APIClient**

In `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`, add import:

```python
from smart_pid_domain.dtos.simulator import SimulatorStatusResponse
```

Add methods to the `APIClient` class:

```python
    def get_simulator_status(self) -> SimulatorStatusResponse:
        resp = self._http.get("/simulator/status", headers=self._headers())
        resp.raise_for_status()
        return SimulatorStatusResponse.model_validate(resp.json())

    def set_simulator_preset(self, controller_id: int, preset: str) -> CommandResponse:
        resp = self._http.post(
            "/simulator/preset",
            json={"controller_id": controller_id, "preset": preset},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def set_simulator_parameters(
        self, controller_id: int, gain: float, tau1: float,
        tau2: float | None, dead_time: float,
    ) -> CommandResponse:
        resp = self._http.put(
            "/simulator/parameters",
            json={
                "controller_id": controller_id, "gain": gain,
                "tau1": tau1, "tau2": tau2, "dead_time": dead_time,
            },
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def inject_simulator_disturbance(
        self, controller_id: int, dist_type: str, amplitude: float,
    ) -> CommandResponse:
        resp = self._http.post(
            "/simulator/disturbance",
            json={"controller_id": controller_id, "type": dist_type, "amplitude": amplitude},
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())

    def clear_simulator_disturbance(self, controller_id: int) -> CommandResponse:
        resp = self._http.delete(
            f"/simulator/disturbance/{controller_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return CommandResponse.model_validate(resp.json())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/hmi/services/test_api_client.py -v`
Expected: all tests PASS (existing + new)

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py \
       tests/hmi/services/test_api_client.py
git commit -m "feat(hmi): add simulator API methods to APIClient"
```

---

## Task 10: SimulatorPage — HMI simulator control page

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`
- Create: `tests/hmi/pages/test_simulator_page.py`

- [ ] **Step 1: Write failing tests for SimulatorPage**

Create `tests/hmi/pages/test_simulator_page.py`:

```python
"""Tests for SimulatorPage — preset selector, parameter sliders, disturbance controls."""
from __future__ import annotations

import pytest

from smart_pid_hmi.pages.simulator_page import SimulatorPage
from smart_pid_hmi.themes.isa101 import ISA101Theme


@pytest.fixture
def theme():
    return ISA101Theme()


def test_creation(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    assert page._preset_combo is not None
    assert page._gain_slider is not None
    assert page._tau1_slider is not None
    assert page._tau2_slider is not None
    assert page._dead_time_slider is not None


def test_preset_combo_has_all_options(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    items = [page._preset_combo.itemText(i) for i in range(page._preset_combo.count())]
    assert "FLOW" in items
    assert "PRESSURE" in items
    assert "LEVEL" in items
    assert "TEMPERATURE" in items
    assert "CUSTOM" in items


def test_tau2_disabled_for_foptd(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    page._preset_combo.setCurrentText("FLOW")
    page._on_preset_changed("FLOW")
    assert not page._tau2_slider.isEnabled()


def test_tau2_enabled_for_soptd(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    page._preset_combo.setCurrentText("LEVEL")
    page._on_preset_changed("LEVEL")
    assert page._tau2_slider.isEnabled()


def test_step_disturbance_signal(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.step_requested, timeout=1000) as blocker:
        page._step_amplitude.setValue(5.0)
        page._on_step_inject()
    assert blocker.args == [5.0]


def test_noise_disturbance_signal(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.noise_requested, timeout=1000) as blocker:
        page._noise_amplitude.setValue(0.5)
        page._on_noise_inject()
    assert blocker.args == [0.5]


def test_clear_disturbance_signal(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.clear_disturbance_requested, timeout=1000):
        page._on_clear_disturbance()


def test_preset_changed_signal(qtbot, theme):
    page = SimulatorPage(theme=theme)
    qtbot.addWidget(page)
    with qtbot.waitSignal(page.preset_changed, timeout=1000) as blocker:
        page._preset_combo.setCurrentText("TEMPERATURE")
        page._on_preset_selected(page._preset_combo.currentIndex())
    assert blocker.args[0] == "TEMPERATURE"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/pages/test_simulator_page.py -v`
Expected: ImportError — `simulator_page` module does not exist yet

- [ ] **Step 3: Implement SimulatorPage**

Create `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`:

```python
"""SimulatorPage — preset selection, parameter sliders, disturbance injection."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from smart_pid_domain.enums import ProcessPresetName
from smart_pid_domain.models.process_preset import PRESETS

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

# Slider range config: (min, max, default, decimals)
_PARAM_RANGES = {
    "gain": (0.1, 10.0, 1.2, 2),
    "tau1": (0.5, 120.0, 3.0, 1),
    "tau2": (0.5, 60.0, 15.0, 1),
    "dead_time": (0.0, 30.0, 1.0, 1),
}

# Which presets are FOPTD (tau2 disabled)
_FOPTD_PRESETS = {ProcessPresetName.FLOW, ProcessPresetName.PRESSURE}


class SimulatorPage(QWidget):
    """Simulator control page with preset selection, parameters, and disturbances."""

    # Signals emitted to MainWindow for API calls
    preset_changed = Signal(str)  # preset name
    parameters_changed = Signal(float, float, float, float)  # gain, tau1, tau2, dead_time
    step_requested = Signal(float)  # amplitude
    noise_requested = Signal(float)  # amplitude
    clear_disturbance_requested = Signal()

    def __init__(self, theme: ThemeBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("Simulator Control")
        title.setStyleSheet(
            f"font-size: {theme.font_size_title}px; font-weight: bold; "
            f"color: {theme.fg_primary};"
        )
        layout.addWidget(title)

        # Controller selector (populated externally)
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Controller:"))
        self._controller_combo = QComboBox()
        ctrl_row.addWidget(self._controller_combo, stretch=1)
        layout.addLayout(ctrl_row)

        # Preset group
        preset_group = QGroupBox("Process Model Preset")
        preset_layout = QHBoxLayout(preset_group)
        preset_layout.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        for p in ProcessPresetName:
            self._preset_combo.addItem(p.value)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self._preset_combo, stretch=1)
        layout.addWidget(preset_group)

        # Parameters group
        param_group = QGroupBox("Parameters")
        param_layout = QVBoxLayout(param_group)

        self._gain_slider = self._make_param_row(param_layout, "Gain (K):", "gain")
        self._tau1_slider = self._make_param_row(param_layout, "Tau1 (s):", "tau1")
        self._tau2_slider = self._make_param_row(param_layout, "Tau2 (s):", "tau2")
        self._dead_time_slider = self._make_param_row(param_layout, "Dead Time (s):", "dead_time")

        apply_btn = QPushButton("Apply Parameters")
        apply_btn.clicked.connect(self._on_apply_parameters)
        param_layout.addWidget(apply_btn)
        layout.addWidget(param_group)

        # Disturbance group
        dist_group = QGroupBox("Disturbances")
        dist_layout = QVBoxLayout(dist_group)

        step_row = QHBoxLayout()
        step_row.addWidget(QLabel("Step:"))
        self._step_amplitude = QDoubleSpinBox()
        self._step_amplitude.setRange(-50.0, 50.0)
        self._step_amplitude.setValue(5.0)
        self._step_amplitude.setSuffix(" %")
        step_row.addWidget(self._step_amplitude)
        step_btn = QPushButton("Inject Step")
        step_btn.clicked.connect(self._on_step_inject)
        step_row.addWidget(step_btn)
        dist_layout.addLayout(step_row)

        noise_row = QHBoxLayout()
        noise_row.addWidget(QLabel("Noise:"))
        self._noise_amplitude = QDoubleSpinBox()
        self._noise_amplitude.setRange(0.0, 10.0)
        self._noise_amplitude.setValue(0.5)
        self._noise_amplitude.setSuffix(" %")
        noise_row.addWidget(self._noise_amplitude)
        noise_btn = QPushButton("Inject Noise")
        noise_btn.clicked.connect(self._on_noise_inject)
        noise_row.addWidget(noise_btn)
        dist_layout.addLayout(noise_row)

        clear_btn = QPushButton("Clear All Disturbances")
        clear_btn.clicked.connect(self._on_clear_disturbance)
        dist_layout.addWidget(clear_btn)
        layout.addWidget(dist_group)

        # Status
        self._status_label = QLabel("Status: Ready")
        self._status_label.setStyleSheet(f"color: {theme.fg_secondary};")
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Apply initial preset
        self._on_preset_changed(self._preset_combo.currentText())

    def _make_param_row(
        self, layout: QVBoxLayout, label: str, key: str,
    ) -> QDoubleSpinBox:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        mn, mx, default, decimals = _PARAM_RANGES[key]
        spin = QDoubleSpinBox()
        spin.setRange(mn, mx)
        spin.setValue(default)
        spin.setDecimals(decimals)
        row.addWidget(spin, stretch=1)
        layout.addLayout(row)
        return spin

    def _on_preset_selected(self, index: int) -> None:
        text = self._preset_combo.itemText(index)
        self._on_preset_changed(text)
        self.preset_changed.emit(text)

    def _on_preset_changed(self, preset_name: str) -> None:
        try:
            preset_enum = ProcessPresetName(preset_name)
        except ValueError:
            return

        is_foptd = preset_enum in _FOPTD_PRESETS
        self._tau2_slider.setEnabled(not is_foptd)

        if preset_enum != ProcessPresetName.CUSTOM and preset_enum in PRESETS:
            p = PRESETS[preset_enum]
            self._gain_slider.setValue(p.gain)
            self._tau1_slider.setValue(p.tau1)
            self._tau2_slider.setValue(p.tau2 if p.tau2 is not None else 0.0)
            self._dead_time_slider.setValue(p.dead_time)

    def _on_apply_parameters(self) -> None:
        tau2 = self._tau2_slider.value() if self._tau2_slider.isEnabled() else 0.0
        self.parameters_changed.emit(
            self._gain_slider.value(),
            self._tau1_slider.value(),
            tau2,
            self._dead_time_slider.value(),
        )

    def _on_step_inject(self) -> None:
        self.step_requested.emit(self._step_amplitude.value())

    def _on_noise_inject(self) -> None:
        self.noise_requested.emit(self._noise_amplitude.value())

    def _on_clear_disturbance(self) -> None:
        self.clear_disturbance_requested.emit()

    def set_status_text(self, text: str) -> None:
        self._status_label.setText(f"Status: {text}")

    def populate_controllers(self, controllers: list[dict]) -> None:
        self._controller_combo.clear()
        for ctrl in controllers:
            self._controller_combo.addItem(ctrl["name"], ctrl["id"])

    @property
    def current_controller_id(self) -> int | None:
        data = self._controller_combo.currentData()
        return data if isinstance(data, int) else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/hmi/pages/test_simulator_page.py -v`
Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py \
       tests/hmi/pages/test_simulator_page.py
git commit -m "feat(hmi): add SimulatorPage with preset selector, parameter sliders, disturbance controls"
```

---

## Task 11: Integrate SimulatorPage into MainWindow

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`

- [ ] **Step 1: Add SimulatorPage import and toolbar button**

In `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`, add import:

```python
from smart_pid_hmi.pages.simulator_page import SimulatorPage
```

In `MainWindow.__init__`, after creating `self._dashboard_page` and before wiring signals, add:

```python
        self._simulator_page = SimulatorPage(theme=theme)
        self._stack.addWidget(self._simulator_page)
```

In the toolbar section, after `toolbar.addWidget(self._user_label)` and before `spacer = QWidget()`, add:

```python
        toolbar.addSeparator()
        self._dashboard_btn = toolbar.addAction("Dashboard")
        self._dashboard_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._dashboard_page)
        )
        self._simulator_btn = toolbar.addAction("Simulator")
        self._simulator_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._simulator_page)
        )
        self._simulator_btn.setEnabled(False)  # enabled after login if backend has simulator
```

After `self._dashboard_page.output_requested.connect(self._send_output)`, add signal wiring:

```python
        self._simulator_page.preset_changed.connect(self._send_sim_preset)
        self._simulator_page.parameters_changed.connect(self._send_sim_parameters)
        self._simulator_page.step_requested.connect(self._send_sim_step)
        self._simulator_page.noise_requested.connect(self._send_sim_noise)
        self._simulator_page.clear_disturbance_requested.connect(self._send_sim_clear)
```

- [ ] **Step 2: Add simulator command methods**

Add these methods to `MainWindow`:

```python
    def _check_simulator_available(self) -> None:
        """Check if backend has simulator and enable button if so."""
        def do_check():
            try:
                status = self._api_client.get_simulator_status()
                if status.enabled:
                    QMetaObject.invokeMethod(
                        self, "_enable_simulator", Qt.ConnectionType.QueuedConnection,
                    )
            except Exception:
                pass  # Not available — button stays disabled

        threading.Thread(target=do_check, daemon=True).start()

    @Slot()
    def _enable_simulator(self) -> None:
        self._simulator_btn.setEnabled(True)

    def _send_sim_preset(self, preset: str) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        threading.Thread(
            target=lambda: self._api_client.set_simulator_preset(cid, preset),
            daemon=True,
        ).start()

    def _send_sim_parameters(self, gain: float, tau1: float, tau2: float, dead_time: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        tau2_val = tau2 if tau2 > 0 else None
        threading.Thread(
            target=lambda: self._api_client.set_simulator_parameters(
                cid, gain, tau1, tau2_val, dead_time,
            ),
            daemon=True,
        ).start()

    def _send_sim_step(self, amplitude: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        threading.Thread(
            target=lambda: self._api_client.inject_simulator_disturbance(cid, "step", amplitude),
            daemon=True,
        ).start()

    def _send_sim_noise(self, amplitude: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        threading.Thread(
            target=lambda: self._api_client.inject_simulator_disturbance(cid, "noise", amplitude),
            daemon=True,
        ).start()

    def _send_sim_clear(self) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        threading.Thread(
            target=lambda: self._api_client.clear_simulator_disturbance(cid),
            daemon=True,
        ).start()
```

- [ ] **Step 3: Call _check_simulator_available after login**

In `_login_success`, after `self._stack.setCurrentWidget(self._dashboard_page)`, add:

```python
        self._check_simulator_available()
```

And in `_load_dashboard`, in the `do_load` callback, after populating controllers, also populate simulator page:

```python
                self._simulator_page.populate_controllers(
                    [c.model_dump() for c in controllers]
                )
```

Wait — `controllers` variable is already used differently. Let me re-check. In `_load_dashboard`, the `do_load` function does:

```python
controllers = self._api_client.list_controllers()
self._pending_controllers = [c.model_dump() for c in controllers]
```

So in `_populate_dashboard`, add:

```python
    @Slot()
    def _populate_dashboard(self) -> None:
        self._dashboard_page.populate_controllers(self._pending_controllers)
        self._simulator_page.populate_controllers(self._pending_controllers)
```

- [ ] **Step 4: Run all HMI tests**

Run: `uv run pytest tests/hmi/ -v`
Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/main.py
git commit -m "feat(hmi): integrate SimulatorPage into MainWindow with toolbar navigation"
```

---

## Task 12: Full test suite validation and lint

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 2: Run linter**

Run: `uv run --with ruff ruff check .`
Expected: no errors. If there are errors, fix them.

- [ ] **Step 3: Fix any lint issues**

Run: `uv run --with ruff ruff check --fix .`

- [ ] **Step 4: Run tests again after lint fixes**

Run: `uv run pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 5: Commit lint fixes if any**

```bash
git add -u
git commit -m "chore: fix lint issues from Phase 4 implementation"
```

---

## Deferred to Phase 4b (follow-up plan)

- **Embedded asyncua.Server** (OPC-UA on port 4841): The spec includes an embedded OPC-UA server managed by SimulatorAdapter. This is deferred to a second plan because: (a) the core closed-loop simulation works entirely through the SimpleQueue/TelemetrySource path, (b) asyncua requires an asyncio event loop which adds complexity to the threading model, and (c) the OPC-UA server is primarily for external client connectivity, not for the PID engine loop. A Phase 4b plan will add asyncua.Server lifecycle management inside SimulatorAdapter and node updates per simulation cycle.

---

## Notes for the implementing agent

1. **ControlWriter port is already defined** in `packages/smart_pid_core/src/smart_pid_core/domain/ports/outbound.py` with async methods. The SimulatorAdapter uses sync methods because it runs in a thread. The spec says SimulatorAdapter implements ControlWriter, but the existing protocol uses `async def`. You have two options:
   - Make SimulatorAdapter's `write_output`/`write_parameter` sync (simpler, the protocol is structural so it won't match the async version anyway)
   - The adapter is used directly, not through the protocol. Since PID workers call it from threads, sync is correct.

2. **OPC-UA server** (asyncua) is listed in the spec but is a lower-priority integration detail. The core value is the process model + closed loop. The OPC-UA server can be added in a follow-up task if time permits, since the main data flow uses the SimpleQueue/TelemetrySource path.

3. **The test for `test_api_client.py` (Task 8)** requires reading the existing test file first to understand the mock transport pattern. The pattern shown is approximate — adapt to whatever the existing tests use.

4. **Thread safety**: SimulatorAdapter uses `threading.Lock` for all controller state access. The simulation thread and the REST/PID threads both acquire this lock.

5. **ProcessPreset and PRESETS live in smart_pid_domain** (`models/process_preset.py`) so both core and HMI can import them without violating hexagonal boundaries. The ProcessModel (scipy-dependent) stays in core.
