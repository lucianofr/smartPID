# Phase 1: Foundation + PID Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold the Smart PID project and implement the PID control core — event bus, PID engine (velocity form), mode manager, workers, and SQLite persistence — so a PID loop can execute in a thread, receive telemetry via ZeroMQ, compute control output, and log to the database.

**Architecture:** Hexagonal + Event-Driven. Domain services (PID engine, mode manager) are pure Python with no external dependencies. The ZeroMQ event bus (inproc://) connects workers. SQLite with WAL mode persists data. Each control loop gets dedicated PID and I/O worker threads.

**Tech Stack:** Python 3.13+, uv, pyzmq, msgpack, aiosqlite, pydantic, pydantic-settings, structlog, pytest, pytest-asyncio, ruff, mypy

**Reference docs:**
- Architecture spec: `docs/superpowers/specs/2026-04-02-smart-pid-architecture-design.md`
- PID block spec: `docs/bloco_pid.md`
- Original spec: `docs/smartPID.md`

---

## File Map

```
src/smart_pid/
├── __init__.py                         # Package version
├── main.py                             # Bootstrap and lifecycle
├── config.py                           # Settings via pydantic-settings
├── exceptions.py                       # Typed exception hierarchy
├── domain/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py                 # Re-exports
│   │   ├── controller.py              # Controller, PIDParams, ScaleConfig, enums
│   │   └── telemetry.py               # TelemetryFrame, ControlAction
│   ├── events.py                       # Frozen domain events
│   ├── ports/
│   │   ├── __init__.py
│   │   ├── inbound.py                 # TelemetrySource protocol
│   │   └── outbound.py                # ControllerRepository, HistorianWriter, ControlWriter
│   └── services/
│       ├── __init__.py
│       ├── pid_engine.py              # PID velocity form equation
│       └── pid_mode_manager.py        # Mode state machine
├── application/
│   ├── __init__.py
│   ├── event_bus.py                   # ZeroMQ XPUB/XSUB wrapper
│   └── workers/
│       ├── __init__.py
│       ├── pid_worker.py              # High-priority PID loop thread
│       └── db_worker.py               # Batch insert thread
└── adapters/
    ├── __init__.py
    └── outbound/
        ├── __init__.py
        ├── sqlite_repo.py             # ControllerRepository implementation
        └── historian.py               # HistorianWriter implementation

tests/
├── conftest.py                        # Shared fixtures
├── unit/
│   ├── test_pid_engine.py
│   └── test_pid_mode_manager.py
└── integration/
    ├── test_event_bus.py
    └── test_sqlite_repo.py
```

---

## Task 1: Project Scaffold and Tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/smart_pid/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "smart-pid"
version = "0.1.0"
description = "Smart PID Edge Optimizer - Industrial PID loop optimization with AI"
requires-python = ">=3.13"
dependencies = [
    "pyzmq>=26.0",
    "msgpack>=1.0",
    "aiosqlite>=0.20",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "structlog>=24.0",
    "numpy>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.14",
    "mypy>=1.10",
    "ruff>=0.4",
    "coverage>=7.5",
]

[project.scripts]
smart-pid = "smart_pid.main:main"

[tool.hatch.build.targets.wheel]
packages = ["src/smart_pid"]

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "TCH"]

[tool.ruff.lint.isort]
known-first-party = ["smart_pid"]

[tool.mypy]
strict = true
python_version = "3.13"
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create .env.example**

```bash
SPID_LOG_LEVEL=INFO
SPID_OPCUA_ENDPOINT=opc.tcp://localhost:4840
SPID_THEME=dark
SPID_SIMULATOR_ENABLED=false
SPID_SIMULATOR_PORT=4841
```

- [ ] **Step 3: Create package __init__.py**

```python
# src/smart_pid/__init__.py
"""Smart PID Edge Optimizer."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Create all __init__.py files for subpackages**

Create empty `__init__.py` in each directory:
- `src/smart_pid/domain/__init__.py`
- `src/smart_pid/domain/models/__init__.py`
- `src/smart_pid/domain/ports/__init__.py`
- `src/smart_pid/domain/services/__init__.py`
- `src/smart_pid/application/__init__.py`
- `src/smart_pid/application/workers/__init__.py`
- `src/smart_pid/adapters/__init__.py`
- `src/smart_pid/adapters/outbound/__init__.py`
- `tests/__init__.py` (empty)
- `tests/unit/__init__.py` (empty)
- `tests/integration/__init__.py` (empty)

- [ ] **Step 5: Create tests/conftest.py**

```python
# tests/conftest.py
"""Shared test fixtures for Smart PID."""
from __future__ import annotations

import pytest


@pytest.fixture
def sample_pid_params() -> dict:
    """Standard PID parameters for testing."""
    return {
        "gain": 1.5,
        "reset": 10.0,
        "rate": 2.0,
        "alpha": 0.125,
        "deadband": 0.0,
    }
```

- [ ] **Step 6: Initialize uv and install dependencies**

Run:
```bash
uv sync --dev
```
Expected: Virtual environment created, all dependencies installed.

- [ ] **Step 7: Verify tooling works**

Run:
```bash
uv run pytest --version && uv run ruff --version && uv run mypy --version
```
Expected: All three print version numbers without errors.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .env.example src/ tests/ uv.lock
git commit -m "chore: scaffold project with uv, pyproject.toml, and package structure"
```

---

## Task 2: Configuration and Exceptions

**Files:**
- Create: `src/smart_pid/config.py`
- Create: `src/smart_pid/exceptions.py`

- [ ] **Step 1: Create config.py**

```python
# src/smart_pid/config.py
"""Application settings via pydantic-settings."""
from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SPID_",
    )

    # Application
    app_name: str = "Smart PID Edge Optimizer"
    app_version: str = "0.1.0"
    log_level: LogLevel = LogLevel.INFO

    # OPC-UA
    opcua_endpoint: str = "opc.tcp://localhost:4840"
    opcua_timeout_ms: int = 5000
    opcua_reconnect_interval_s: float = 5.0

    # Database
    db_retention_process_days: int = 7
    db_retention_alarm_days: int = 30
    db_flush_interval_s: float = 5.0
    db_batch_size: int = 500

    # Simulator
    simulator_port: int = 4841
    simulator_enabled: bool = False

    # UI
    theme: str = "dark"
    chart_fps: int = 30
    chart_max_points: int = 50000

    # Paths
    last_project_path: Path | None = None


settings = Settings()
```

- [ ] **Step 2: Create exceptions.py**

```python
# src/smart_pid/exceptions.py
"""Typed exception hierarchy for Smart PID."""
from __future__ import annotations


class SmartPIDError(Exception):
    """Base error for entire application."""


class DomainError(SmartPIDError):
    """Errors from domain logic."""


class PIDComputationError(DomainError):
    """Error during PID calculation."""


class InvalidModeTransition(DomainError):
    """Invalid PID mode transition requested."""

    def __init__(self, current: str, target: str, reason: str) -> None:
        super().__init__(f"Cannot transition from {current} to {target}: {reason}")
        self.current = current
        self.target = target
        self.reason = reason


class InfrastructureError(SmartPIDError):
    """Errors from adapters/external systems."""


class OPCUAConnectionError(InfrastructureError):
    """Failed to connect to OPC-UA server."""


class DatabaseError(InfrastructureError):
    """Database operation failed."""


class ProjectError(SmartPIDError):
    """Errors related to project lifecycle."""


class ProjectNotFoundError(ProjectError):
    """Project file (.spid) not found."""
```

- [ ] **Step 3: Verify with ruff and mypy**

Run:
```bash
uv run ruff check src/smart_pid/config.py src/smart_pid/exceptions.py && uv run mypy src/smart_pid/config.py src/smart_pid/exceptions.py
```
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add src/smart_pid/config.py src/smart_pid/exceptions.py
git commit -m "feat: add application settings and typed exception hierarchy"
```

---

## Task 3: Domain Models — Enums and ScaleConfig

**Files:**
- Create: `src/smart_pid/domain/models/controller.py`
- Create: `src/smart_pid/domain/models/telemetry.py`
- Create: `src/smart_pid/domain/models/__init__.py` (update with re-exports)

- [ ] **Step 1: Create controller.py with enums and data models**

```python
# src/smart_pid/domain/models/controller.py
"""Controller configuration and PID parameter models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ExecutionMode(str, Enum):
    SUPERVISORY = "SUPERVISORY"
    DDC = "DDC"


class PIDStructure(str, Enum):
    ISA = "ISA"
    PARALLEL = "PARALLEL"
    SERIES = "SERIES"


class IntegralType(str, Enum):
    GAIN_KI = "GAIN_KI"
    TIME_TI = "TIME_TI"


class PIDMode(str, Enum):
    OOS = "OOS"           # Out of Service
    IMAN = "IMAN"         # Initializing Manual
    LO = "LO"             # Local Override
    MAN = "MAN"           # Manual
    AUTO = "AUTO"         # Automatic
    CAS = "CAS"           # Cascade
    RCAS = "RCAS"         # Remote Cascade
    ROUT = "ROUT"         # Remote Output


class AIEngine(str, Enum):
    NONE = "NONE"
    FUZZY = "FUZZY"
    RL = "RL"


class ControlObjective(str, Enum):
    SP_TRACKING = "SP_TRACKING"
    DISTURBANCE_REJECTION = "DISTURBANCE_REJECTION"
    SURGE_LEVEL = "SURGE_LEVEL"


class ProcessSpeed(str, Enum):
    SLOW = "SLOW"
    MEDIUM = "MEDIUM"
    FAST = "FAST"


class ConnectionState(str, Enum):
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"
    RECONNECTING = "RECONNECTING"


class SignalStatus(str, Enum):
    GOOD = "GOOD"
    BAD = "BAD"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class ScaleConfig:
    """Engineering unit scale definition."""

    eu_min: float
    eu_max: float
    unit: str = ""

    @property
    def span(self) -> float:
        return self.eu_max - self.eu_min


@dataclass
class PIDParams:
    """PID tuning parameters."""

    gain: float = 1.0             # Kp (proportional gain)
    reset: float = 10.0           # Ti (integral time, seconds/repeat)
    rate: float = 0.0             # Td (derivative time, seconds)
    alpha: float = 0.125          # Derivative filter factor (Rate/8)
    deadband: float = 0.0         # Integral deadband (engineering units)


@dataclass
class AIConfig:
    """AI optimization configuration."""

    engine: AIEngine = AIEngine.NONE
    objective: ControlObjective = ControlObjective.DISTURBANCE_REJECTION
    process_speed: ProcessSpeed = ProcessSpeed.MEDIUM
    dead_time_l: float = 1.0      # Estimated dead time (seconds)
    limit_min: float = 0.1        # Ki/Ti minimum clamp
    limit_max: float = 100.0      # Ki/Ti maximum clamp


@dataclass
class TagBindings:
    """OPC-UA NodeID mappings for a controller."""

    node_id_pv: str = ""
    node_id_sp: str = ""
    node_id_co: str = ""
    node_id_integral: str = ""


@dataclass
class ControlOpts:
    """Control strategy options (CONTROL_OPTS from bloco_pid.md)."""

    no_out_limits_in_manual: bool = False
    obey_sp_limits_if_cas: bool = False
    track_in_manual: bool = False
    track_enable: bool = False
    direct_acting: bool = False
    sp_track_retained_target: bool = False
    sp_pv_track_in_lo_or_iman: bool = False
    sp_pv_track_in_rout: bool = False
    sp_pv_track_in_man: bool = False


@dataclass
class IOOpts:
    """I/O processing options (IO_OPTS from bloco_pid.md)."""

    low_cutoff: bool = False
    target_to_man_if_fault: bool = False
    fault_state_to_value: bool = False  # False=freeze, True=go to value
    increase_to_close: bool = False
    sp_pv_track_in_lo_or_iman: bool = False
    sp_pv_track_in_man: bool = False


@dataclass
class Controller:
    """Complete configuration for a single PID control loop."""

    id: int = 0
    name: str = ""
    description: str = ""
    mode_execution: ExecutionMode = ExecutionMode.DDC
    scan_rate_ms: int = 1000
    pid_params: PIDParams = field(default_factory=PIDParams)
    pid_structure: PIDStructure = PIDStructure.ISA
    integral_type: IntegralType = IntegralType.TIME_TI
    pv_scale: ScaleConfig = field(default_factory=lambda: ScaleConfig(0.0, 100.0))
    out_scale: ScaleConfig = field(default_factory=lambda: ScaleConfig(0.0, 100.0))
    tag_bindings: TagBindings = field(default_factory=TagBindings)
    control_opts: ControlOpts = field(default_factory=ControlOpts)
    io_opts: IOOpts = field(default_factory=IOOpts)
    ai_config: AIConfig = field(default_factory=AIConfig)
    permitted_modes: set[PIDMode] = field(
        default_factory=lambda: {PIDMode.MAN, PIDMode.AUTO}
    )
    mode_normal: PIDMode = PIDMode.AUTO

    # SP limits
    sp_hi_lim: float = 100.0
    sp_lo_lim: float = 0.0
    sp_rate_up: float = 0.0       # 0 = immediate
    sp_rate_dn: float = 0.0       # 0 = immediate

    # Output limits
    out_hi_lim: float = 100.0
    out_lo_lim: float = 0.0

    # Anti-reset windup limits
    arw_hi_lim: float = 100.0
    arw_lo_lim: float = 0.0

    # Filter time constants
    pv_ftime: float = 0.0         # PV filter (seconds)
    sp_ftime: float = 0.0         # SP filter (seconds)

    # Low cutoff
    low_cut: float = 0.0

    # Shed (connection loss)
    shed_opt: PIDMode = PIDMode.MAN
    shed_time_s: float = 10.0
```

- [ ] **Step 2: Create telemetry.py**

```python
# src/smart_pid/domain/models/telemetry.py
"""Telemetry and control action models."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from smart_pid.domain.models.controller import SignalStatus


@dataclass(frozen=True)
class TelemetryFrame:
    """Immutable snapshot of a controller's process values."""

    controller_id: int
    pv: float
    sp: float
    co: float
    integral_val: float
    timestamp: datetime
    status: SignalStatus = SignalStatus.GOOD


@dataclass(frozen=True)
class ControlAction:
    """Output from PID computation to be written to the process."""

    controller_id: int
    co: float
    integral_val: float
    timestamp: datetime
```

- [ ] **Step 3: Update domain/models/__init__.py with re-exports**

```python
# src/smart_pid/domain/models/__init__.py
"""Domain models re-exports."""
from smart_pid.domain.models.controller import (
    AIConfig,
    AIEngine,
    ConnectionState,
    ControlObjective,
    ControlOpts,
    Controller,
    ExecutionMode,
    IntegralType,
    IOOpts,
    PIDMode,
    PIDParams,
    PIDStructure,
    ProcessSpeed,
    ScaleConfig,
    SignalStatus,
    TagBindings,
)
from smart_pid.domain.models.telemetry import ControlAction, TelemetryFrame

__all__ = [
    "AIConfig",
    "AIEngine",
    "ConnectionState",
    "ControlAction",
    "ControlObjective",
    "ControlOpts",
    "Controller",
    "ExecutionMode",
    "IntegralType",
    "IOOpts",
    "PIDMode",
    "PIDParams",
    "PIDStructure",
    "ProcessSpeed",
    "ScaleConfig",
    "SignalStatus",
    "TagBindings",
    "TelemetryFrame",
]
```

- [ ] **Step 4: Verify with ruff and mypy**

Run:
```bash
uv run ruff check src/smart_pid/domain/ && uv run mypy src/smart_pid/domain/
```
Expected: No errors.

- [ ] **Step 5: Commit**

```bash
git add src/smart_pid/domain/
git commit -m "feat: add domain models — Controller, PIDParams, TelemetryFrame, enums"
```

---

## Task 4: Domain Events

**Files:**
- Create: `src/smart_pid/domain/events.py`

- [ ] **Step 1: Create events.py**

```python
# src/smart_pid/domain/events.py
"""Frozen domain events for the ZeroMQ event bus."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from smart_pid.domain.models.controller import ConnectionState
from smart_pid.domain.models.telemetry import TelemetryFrame


@dataclass(frozen=True)
class TelemetryReceived:
    """Published by I/O Worker when new telemetry is read."""

    controller_id: int
    frame: TelemetryFrame
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ControlActionComputed:
    """Published by PID Worker after computing new output."""

    controller_id: int
    co: float
    integral_val: float
    delta_cv: float
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class SystemStateChanged:
    """Published by Loop Manager on connection state changes."""

    new_state: ConnectionState
    reason: str
    event_id: UUID = field(default_factory=uuid4)
```

- [ ] **Step 2: Verify**

Run:
```bash
uv run mypy src/smart_pid/domain/events.py
```
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add src/smart_pid/domain/events.py
git commit -m "feat: add frozen domain events for ZeroMQ bus"
```

---

## Task 5: Domain Ports (Protocol interfaces)

**Files:**
- Create: `src/smart_pid/domain/ports/inbound.py`
- Create: `src/smart_pid/domain/ports/outbound.py`

- [ ] **Step 1: Create inbound.py**

```python
# src/smart_pid/domain/ports/inbound.py
"""Inbound port interfaces (external world -> domain)."""
from __future__ import annotations

from typing import Protocol

from smart_pid.domain.models.telemetry import TelemetryFrame


class TelemetrySource(Protocol):
    """Reads process values from an external source (OPC-UA or Simulator)."""

    async def read_telemetry(self, controller_id: int) -> TelemetryFrame: ...

    async def connect(self, endpoint: str) -> None: ...

    async def disconnect(self) -> None: ...
```

- [ ] **Step 2: Create outbound.py**

```python
# src/smart_pid/domain/ports/outbound.py
"""Outbound port interfaces (domain -> external world)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from smart_pid.domain.models.controller import Controller
from smart_pid.domain.models.telemetry import TelemetryFrame


class ControlWriter(Protocol):
    """Writes control actions to the process (OPC-UA or Simulator)."""

    async def write_output(self, controller_id: int, co: float) -> None: ...

    async def write_parameter(
        self, controller_id: int, param: str, value: float
    ) -> None: ...


class ControllerRepository(Protocol):
    """Persistence for controller configurations."""

    async def get(self, controller_id: int) -> Controller: ...

    async def list_all(self) -> list[Controller]: ...

    async def save(self, controller: Controller) -> None: ...

    async def delete(self, controller_id: int) -> None: ...


class HistorianWriter(Protocol):
    """Batch write process data to historian storage."""

    async def write_batch(self, frames: list[TelemetryFrame]) -> None: ...

    async def query(
        self,
        controller_id: int,
        start: datetime,
        end: datetime,
    ) -> list[TelemetryFrame]: ...

    async def cleanup_older_than(self, days: int) -> int: ...


class ProjectStore(Protocol):
    """Manages .spid project files."""

    async def create(self, path: Path) -> None: ...

    async def open(self, path: Path) -> None: ...

    async def close(self) -> None: ...
```

- [ ] **Step 3: Verify**

Run:
```bash
uv run mypy src/smart_pid/domain/ports/
```
Expected: No errors.

- [ ] **Step 4: Commit**

```bash
git add src/smart_pid/domain/ports/
git commit -m "feat: add domain port interfaces (TelemetrySource, ControllerRepository, etc.)"
```

---

## Task 6: PID Engine — Tests First

**Files:**
- Create: `tests/unit/test_pid_engine.py`
- Create: `src/smart_pid/domain/services/pid_engine.py`

- [ ] **Step 1: Write failing tests for PID engine**

```python
# tests/unit/test_pid_engine.py
"""Unit tests for PID engine velocity form equation."""
from __future__ import annotations

import math

import pytest

from smart_pid.domain.models.controller import PIDParams
from smart_pid.domain.services.pid_engine import PIDEngine, PIDResult, PIDState


class TestPIDCompute:
    """Test PID velocity form: delta_cv = G*[(e-e_prev) + dt/Ti*e - Td*(pv-2*pv_prev+pv_prev2)/dt]"""

    def setup_method(self) -> None:
        self.engine = PIDEngine()
        self.params = PIDParams(gain=1.0, reset=10.0, rate=0.0)

    def test_zero_error_produces_zero_delta(self) -> None:
        """With PV == SP and no history, delta_cv should be zero."""
        state = PIDState(cv=50.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=self.params,
            state=state,
            pv=50.0,
            sp=50.0,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        assert result.delta_cv == pytest.approx(0.0, abs=1e-10)
        assert result.cv == pytest.approx(50.0, abs=1e-10)

    def test_proportional_action_on_error_step(self) -> None:
        """Step change in SP should produce proportional kick (error term)."""
        state = PIDState(cv=50.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=PIDParams(gain=2.0, reset=1e9, rate=0.0),  # P-only (huge Ti)
            state=state,
            pv=50.0,
            sp=60.0,  # Step change: error = 10
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # delta_cv = G * (e - e_prev) = 2.0 * (10 - 0) = 20.0
        assert result.delta_cv == pytest.approx(20.0, abs=1e-6)
        assert result.cv == pytest.approx(70.0, abs=1e-6)

    def test_integral_action_accumulates(self) -> None:
        """Constant error should produce steady integral accumulation."""
        state = PIDState(cv=50.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=40.0,
            sp=50.0,  # error = 10
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # error unchanged: proportional delta = 0
        # integral delta = G * dt/Ti * e = 1.0 * 1.0/10.0 * 10 = 1.0
        assert result.delta_cv == pytest.approx(1.0, abs=1e-6)

    def test_derivative_action_on_pv_change(self) -> None:
        """Derivative acts on PV change, not error change (derivative on PV)."""
        state = PIDState(cv=50.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=1e9, rate=5.0),  # D-only (huge Ti)
            state=state,
            pv=42.0,  # PV changed by 2
            sp=50.0,  # error = 8
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # proportional delta = G * (8 - 10) = -2.0
        # derivative = -G * Td * (pv - 2*pv_prev + pv_prev2) / dt
        #            = -1.0 * 5.0 * (42 - 80 + 40) / 1.0 = -1.0 * 5.0 * 2.0 = -10.0
        # total delta = -2.0 + 0.0 (no integral) + (-10.0) = -12.0
        assert result.delta_cv == pytest.approx(-12.0, abs=1e-6)

    def test_output_clamped_to_limits(self) -> None:
        """CV must be clamped within out_limits."""
        state = PIDState(cv=98.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=PIDParams(gain=2.0, reset=1e9, rate=0.0),
            state=state,
            pv=50.0,
            sp=60.0,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # delta_cv = 20, but 98 + 20 = 118 -> clamped to 100
        assert result.cv == pytest.approx(100.0, abs=1e-6)
        assert result.new_state.is_saturated is True

    def test_direct_acting_reverses_error(self) -> None:
        """Direct acting: increasing PV should increase output."""
        state = PIDState(cv=50.0, error_prev=0.0, pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=1e9, rate=0.0),
            state=state,
            pv=50.0,
            sp=40.0,  # error = -10 (reverse acting) or +10 (direct acting)
            dt=1.0,
            out_limits=(0.0, 100.0),
            direct_acting=True,
        )
        # Direct acting: error = PV - SP = 10
        assert result.delta_cv == pytest.approx(10.0, abs=1e-6)


class TestAntiWindup:
    """Anti-reset windup: pause integral when output is saturated."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_integral_paused_when_saturated_high(self) -> None:
        """When CV hits upper limit, integral should not accumulate further up."""
        state = PIDState(cv=100.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0, is_saturated=True)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=40.0,
            sp=50.0,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Proportional delta = 0 (error unchanged)
        # Integral should be suppressed because output is saturated high and error is positive
        assert result.cv == pytest.approx(100.0, abs=1e-6)

    def test_integral_resumes_when_error_reverses(self) -> None:
        """When error direction reverses, integral should resume to bring output back."""
        state = PIDState(cv=100.0, error_prev=-5.0, pv_prev=55.0, pv_prev2=55.0, is_saturated=True)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=55.0,
            sp=50.0,  # error = -5
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Error is negative while saturated high -> integral should act to reduce output
        # integral delta = 1.0 * 1.0/10.0 * (-5) = -0.5
        assert result.cv < 100.0


class TestBumplessTransfer:
    """Bumpless transfer recalculates integral on mode change."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_bumpless_sets_cv_to_current_co(self) -> None:
        """After bumpless transfer, the PID output should match the current CO."""
        state = PIDState(cv=30.0)
        new_state = self.engine.bumpless_transfer(
            state=state,
            current_pv=45.0,
            current_co=65.0,
            params=PIDParams(gain=1.5, reset=10.0, rate=0.0),
        )
        assert new_state.cv == pytest.approx(65.0, abs=1e-6)
        assert new_state.pv_prev == pytest.approx(45.0, abs=1e-6)
        assert new_state.pv_prev2 == pytest.approx(45.0, abs=1e-6)


class TestSPRamp:
    """SP rate limiting (SP_RATE_UP / SP_RATE_DN)."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_ramp_up_limits_sp_increase(self) -> None:
        """SP should increase at most rate_up * dt per scan."""
        result = self.engine.apply_sp_ramp(
            sp_target=100.0,
            sp_current=50.0,
            rate_up=10.0,  # 10 units/second
            rate_dn=10.0,
            dt=1.0,
        )
        assert result == pytest.approx(60.0, abs=1e-6)  # 50 + 10*1

    def test_ramp_down_limits_sp_decrease(self) -> None:
        result = self.engine.apply_sp_ramp(
            sp_target=0.0,
            sp_current=50.0,
            rate_up=10.0,
            rate_dn=5.0,  # 5 units/second
            dt=1.0,
        )
        assert result == pytest.approx(45.0, abs=1e-6)  # 50 - 5*1

    def test_zero_rate_means_immediate(self) -> None:
        """Rate of 0 means no limiting — SP jumps immediately."""
        result = self.engine.apply_sp_ramp(
            sp_target=100.0,
            sp_current=50.0,
            rate_up=0.0,
            rate_dn=0.0,
            dt=1.0,
        )
        assert result == pytest.approx(100.0, abs=1e-6)


class TestDeadband:
    """Integral deadband: stops integral when error is within deadband."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_integral_stops_within_deadband(self) -> None:
        """When |error| < deadband, integral term should not accumulate."""
        state = PIDState(cv=50.0, error_prev=0.5, pv_prev=49.5, pv_prev2=49.5)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0, deadband=2.0),
            state=state,
            pv=49.5,
            sp=50.0,  # error = 0.5, within deadband of 2.0
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Proportional delta = 0 (error unchanged)
        # Integral should be zero because |error| < deadband
        assert result.delta_cv == pytest.approx(0.0, abs=1e-6)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest tests/unit/test_pid_engine.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid.domain.services.pid_engine'`

- [ ] **Step 3: Implement PID engine**

```python
# src/smart_pid/domain/services/pid_engine.py
"""PID controller engine using velocity (incremental) form.

Equation (derivative on PV):
    delta_cv = Gain * [(e_n - e_n-1) + (dt/Reset)*e_n - Rate*(PV_n - 2*PV_n-1 + PV_n-2)/dt]
    cv_new = cv_current + delta_cv

Derivative filter: alpha (default Rate/8).
Anti-windup: suppresses integral when output is saturated and error pushes further.
Bumpless transfer: reinitializes state to match current output on mode change.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from smart_pid.domain.models.controller import PIDParams


@dataclass
class PIDState:
    """Mutable state carried between PID scans."""

    cv: float = 0.0
    error_prev: float = 0.0
    pv_prev: float = 0.0
    pv_prev2: float = 0.0
    sp_working: float = 0.0
    derivative_filtered: float = 0.0
    is_saturated: bool = False


@dataclass(frozen=True)
class PIDResult:
    """Output of a single PID computation."""

    cv: float
    delta_cv: float
    error: float
    new_state: PIDState


class PIDEngine:
    """Stateless PID engine. All state is passed in and returned explicitly."""

    def compute(
        self,
        params: PIDParams,
        state: PIDState,
        pv: float,
        sp: float,
        dt: float,
        out_limits: tuple[float, float],
        direct_acting: bool = False,
    ) -> PIDResult:
        """Execute one PID scan. Returns new CV and updated state."""
        lo, hi = out_limits

        # Error calculation
        if direct_acting:
            error = pv - sp
        else:
            error = sp - pv

        # --- Proportional term (acts on error change) ---
        p_term = params.gain * (error - state.error_prev)

        # --- Integral term ---
        i_term = 0.0
        if params.reset > 0 and dt > 0:
            # Check deadband
            in_deadband = abs(error) < params.deadband if params.deadband > 0 else False
            # Anti-windup: suppress integral if saturated AND error drives further
            windup_block = (
                state.is_saturated
                and (
                    (state.cv >= hi and error > 0)
                    or (state.cv <= lo and error < 0)
                )
            )
            if not in_deadband and not windup_block:
                i_term = params.gain * (dt / params.reset) * error

        # --- Derivative term (acts on PV, not error) ---
        d_term = 0.0
        if params.rate > 0 and dt > 0:
            d2_pv = pv - 2.0 * state.pv_prev + state.pv_prev2
            d_raw = -params.gain * params.rate * (d2_pv / dt)
            # Apply derivative filter (exponential smoothing)
            alpha = min(max(params.alpha, 0.05), 1.0)
            d_term = alpha * d_raw + (1.0 - alpha) * state.derivative_filtered

        # --- Total increment ---
        delta_cv = p_term + i_term + d_term

        # --- Apply to output ---
        cv_new = state.cv + delta_cv

        # --- Clamp output ---
        is_saturated = False
        if cv_new > hi:
            cv_new = hi
            is_saturated = True
        elif cv_new < lo:
            cv_new = lo
            is_saturated = True

        new_state = PIDState(
            cv=cv_new,
            error_prev=error,
            pv_prev=pv,
            pv_prev2=state.pv_prev,
            sp_working=sp,
            derivative_filtered=d_term,
            is_saturated=is_saturated,
        )

        return PIDResult(
            cv=cv_new,
            delta_cv=delta_cv,
            error=error,
            new_state=new_state,
        )

    def bumpless_transfer(
        self,
        state: PIDState,
        current_pv: float,
        current_co: float,
        params: PIDParams,
    ) -> PIDState:
        """Reinitialize PID state for seamless mode transition.

        Sets CV to match current CO so there's no output bump.
        Resets PV history to current PV to avoid derivative spike.
        """
        return PIDState(
            cv=current_co,
            error_prev=0.0,
            pv_prev=current_pv,
            pv_prev2=current_pv,
            sp_working=state.sp_working,
            derivative_filtered=0.0,
            is_saturated=False,
        )

    def apply_sp_ramp(
        self,
        sp_target: float,
        sp_current: float,
        rate_up: float,
        rate_dn: float,
        dt: float,
    ) -> float:
        """Apply SP rate limiting. Returns working SP for this scan.

        rate_up/rate_dn in engineering units per second. 0 = no limiting.
        """
        diff = sp_target - sp_current
        if diff > 0:
            if rate_up <= 0:
                return sp_target
            max_change = rate_up * dt
            return sp_current + min(diff, max_change)
        elif diff < 0:
            if rate_dn <= 0:
                return sp_target
            max_change = rate_dn * dt
            return sp_current - min(abs(diff), max_change)
        return sp_target
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/unit/test_pid_engine.py -v
```
Expected: All tests PASS.

- [ ] **Step 5: Run ruff and mypy**

Run:
```bash
uv run ruff check src/smart_pid/domain/services/pid_engine.py tests/unit/test_pid_engine.py && uv run mypy src/smart_pid/domain/services/pid_engine.py
```
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add src/smart_pid/domain/services/pid_engine.py tests/unit/test_pid_engine.py
git commit -m "feat: implement PID engine with velocity form, anti-windup, bumpless transfer"
```

---

## Task 7: PID Mode Manager — Tests First

**Files:**
- Create: `tests/unit/test_pid_mode_manager.py`
- Create: `src/smart_pid/domain/services/pid_mode_manager.py`

- [ ] **Step 1: Write failing tests for mode manager**

```python
# tests/unit/test_pid_mode_manager.py
"""Unit tests for PID mode state machine."""
from __future__ import annotations

import pytest

from smart_pid.domain.models.controller import PIDMode, SignalStatus
from smart_pid.domain.services.pid_mode_manager import (
    BlockStatus,
    ModeManager,
    ModeTransition,
)
from smart_pid.exceptions import InvalidModeTransition


class TestModeTransitions:
    """Test valid and invalid mode transitions."""

    def setup_method(self) -> None:
        self.mgr = ModeManager()
        self.permitted = {PIDMode.OOS, PIDMode.MAN, PIDMode.AUTO, PIDMode.CAS}

    def test_man_to_auto_allowed(self) -> None:
        result = self.mgr.request_mode(
            current=PIDMode.MAN,
            target=PIDMode.AUTO,
            permitted=self.permitted,
            block_status=BlockStatus(),
        )
        assert result.accepted is True
        assert result.new_mode == PIDMode.AUTO
        assert result.requires_bumpless is True

    def test_auto_to_man_allowed(self) -> None:
        result = self.mgr.request_mode(
            current=PIDMode.AUTO,
            target=PIDMode.MAN,
            permitted=self.permitted,
            block_status=BlockStatus(),
        )
        assert result.accepted is True
        assert result.new_mode == PIDMode.MAN

    def test_transition_to_unpermitted_mode_rejected(self) -> None:
        permitted = {PIDMode.MAN, PIDMode.AUTO}
        result = self.mgr.request_mode(
            current=PIDMode.MAN,
            target=PIDMode.CAS,
            permitted=permitted,
            block_status=BlockStatus(),
        )
        assert result.accepted is False
        assert result.rejection_reason == "CAS not in permitted modes"

    def test_auto_to_cas_allowed(self) -> None:
        result = self.mgr.request_mode(
            current=PIDMode.AUTO,
            target=PIDMode.CAS,
            permitted=self.permitted,
            block_status=BlockStatus(),
        )
        assert result.accepted is True
        assert result.new_mode == PIDMode.CAS

    def test_oos_to_man_allowed(self) -> None:
        result = self.mgr.request_mode(
            current=PIDMode.OOS,
            target=PIDMode.MAN,
            permitted=self.permitted,
            block_status=BlockStatus(),
        )
        assert result.accepted is True


class TestForcedTransitions:
    """Test automatic mode changes from system conditions."""

    def setup_method(self) -> None:
        self.mgr = ModeManager()

    def test_bad_pv_forces_manual(self) -> None:
        """Bad PV status forces transition to MAN."""
        status = BlockStatus(pv_status=SignalStatus.BAD)
        forced = self.mgr.evaluate_forced_transitions(
            current=PIDMode.AUTO,
            block_status=status,
        )
        assert forced == PIDMode.MAN

    def test_tracking_active_forces_lo(self) -> None:
        """Active tracking input forces Local Override mode."""
        status = BlockStatus(tracking_active=True)
        forced = self.mgr.evaluate_forced_transitions(
            current=PIDMode.AUTO,
            block_status=status,
        )
        assert forced == PIDMode.LO

    def test_good_pv_no_force(self) -> None:
        """Good PV and no tracking — no forced transition."""
        status = BlockStatus(pv_status=SignalStatus.GOOD)
        forced = self.mgr.evaluate_forced_transitions(
            current=PIDMode.AUTO,
            block_status=status,
        )
        assert forced is None

    def test_shed_timeout_forces_configured_mode(self) -> None:
        """Connection loss timeout forces SHED_OPT mode."""
        status = BlockStatus(shed_timeout_expired=True)
        forced = self.mgr.evaluate_forced_transitions(
            current=PIDMode.AUTO,
            block_status=status,
            shed_mode=PIDMode.MAN,
        )
        assert forced == PIDMode.MAN
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest tests/unit/test_pid_mode_manager.py -v
```
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implement mode manager**

```python
# src/smart_pid/domain/services/pid_mode_manager.py
"""PID mode state machine.

Manages transitions between 8 operating modes:
OOS, IMan, LO, Man, Auto, Cas, RCas, ROut.

Rules from bloco_pid.md:
- Bad PV -> forces MAN
- TRK_IN_D active -> forces LO
- SHED timeout -> forces configured shed mode
- Transitions validate against permitted modes
- Man->Auto and Auto->Cas require bumpless transfer
"""
from __future__ import annotations

from dataclasses import dataclass

from smart_pid.domain.models.controller import PIDMode, SignalStatus


# Modes that require bumpless transfer when entering
_BUMPLESS_REQUIRED_TARGETS = {PIDMode.AUTO, PIDMode.CAS, PIDMode.RCAS}


@dataclass
class BlockStatus:
    """Current status conditions that may force mode changes."""

    pv_status: SignalStatus = SignalStatus.GOOD
    tracking_active: bool = False
    shed_timeout_expired: bool = False
    simulate_active: bool = False


@dataclass
class ModeTransition:
    """Result of a mode transition request."""

    accepted: bool
    new_mode: PIDMode
    requires_bumpless: bool = False
    rejection_reason: str = ""


class ModeManager:
    """Stateless mode transition evaluator."""

    def request_mode(
        self,
        current: PIDMode,
        target: PIDMode,
        permitted: set[PIDMode],
        block_status: BlockStatus,
    ) -> ModeTransition:
        """Evaluate a requested mode transition.

        Returns ModeTransition with accepted=True if valid,
        or accepted=False with reason if rejected.
        """
        # Check if target is in permitted modes
        if target not in permitted:
            return ModeTransition(
                accepted=False,
                new_mode=current,
                rejection_reason=f"{target.value} not in permitted modes",
            )

        # Check for forced conditions that override the request
        forced = self.evaluate_forced_transitions(current, block_status)
        if forced is not None and forced != target:
            return ModeTransition(
                accepted=False,
                new_mode=forced,
                rejection_reason=f"Forced to {forced.value} by system condition",
            )

        # Determine if bumpless transfer is needed
        requires_bumpless = (
            target in _BUMPLESS_REQUIRED_TARGETS and current != target
        )

        return ModeTransition(
            accepted=True,
            new_mode=target,
            requires_bumpless=requires_bumpless,
        )

    def evaluate_forced_transitions(
        self,
        current: PIDMode,
        block_status: BlockStatus,
        shed_mode: PIDMode = PIDMode.MAN,
    ) -> PIDMode | None:
        """Check for conditions that force an automatic mode change.

        Priority order:
        1. Tracking active -> LO
        2. Bad PV -> MAN
        3. Shed timeout -> configured shed mode

        Returns None if no forced transition is needed.
        """
        # Tracking has highest priority
        if block_status.tracking_active:
            return PIDMode.LO

        # Bad PV forces manual
        if block_status.pv_status == SignalStatus.BAD:
            return PIDMode.MAN

        # Shed timeout
        if block_status.shed_timeout_expired:
            return shed_mode

        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/unit/test_pid_mode_manager.py -v
```
Expected: All tests PASS.

- [ ] **Step 5: Run ruff and mypy**

Run:
```bash
uv run ruff check src/smart_pid/domain/services/pid_mode_manager.py && uv run mypy src/smart_pid/domain/services/pid_mode_manager.py
```
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add src/smart_pid/domain/services/pid_mode_manager.py tests/unit/test_pid_mode_manager.py
git commit -m "feat: implement PID mode manager with 8-mode state machine"
```

---

## Task 8: Event Bus (ZeroMQ XPUB/XSUB)

**Files:**
- Create: `tests/integration/test_event_bus.py`
- Create: `src/smart_pid/application/event_bus.py`

- [ ] **Step 1: Write failing tests for event bus**

```python
# tests/integration/test_event_bus.py
"""Integration tests for ZeroMQ event bus."""
from __future__ import annotations

import threading
import time

import pytest

from smart_pid.application.event_bus import EventBus


class TestEventBus:
    """Test ZeroMQ PUB/SUB message routing."""

    def test_publish_and_receive_single_message(self) -> None:
        """Publisher sends, subscriber receives on matching topic."""
        bus = EventBus()
        bus.start_proxy()

        sub = bus.subscriber(["TEST."])
        pub = bus.publisher()

        # Give sockets time to connect to proxy
        time.sleep(0.1)

        pub.publish("TEST.1", {"value": 42})

        result = sub.receive(timeout_ms=2000)
        assert result is not None
        topic, data = result
        assert topic == "TEST.1"
        assert data == {"value": 42}

        bus.shutdown()

    def test_subscriber_filters_by_prefix(self) -> None:
        """Subscriber only receives messages matching subscribed prefix."""
        bus = EventBus()
        bus.start_proxy()

        sub = bus.subscriber(["TELEMETRY."])
        pub = bus.publisher()

        time.sleep(0.1)

        pub.publish("ACTION.1", {"ignored": True})
        pub.publish("TELEMETRY.1", {"pv": 50.0})

        result = sub.receive(timeout_ms=2000)
        assert result is not None
        topic, data = result
        assert topic == "TELEMETRY.1"
        assert data["pv"] == 50.0

        # Should not receive the ACTION message
        result2 = sub.receive(timeout_ms=500)
        assert result2 is None

        bus.shutdown()

    def test_multiple_subscribers_receive_same_message(self) -> None:
        """PUB/SUB fanout: all subscribers get the message."""
        bus = EventBus()
        bus.start_proxy()

        sub1 = bus.subscriber(["DATA."])
        sub2 = bus.subscriber(["DATA."])
        pub = bus.publisher()

        time.sleep(0.1)

        pub.publish("DATA.x", {"val": 99})

        r1 = sub1.receive(timeout_ms=2000)
        r2 = sub2.receive(timeout_ms=2000)

        assert r1 is not None
        assert r2 is not None
        assert r1[1]["val"] == 99
        assert r2[1]["val"] == 99

        bus.shutdown()

    def test_noblock_returns_none_when_empty(self) -> None:
        """Non-blocking receive returns None if no message available."""
        bus = EventBus()
        bus.start_proxy()

        sub = bus.subscriber(["X."])
        time.sleep(0.1)

        result = sub.receive_noblock()
        assert result is None

        bus.shutdown()

    def test_cross_thread_communication(self) -> None:
        """Messages sent from one thread are received in another."""
        bus = EventBus()
        bus.start_proxy()

        received: list[dict] = []

        def consumer() -> None:
            s = bus.subscriber(["CROSS."])
            time.sleep(0.1)
            r = s.receive(timeout_ms=3000)
            if r:
                received.append(r[1])

        t = threading.Thread(target=consumer)
        t.start()

        pub = bus.publisher()
        time.sleep(0.2)  # Wait for subscriber to connect
        pub.publish("CROSS.1", {"thread": "main"})

        t.join(timeout=5.0)
        assert len(received) == 1
        assert received[0]["thread"] == "main"

        bus.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest tests/integration/test_event_bus.py -v
```
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implement event bus**

```python
# src/smart_pid/application/event_bus.py
"""ZeroMQ-based internal event bus using XPUB/XSUB proxy.

Architecture:
    Publishers -> XSUB (frontend) -> proxy -> XPUB (backend) -> Subscribers

All communication via inproc:// (zero-copy, in-process).
Serialization: msgpack for performance.
Thread-safe: each publisher/subscriber creates its own socket.
"""
from __future__ import annotations

import threading
from typing import Any

import msgpack
import zmq


class BusPublisher:
    """Thread-local publisher. Create one per producing thread."""

    def __init__(self, socket: zmq.Socket) -> None:
        self._socket = socket

    def publish(self, topic: str, payload: Any) -> None:
        """Send a message on the given topic.

        Message format: [topic_bytes, msgpack_bytes]
        """
        topic_bytes = topic.encode("utf-8")
        data_bytes = msgpack.packb(payload, use_bin_type=True)
        self._socket.send_multipart([topic_bytes, data_bytes])


class BusSubscriber:
    """Thread-local subscriber. Create one per consuming thread."""

    def __init__(self, socket: zmq.Socket) -> None:
        self._socket = socket

    def subscribe(self, topic_prefix: str) -> None:
        """Subscribe to all topics starting with the given prefix."""
        self._socket.subscribe(topic_prefix.encode("utf-8"))

    def receive(self, timeout_ms: int = -1) -> tuple[str, Any] | None:
        """Blocking receive with optional timeout.

        Returns (topic, payload) or None on timeout.
        timeout_ms=-1 means block forever.
        """
        if timeout_ms >= 0:
            if not self._socket.poll(timeout_ms, zmq.POLLIN):
                return None
        try:
            topic_bytes, data_bytes = self._socket.recv_multipart()
            topic = topic_bytes.decode("utf-8")
            data = msgpack.unpackb(data_bytes, raw=False)
            return topic, data
        except zmq.ZMQError:
            return None

    def receive_noblock(self) -> tuple[str, Any] | None:
        """Non-blocking receive. Returns None immediately if no message."""
        return self.receive(timeout_ms=0)


class EventBus:
    """ZeroMQ XPUB/XSUB event bus for intra-process communication.

    Usage:
        bus = EventBus()
        bus.start_proxy()

        pub = bus.publisher()
        sub = bus.subscriber(["TELEMETRY."])

        pub.publish("TELEMETRY.1", {"pv": 50.0})
        topic, data = sub.receive()

        bus.shutdown()
    """

    def __init__(self) -> None:
        self._ctx = zmq.Context()
        self._xsub_endpoint = "inproc://smartpid_bus_frontend"
        self._xpub_endpoint = "inproc://smartpid_bus_backend"
        self._proxy_thread: threading.Thread | None = None
        self._running = False

        # Bind sockets immediately so publishers/subscribers can connect
        self._frontend = self._ctx.socket(zmq.XSUB)
        self._frontend.bind(self._xsub_endpoint)

        self._backend = self._ctx.socket(zmq.XPUB)
        self._backend.bind(self._xpub_endpoint)

    def start_proxy(self) -> None:
        """Start the XPUB/XSUB proxy in a daemon thread."""
        if self._proxy_thread is not None:
            return

        self._running = True
        self._proxy_thread = threading.Thread(
            target=self._run_proxy,
            daemon=True,
            name="ZMQ-Proxy",
        )
        self._proxy_thread.start()

    def _run_proxy(self) -> None:
        """Run zmq.proxy — blocks until context is terminated."""
        try:
            zmq.proxy(self._frontend, self._backend)
        except zmq.ContextTerminated:
            pass

    def publisher(self) -> BusPublisher:
        """Create a new publisher socket connected to the proxy."""
        socket = self._ctx.socket(zmq.PUB)
        socket.connect(self._xsub_endpoint)
        return BusPublisher(socket)

    def subscriber(self, topics: list[str] | None = None) -> BusSubscriber:
        """Create a new subscriber socket connected to the proxy.

        Args:
            topics: List of topic prefixes to subscribe to.
                    If None, subscribes to nothing (call .subscribe() later).
        """
        socket = self._ctx.socket(zmq.SUB)
        socket.connect(self._xpub_endpoint)
        sub = BusSubscriber(socket)
        if topics:
            for t in topics:
                sub.subscribe(t)
        return sub

    def shutdown(self) -> None:
        """Terminate the ZMQ context, unblocking all sockets."""
        self._running = False
        self._ctx.term()
        self._proxy_thread = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/integration/test_event_bus.py -v
```
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/smart_pid/application/event_bus.py tests/integration/test_event_bus.py
git commit -m "feat: implement ZeroMQ XPUB/XSUB event bus with msgpack serialization"
```

---

## Task 9: SQLite Repository and Historian

**Files:**
- Create: `tests/integration/test_sqlite_repo.py`
- Create: `src/smart_pid/adapters/outbound/sqlite_repo.py`
- Create: `src/smart_pid/adapters/outbound/historian.py`

- [ ] **Step 1: Write failing tests for SQLite repo**

```python
# tests/integration/test_sqlite_repo.py
"""Integration tests for SQLite repository and historian."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from smart_pid.adapters.outbound.historian import SQLiteHistorian
from smart_pid.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid.domain.models.controller import (
    Controller,
    ExecutionMode,
    PIDParams,
    ScaleConfig,
)
from smart_pid.domain.models.telemetry import TelemetryFrame


@pytest.fixture
async def repo(tmp_path: Path) -> SQLiteRepository:
    db_path = tmp_path / "test.spid"
    r = SQLiteRepository(db_path)
    await r.initialize()
    return r


@pytest.fixture
async def historian(repo: SQLiteRepository) -> SQLiteHistorian:
    return SQLiteHistorian(repo)


class TestSQLiteRepository:
    async def test_save_and_get_controller(self, repo: SQLiteRepository) -> None:
        ctrl = Controller(
            id=0,  # auto-assigned
            name="TIC-101",
            description="Reactor Temperature",
            mode_execution=ExecutionMode.DDC,
            scan_rate_ms=500,
            pid_params=PIDParams(gain=1.5, reset=10.0, rate=2.0),
            pv_scale=ScaleConfig(0.0, 400.0, "degC"),
            out_scale=ScaleConfig(0.0, 100.0, "%"),
        )
        await repo.save(ctrl)

        retrieved = await repo.list_all()
        assert len(retrieved) == 1
        assert retrieved[0].name == "TIC-101"
        assert retrieved[0].pid_params.gain == 1.5
        assert retrieved[0].pv_scale.eu_max == 400.0
        assert retrieved[0].id > 0

    async def test_get_by_id(self, repo: SQLiteRepository) -> None:
        ctrl = Controller(name="PIC-201", mode_execution=ExecutionMode.SUPERVISORY)
        await repo.save(ctrl)
        all_ctrls = await repo.list_all()
        ctrl_id = all_ctrls[0].id

        retrieved = await repo.get(ctrl_id)
        assert retrieved.name == "PIC-201"

    async def test_delete_controller(self, repo: SQLiteRepository) -> None:
        ctrl = Controller(name="FIC-301")
        await repo.save(ctrl)
        all_ctrls = await repo.list_all()
        await repo.delete(all_ctrls[0].id)

        remaining = await repo.list_all()
        assert len(remaining) == 0

    async def test_create_empty_project(self, tmp_path: Path) -> None:
        db_path = tmp_path / "new_project.spid"
        r = SQLiteRepository(db_path)
        await r.initialize()

        controllers = await r.list_all()
        assert controllers == []


class TestSQLiteHistorian:
    async def test_write_and_query_batch(self, historian: SQLiteHistorian) -> None:
        now = datetime.now()
        frames = [
            TelemetryFrame(
                controller_id=1,
                pv=50.0 + i,
                sp=50.0,
                co=45.0,
                integral_val=1.2,
                timestamp=now + timedelta(seconds=i),
            )
            for i in range(10)
        ]
        await historian.write_batch(frames)

        result = await historian.query(
            controller_id=1,
            start=now - timedelta(seconds=1),
            end=now + timedelta(seconds=20),
        )
        assert len(result) == 10
        assert result[0].pv == pytest.approx(50.0)
        assert result[9].pv == pytest.approx(59.0)

    async def test_cleanup_removes_old_records(self, historian: SQLiteHistorian) -> None:
        old = datetime.now() - timedelta(days=10)
        recent = datetime.now()
        frames = [
            TelemetryFrame(controller_id=1, pv=1.0, sp=1.0, co=1.0, integral_val=0.0, timestamp=old),
            TelemetryFrame(controller_id=1, pv=2.0, sp=2.0, co=2.0, integral_val=0.0, timestamp=recent),
        ]
        await historian.write_batch(frames)

        deleted = await historian.cleanup_older_than(days=7)
        assert deleted == 1

        remaining = await historian.query(
            controller_id=1,
            start=old - timedelta(days=1),
            end=recent + timedelta(days=1),
        )
        assert len(remaining) == 1
        assert remaining[0].pv == pytest.approx(2.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run pytest tests/integration/test_sqlite_repo.py -v
```
Expected: FAIL — ModuleNotFoundError.

- [ ] **Step 3: Implement SQLite repository**

```python
# src/smart_pid/adapters/outbound/sqlite_repo.py
"""SQLite-based controller repository.

Uses aiosqlite for async operations.
Database file uses .spid extension (SQLite in WAL mode).
Schema matches spec Module 6 DDL.
"""
from __future__ import annotations

import json
from pathlib import Path

import aiosqlite

from smart_pid.domain.models.controller import (
    AIConfig,
    AIEngine,
    ControlObjective,
    ControlOpts,
    Controller,
    ExecutionMode,
    IOOpts,
    IntegralType,
    PIDMode,
    PIDParams,
    PIDStructure,
    ProcessSpeed,
    ScaleConfig,
    TagBindings,
)

_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS Usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('ADMIN', 'SUPERVISOR', 'OPERATOR'))
);

CREATE TABLE IF NOT EXISTS Controladores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    descricao TEXT DEFAULT '',
    modo_execucao TEXT CHECK(modo_execucao IN ('SUPERVISORY', 'DDC')) DEFAULT 'DDC',
    scan_rate_ms INTEGER DEFAULT 1000,
    pid_structure TEXT CHECK(pid_structure IN ('ISA', 'PARALLEL', 'SERIES')) DEFAULT 'ISA',
    integral_type TEXT CHECK(integral_type IN ('GAIN_KI', 'TIME_TI')) DEFAULT 'TIME_TI',
    kp REAL DEFAULT 1.0,
    ti REAL DEFAULT 10.0,
    td REAL DEFAULT 0.0,
    alpha REAL DEFAULT 0.125,
    deadband REAL DEFAULT 0.0,
    pv_scale_min REAL DEFAULT 0.0,
    pv_scale_max REAL DEFAULT 100.0,
    pv_scale_unit TEXT DEFAULT '',
    out_scale_min REAL DEFAULT 0.0,
    out_scale_max REAL DEFAULT 100.0,
    out_scale_unit TEXT DEFAULT '%',
    node_id_pv TEXT DEFAULT '',
    node_id_sp TEXT DEFAULT '',
    node_id_co TEXT DEFAULT '',
    node_id_integral TEXT DEFAULT '',
    control_opts_json TEXT DEFAULT '{}',
    io_opts_json TEXT DEFAULT '{}',
    ai_engine TEXT DEFAULT 'NONE',
    ai_objective TEXT DEFAULT 'DISTURBANCE_REJECTION',
    ai_process_speed TEXT DEFAULT 'MEDIUM',
    ai_dead_time_l REAL DEFAULT 1.0,
    ai_limit_min REAL DEFAULT 0.1,
    ai_limit_max REAL DEFAULT 100.0,
    permitted_modes_json TEXT DEFAULT '["MAN", "AUTO"]',
    mode_normal TEXT DEFAULT 'AUTO',
    sp_hi_lim REAL DEFAULT 100.0,
    sp_lo_lim REAL DEFAULT 0.0,
    sp_rate_up REAL DEFAULT 0.0,
    sp_rate_dn REAL DEFAULT 0.0,
    out_hi_lim REAL DEFAULT 100.0,
    out_lo_lim REAL DEFAULT 0.0,
    arw_hi_lim REAL DEFAULT 100.0,
    arw_lo_lim REAL DEFAULT 0.0,
    pv_ftime REAL DEFAULT 0.0,
    sp_ftime REAL DEFAULT 0.0,
    low_cut REAL DEFAULT 0.0,
    shed_opt TEXT DEFAULT 'MAN',
    shed_time_s REAL DEFAULT 10.0
);

CREATE TABLE IF NOT EXISTS Configuracao_Alarmes (
    controlador_id INTEGER,
    deadband_percent REAL DEFAULT 1.0,
    hihi_val REAL, hihi_prioridade TEXT,
    hi_val REAL, hi_prioridade TEXT,
    lo_val REAL, lo_prioridade TEXT,
    lolo_val REAL, lolo_prioridade TEXT,
    FOREIGN KEY(controlador_id) REFERENCES Controladores(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Log_Processo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    controlador_id INTEGER NOT NULL,
    pv REAL, sp REAL, co REAL, integral_val REAL,
    FOREIGN KEY(controlador_id) REFERENCES Controladores(id)
);
CREATE INDEX IF NOT EXISTS idx_log_processo_time
    ON Log_Processo(timestamp, controlador_id);

CREATE TABLE IF NOT EXISTS Log_Sintonia_IA (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    controlador_id INTEGER NOT NULL,
    valor_anterior REAL,
    valor_novo REAL,
    justificativa TEXT
);

CREATE TABLE IF NOT EXISTS Log_Auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    usuario_id INTEGER,
    acao TEXT,
    valor_antigo TEXT,
    valor_novo TEXT
);

CREATE TABLE IF NOT EXISTS Log_Alarmes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    controlador_id INTEGER,
    tipo TEXT,
    prioridade TEXT,
    timestamp_in TEXT,
    timestamp_out TEXT,
    timestamp_ack TEXT,
    usuario_ack_id INTEGER
);
"""


class SQLiteRepository:
    """Async SQLite repository for controller configurations."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open connection and create tables if needed."""
        self._connection = await aiosqlite.connect(str(self._db_path))
        await self._connection.executescript(_SCHEMA_SQL)

    async def _conn(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Repository not initialized. Call initialize() first.")
        return self._connection

    async def save(self, controller: Controller) -> None:
        """Insert or update a controller."""
        conn = await self._conn()
        control_opts_json = json.dumps({
            "no_out_limits_in_manual": controller.control_opts.no_out_limits_in_manual,
            "obey_sp_limits_if_cas": controller.control_opts.obey_sp_limits_if_cas,
            "track_in_manual": controller.control_opts.track_in_manual,
            "track_enable": controller.control_opts.track_enable,
            "direct_acting": controller.control_opts.direct_acting,
            "sp_track_retained_target": controller.control_opts.sp_track_retained_target,
            "sp_pv_track_in_lo_or_iman": controller.control_opts.sp_pv_track_in_lo_or_iman,
            "sp_pv_track_in_rout": controller.control_opts.sp_pv_track_in_rout,
            "sp_pv_track_in_man": controller.control_opts.sp_pv_track_in_man,
        })
        io_opts_json = json.dumps({
            "low_cutoff": controller.io_opts.low_cutoff,
            "target_to_man_if_fault": controller.io_opts.target_to_man_if_fault,
            "fault_state_to_value": controller.io_opts.fault_state_to_value,
            "increase_to_close": controller.io_opts.increase_to_close,
            "sp_pv_track_in_lo_or_iman": controller.io_opts.sp_pv_track_in_lo_or_iman,
            "sp_pv_track_in_man": controller.io_opts.sp_pv_track_in_man,
        })
        permitted_json = json.dumps([m.value for m in controller.permitted_modes])

        if controller.id > 0:
            await conn.execute(
                """UPDATE Controladores SET nome=?, descricao=?, modo_execucao=?,
                   scan_rate_ms=?, pid_structure=?, integral_type=?,
                   kp=?, ti=?, td=?, alpha=?, deadband=?,
                   pv_scale_min=?, pv_scale_max=?, pv_scale_unit=?,
                   out_scale_min=?, out_scale_max=?, out_scale_unit=?,
                   node_id_pv=?, node_id_sp=?, node_id_co=?, node_id_integral=?,
                   control_opts_json=?, io_opts_json=?,
                   ai_engine=?, ai_objective=?, ai_process_speed=?,
                   ai_dead_time_l=?, ai_limit_min=?, ai_limit_max=?,
                   permitted_modes_json=?, mode_normal=?,
                   sp_hi_lim=?, sp_lo_lim=?, sp_rate_up=?, sp_rate_dn=?,
                   out_hi_lim=?, out_lo_lim=?, arw_hi_lim=?, arw_lo_lim=?,
                   pv_ftime=?, sp_ftime=?, low_cut=?, shed_opt=?, shed_time_s=?
                   WHERE id=?""",
                (controller.name, controller.description, controller.mode_execution.value,
                 controller.scan_rate_ms, controller.pid_structure.value,
                 controller.integral_type.value,
                 controller.pid_params.gain, controller.pid_params.reset,
                 controller.pid_params.rate, controller.pid_params.alpha,
                 controller.pid_params.deadband,
                 controller.pv_scale.eu_min, controller.pv_scale.eu_max, controller.pv_scale.unit,
                 controller.out_scale.eu_min, controller.out_scale.eu_max, controller.out_scale.unit,
                 controller.tag_bindings.node_id_pv, controller.tag_bindings.node_id_sp,
                 controller.tag_bindings.node_id_co, controller.tag_bindings.node_id_integral,
                 control_opts_json, io_opts_json,
                 controller.ai_config.engine.value, controller.ai_config.objective.value,
                 controller.ai_config.process_speed.value,
                 controller.ai_config.dead_time_l, controller.ai_config.limit_min,
                 controller.ai_config.limit_max,
                 permitted_json, controller.mode_normal.value,
                 controller.sp_hi_lim, controller.sp_lo_lim,
                 controller.sp_rate_up, controller.sp_rate_dn,
                 controller.out_hi_lim, controller.out_lo_lim,
                 controller.arw_hi_lim, controller.arw_lo_lim,
                 controller.pv_ftime, controller.sp_ftime,
                 controller.low_cut, controller.shed_opt.value, controller.shed_time_s,
                 controller.id),
            )
        else:
            await conn.execute(
                """INSERT INTO Controladores (nome, descricao, modo_execucao,
                   scan_rate_ms, pid_structure, integral_type,
                   kp, ti, td, alpha, deadband,
                   pv_scale_min, pv_scale_max, pv_scale_unit,
                   out_scale_min, out_scale_max, out_scale_unit,
                   node_id_pv, node_id_sp, node_id_co, node_id_integral,
                   control_opts_json, io_opts_json,
                   ai_engine, ai_objective, ai_process_speed,
                   ai_dead_time_l, ai_limit_min, ai_limit_max,
                   permitted_modes_json, mode_normal,
                   sp_hi_lim, sp_lo_lim, sp_rate_up, sp_rate_dn,
                   out_hi_lim, out_lo_lim, arw_hi_lim, arw_lo_lim,
                   pv_ftime, sp_ftime, low_cut, shed_opt, shed_time_s)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (controller.name, controller.description, controller.mode_execution.value,
                 controller.scan_rate_ms, controller.pid_structure.value,
                 controller.integral_type.value,
                 controller.pid_params.gain, controller.pid_params.reset,
                 controller.pid_params.rate, controller.pid_params.alpha,
                 controller.pid_params.deadband,
                 controller.pv_scale.eu_min, controller.pv_scale.eu_max, controller.pv_scale.unit,
                 controller.out_scale.eu_min, controller.out_scale.eu_max, controller.out_scale.unit,
                 controller.tag_bindings.node_id_pv, controller.tag_bindings.node_id_sp,
                 controller.tag_bindings.node_id_co, controller.tag_bindings.node_id_integral,
                 control_opts_json, io_opts_json,
                 controller.ai_config.engine.value, controller.ai_config.objective.value,
                 controller.ai_config.process_speed.value,
                 controller.ai_config.dead_time_l, controller.ai_config.limit_min,
                 controller.ai_config.limit_max,
                 permitted_json, controller.mode_normal.value,
                 controller.sp_hi_lim, controller.sp_lo_lim,
                 controller.sp_rate_up, controller.sp_rate_dn,
                 controller.out_hi_lim, controller.out_lo_lim,
                 controller.arw_hi_lim, controller.arw_lo_lim,
                 controller.pv_ftime, controller.sp_ftime,
                 controller.low_cut, controller.shed_opt.value, controller.shed_time_s),
            )
        await conn.commit()

    async def get(self, controller_id: int) -> Controller:
        """Fetch a controller by ID."""
        conn = await self._conn()
        cursor = await conn.execute(
            "SELECT * FROM Controladores WHERE id=?", (controller_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            from smart_pid.exceptions import DatabaseError
            raise DatabaseError(f"Controller {controller_id} not found")
        return self._row_to_controller(row, cursor.description)

    async def list_all(self) -> list[Controller]:
        """List all controllers."""
        conn = await self._conn()
        cursor = await conn.execute("SELECT * FROM Controladores ORDER BY nome")
        rows = await cursor.fetchall()
        return [self._row_to_controller(row, cursor.description) for row in rows]

    async def delete(self, controller_id: int) -> None:
        """Delete a controller by ID."""
        conn = await self._conn()
        await conn.execute("DELETE FROM Controladores WHERE id=?", (controller_id,))
        await conn.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    def _row_to_controller(
        self, row: aiosqlite.Row, description: tuple | None
    ) -> Controller:
        """Map a database row to a Controller domain model."""
        # Build column name -> index mapping
        cols = {d[0]: i for i, d in enumerate(description)} if description else {}
        r = lambda name: row[cols[name]]  # noqa: E731

        control_opts_data = json.loads(r("control_opts_json") or "{}")
        io_opts_data = json.loads(r("io_opts_json") or "{}")
        permitted_data = json.loads(r("permitted_modes_json") or '["MAN", "AUTO"]')

        return Controller(
            id=r("id"),
            name=r("nome"),
            description=r("descricao") or "",
            mode_execution=ExecutionMode(r("modo_execucao")),
            scan_rate_ms=r("scan_rate_ms"),
            pid_params=PIDParams(
                gain=r("kp"), reset=r("ti"), rate=r("td"),
                alpha=r("alpha"), deadband=r("deadband"),
            ),
            pid_structure=PIDStructure(r("pid_structure")),
            integral_type=IntegralType(r("integral_type")),
            pv_scale=ScaleConfig(r("pv_scale_min"), r("pv_scale_max"), r("pv_scale_unit") or ""),
            out_scale=ScaleConfig(r("out_scale_min"), r("out_scale_max"), r("out_scale_unit") or ""),
            tag_bindings=TagBindings(
                node_id_pv=r("node_id_pv") or "",
                node_id_sp=r("node_id_sp") or "",
                node_id_co=r("node_id_co") or "",
                node_id_integral=r("node_id_integral") or "",
            ),
            control_opts=ControlOpts(**control_opts_data) if control_opts_data else ControlOpts(),
            io_opts=IOOpts(**io_opts_data) if io_opts_data else IOOpts(),
            ai_config=AIConfig(
                engine=AIEngine(r("ai_engine")),
                objective=ControlObjective(r("ai_objective")),
                process_speed=ProcessSpeed(r("ai_process_speed")),
                dead_time_l=r("ai_dead_time_l"),
                limit_min=r("ai_limit_min"),
                limit_max=r("ai_limit_max"),
            ),
            permitted_modes={PIDMode(m) for m in permitted_data},
            mode_normal=PIDMode(r("mode_normal")),
            sp_hi_lim=r("sp_hi_lim"), sp_lo_lim=r("sp_lo_lim"),
            sp_rate_up=r("sp_rate_up"), sp_rate_dn=r("sp_rate_dn"),
            out_hi_lim=r("out_hi_lim"), out_lo_lim=r("out_lo_lim"),
            arw_hi_lim=r("arw_hi_lim"), arw_lo_lim=r("arw_lo_lim"),
            pv_ftime=r("pv_ftime"), sp_ftime=r("sp_ftime"),
            low_cut=r("low_cut"),
            shed_opt=PIDMode(r("shed_opt")),
            shed_time_s=r("shed_time_s"),
        )
```

- [ ] **Step 4: Implement historian**

```python
# src/smart_pid/adapters/outbound/historian.py
"""SQLite historian for batch process data logging.

Writes telemetry frames in batches via executemany().
Queries for trend charts and export.
Cleanup by retention policy.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from smart_pid.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid.domain.models.controller import SignalStatus
from smart_pid.domain.models.telemetry import TelemetryFrame


class SQLiteHistorian:
    """Batch historian backed by the same SQLite connection as the repo."""

    def __init__(self, repo: SQLiteRepository) -> None:
        self._repo = repo

    async def write_batch(self, frames: list[TelemetryFrame]) -> None:
        """Batch INSERT telemetry frames into Log_Processo."""
        if not frames:
            return
        conn = await self._repo._conn()
        rows = [
            (f.timestamp.isoformat(), f.controller_id, f.pv, f.sp, f.co, f.integral_val)
            for f in frames
        ]
        await conn.executemany(
            """INSERT INTO Log_Processo (timestamp, controlador_id, pv, sp, co, integral_val)
               VALUES (?, ?, ?, ?, ?, ?)""",
            rows,
        )
        await conn.commit()

    async def query(
        self,
        controller_id: int,
        start: datetime,
        end: datetime,
    ) -> list[TelemetryFrame]:
        """Query process historian for a time range."""
        conn = await self._repo._conn()
        cursor = await conn.execute(
            """SELECT timestamp, controlador_id, pv, sp, co, integral_val
               FROM Log_Processo
               WHERE controlador_id=? AND timestamp >= ? AND timestamp <= ?
               ORDER BY timestamp""",
            (controller_id, start.isoformat(), end.isoformat()),
        )
        rows = await cursor.fetchall()
        return [
            TelemetryFrame(
                controller_id=row[1],
                pv=row[2],
                sp=row[3],
                co=row[4],
                integral_val=row[5],
                timestamp=datetime.fromisoformat(row[0]),
                status=SignalStatus.GOOD,
            )
            for row in rows
        ]

    async def cleanup_older_than(self, days: int) -> int:
        """Delete records older than the specified retention period.

        Returns the number of deleted rows.
        """
        conn = await self._repo._conn()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = await conn.execute(
            "DELETE FROM Log_Processo WHERE timestamp <= ?", (cutoff,)
        )
        await conn.commit()
        return cursor.rowcount
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
uv run pytest tests/integration/test_sqlite_repo.py -v
```
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/smart_pid/adapters/outbound/sqlite_repo.py src/smart_pid/adapters/outbound/historian.py tests/integration/test_sqlite_repo.py
git commit -m "feat: implement SQLite repository and batch historian with WAL mode"
```

---

## Task 10: PID Worker Thread

**Files:**
- Create: `src/smart_pid/application/workers/pid_worker.py`

- [ ] **Step 1: Implement PID worker**

```python
# src/smart_pid/application/workers/pid_worker.py
"""High-priority PID worker thread.

Executes the PID equation at the configured scan rate.
Consumes TELEMETRY.{id} from the bus.
Publishes ACTION.CTRL.{id} with the computed output.
Accepts AI adjustments via ACTION.AI.{id}.

Determinism: uses time.monotonic() for precise timing.
Resilience: continues with last valid Ki if AI fails.
"""
from __future__ import annotations

import threading
import time

import structlog

from smart_pid.application.event_bus import BusPublisher, BusSubscriber, EventBus
from smart_pid.domain.models.controller import Controller, PIDMode, SignalStatus
from smart_pid.domain.services.pid_engine import PIDEngine, PIDState
from smart_pid.domain.services.pid_mode_manager import BlockStatus, ModeManager

log = structlog.get_logger()


class PIDWorker(threading.Thread):
    """Dedicated PID computation thread for a single controller."""

    def __init__(
        self,
        controller: Controller,
        bus: EventBus,
        pid_engine: PIDEngine,
        mode_manager: ModeManager,
    ) -> None:
        super().__init__(daemon=True, name=f"PID-{controller.name}")
        self._controller = controller
        self._bus = bus
        self._pid = pid_engine
        self._mode_mgr = mode_manager
        self._state = PIDState()
        self._mode_actual = PIDMode.MAN
        self._mode_target = PIDMode.MAN
        self._block_status = BlockStatus()
        self._running = threading.Event()
        self._paused = threading.Event()
        self._latest_telemetry: dict | None = None
        self._ai_ki_override: float | None = None
        self._pub: BusPublisher | None = None
        self._sub: BusSubscriber | None = None

    def run(self) -> None:
        """Main loop: read telemetry, compute PID, publish action."""
        self._running.set()
        ctrl_id = self._controller.id
        scan_rate_s = self._controller.scan_rate_ms / 1000.0

        self._pub = self._bus.publisher()
        self._sub = self._bus.subscriber([
            f"TELEMETRY.{ctrl_id}",
            f"ACTION.AI.{ctrl_id}",
        ])

        log.info(
            "pid_worker.started",
            controller=self._controller.name,
            scan_rate_ms=self._controller.scan_rate_ms,
        )

        while self._running.is_set():
            t_start = time.monotonic()

            # Drain all pending messages (non-blocking)
            self._drain_bus()

            # Execute PID if we have telemetry and mode allows it
            if self._latest_telemetry is not None:
                self._execute_scan()

            # Sleep for remaining scan time
            elapsed = time.monotonic() - t_start
            sleep_time = scan_rate_s - elapsed
            if sleep_time > 0:
                self._running.wait(timeout=sleep_time)
            else:
                log.warning(
                    "pid_worker.overrun",
                    controller=self._controller.name,
                    elapsed_ms=round(elapsed * 1000),
                )

        log.info("pid_worker.stopped", controller=self._controller.name)

    def _drain_bus(self) -> None:
        """Read all available messages from the bus without blocking."""
        while True:
            msg = self._sub.receive_noblock() if self._sub else None
            if msg is None:
                break
            topic, data = msg
            if topic.startswith("TELEMETRY."):
                self._latest_telemetry = data
            elif topic.startswith("ACTION.AI."):
                if "new_ki" in data:
                    self._ai_ki_override = data["new_ki"]
                    log.info(
                        "pid_worker.ai_update",
                        controller=self._controller.name,
                        new_ki=data["new_ki"],
                    )

    def _execute_scan(self) -> None:
        """Run one PID scan cycle."""
        telem = self._latest_telemetry
        if telem is None:
            return

        params = self._controller.pid_params

        # Apply AI Ki override if available
        if self._ai_ki_override is not None:
            from dataclasses import replace
            params = replace(params, reset=self._ai_ki_override)

        # Check forced mode transitions
        forced = self._mode_mgr.evaluate_forced_transitions(
            current=self._mode_actual,
            block_status=self._block_status,
            shed_mode=self._controller.shed_opt,
        )
        if forced is not None and forced != self._mode_actual:
            log.info(
                "pid_worker.forced_mode",
                controller=self._controller.name,
                old=self._mode_actual.value,
                new=forced.value,
            )
            self._mode_actual = forced

        # Only compute PID in automatic modes
        if self._mode_actual in {PIDMode.AUTO, PIDMode.CAS, PIDMode.RCAS}:
            dt = self._controller.scan_rate_ms / 1000.0

            # Apply SP ramp
            sp = self._pid.apply_sp_ramp(
                sp_target=telem["sp"],
                sp_current=self._state.sp_working if self._state.sp_working != 0 else telem["sp"],
                rate_up=self._controller.sp_rate_up,
                rate_dn=self._controller.sp_rate_dn,
                dt=dt,
            )

            result = self._pid.compute(
                params=params,
                state=self._state,
                pv=telem["pv"],
                sp=sp,
                dt=dt,
                out_limits=(self._controller.out_lo_lim, self._controller.out_hi_lim),
                direct_acting=self._controller.control_opts.direct_acting,
            )

            self._state = result.new_state

            # Publish control action
            if self._pub:
                self._pub.publish(
                    f"ACTION.CTRL.{self._controller.id}",
                    {"co": result.cv, "integral_val": params.reset},
                )

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running.clear()

    def request_mode(self, target: PIDMode) -> bool:
        """Request a mode change from external caller."""
        transition = self._mode_mgr.request_mode(
            current=self._mode_actual,
            target=target,
            permitted=self._controller.permitted_modes,
            block_status=self._block_status,
        )
        if transition.accepted:
            if transition.requires_bumpless and self._latest_telemetry:
                telem = self._latest_telemetry
                self._state = self._pid.bumpless_transfer(
                    state=self._state,
                    current_pv=telem["pv"],
                    current_co=telem["co"],
                    params=self._controller.pid_params,
                )
            self._mode_actual = transition.new_mode
            log.info(
                "pid_worker.mode_changed",
                controller=self._controller.name,
                new_mode=transition.new_mode.value,
            )
            return True
        log.warning(
            "pid_worker.mode_rejected",
            controller=self._controller.name,
            reason=transition.rejection_reason,
        )
        return False
```

- [ ] **Step 2: Verify with ruff and mypy**

Run:
```bash
uv run ruff check src/smart_pid/application/workers/pid_worker.py && uv run mypy src/smart_pid/application/workers/pid_worker.py
```
Expected: No errors (warnings about unresolved types are acceptable at this stage).

- [ ] **Step 3: Commit**

```bash
git add src/smart_pid/application/workers/pid_worker.py
git commit -m "feat: implement PID worker thread with scan rate loop and bus integration"
```

---

## Task 11: DB Worker Thread

**Files:**
- Create: `src/smart_pid/application/workers/db_worker.py`

- [ ] **Step 1: Implement DB worker**

```python
# src/smart_pid/application/workers/db_worker.py
"""Database worker thread for batch inserts.

Subscribes to TELEMETRY.*, EVENT.ALARM.*, LOG.AI.* on the bus.
Accumulates data in RAM buffers (deque).
Flushes to SQLite every flush_interval seconds.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime

import structlog

from smart_pid.application.event_bus import EventBus
from smart_pid.domain.models.controller import SignalStatus
from smart_pid.domain.models.telemetry import TelemetryFrame

log = structlog.get_logger()


class DBWorker(threading.Thread):
    """Shared database writer thread. One per application."""

    def __init__(
        self,
        bus: EventBus,
        historian: object,  # HistorianWriter protocol
        flush_interval: float = 5.0,
        max_buffer_size: int = 10000,
    ) -> None:
        super().__init__(daemon=True, name="DB-Worker")
        self._bus = bus
        self._historian = historian
        self._flush_interval = flush_interval
        self._telemetry_buffer: deque[TelemetryFrame] = deque(maxlen=max_buffer_size)
        self._running = threading.Event()

    def run(self) -> None:
        """Main loop: drain bus, accumulate, flush periodically."""
        self._running.set()

        sub = self._bus.subscriber([
            "TELEMETRY.",
            "EVENT.ALARM.",
            "LOG.AI.",
        ])

        log.info("db_worker.started", flush_interval=self._flush_interval)

        last_flush = time.monotonic()

        while self._running.is_set():
            # Drain messages
            msg = sub.receive(timeout_ms=500)
            if msg:
                topic, data = msg
                if topic.startswith("TELEMETRY."):
                    self._buffer_telemetry(data)

            # Flush if interval elapsed
            now = time.monotonic()
            if now - last_flush >= self._flush_interval:
                self._flush()
                last_flush = now

        # Final flush on shutdown
        self._flush()
        log.info("db_worker.stopped")

    def _buffer_telemetry(self, data: dict) -> None:
        """Convert bus message to TelemetryFrame and buffer."""
        try:
            frame = TelemetryFrame(
                controller_id=data["controller_id"],
                pv=data["pv"],
                sp=data["sp"],
                co=data["co"],
                integral_val=data.get("integral_val", 0.0),
                timestamp=datetime.fromisoformat(data["timestamp"])
                if isinstance(data.get("timestamp"), str)
                else datetime.now(),
                status=SignalStatus.GOOD,
            )
            self._telemetry_buffer.append(frame)
        except (KeyError, ValueError) as e:
            log.warning("db_worker.parse_error", error=str(e))

    def _flush(self) -> None:
        """Flush all buffered data to the historian."""
        if not self._telemetry_buffer:
            return

        frames = list(self._telemetry_buffer)
        self._telemetry_buffer.clear()

        import asyncio

        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._historian.write_batch(frames))
            loop.close()
            log.debug("db_worker.flushed", count=len(frames))
        except Exception:
            log.exception("db_worker.flush_error", count=len(frames))

    def stop(self) -> None:
        """Signal the worker to stop."""
        self._running.clear()
```

- [ ] **Step 2: Verify**

Run:
```bash
uv run ruff check src/smart_pid/application/workers/db_worker.py && uv run mypy src/smart_pid/application/workers/db_worker.py
```
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add src/smart_pid/application/workers/db_worker.py
git commit -m "feat: implement DB worker thread with batch insert buffering"
```

---

## Task 12: Structured Logging Setup

**Files:**
- Create: `src/smart_pid/logging_config.py`

- [ ] **Step 1: Implement logging configuration**

```python
# src/smart_pid/logging_config.py
"""Structured logging setup with structlog."""
from __future__ import annotations

import logging

import structlog

from smart_pid.config import LogLevel


def configure_logging(level: LogLevel = LogLevel.INFO) -> None:
    """Configure structlog with console rendering for development."""
    log_level = getattr(logging, level.value)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

- [ ] **Step 2: Commit**

```bash
git add src/smart_pid/logging_config.py
git commit -m "feat: add structured logging configuration with structlog"
```

---

## Task 13: Main Entry Point (Bootstrap)

**Files:**
- Create: `src/smart_pid/main.py`

- [ ] **Step 1: Implement main.py**

```python
# src/smart_pid/main.py
"""Smart PID Edge Optimizer entry point.

Phase 1 bootstrap: initializes logging, event bus, database,
and provides CLI entry for testing the PID core without UI.
"""
from __future__ import annotations

import sys

import structlog

from smart_pid.config import settings
from smart_pid.logging_config import configure_logging


def main() -> None:
    """Application entry point."""
    configure_logging(settings.log_level)
    log = structlog.get_logger()

    log.info(
        "app.starting",
        version=settings.app_version,
        log_level=settings.log_level.value,
    )

    # Phase 1: Initialize core infrastructure
    from smart_pid.application.event_bus import EventBus

    bus = EventBus()
    bus.start_proxy()
    log.info("app.bus_started")

    log.info("app.ready", message="Phase 1 - Foundation + PID Core initialized")

    # In Phase 2, the Qt event loop will run here.
    # For now, just confirm bootstrap works and exit.
    bus.shutdown()
    log.info("app.shutdown")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the entry point to verify bootstrap**

Run:
```bash
uv run smart-pid
```
Expected: Log output showing `app.starting`, `app.bus_started`, `app.ready`, `app.shutdown` — clean exit.

- [ ] **Step 3: Run full test suite**

Run:
```bash
uv run pytest tests/ -v
```
Expected: All tests PASS.

- [ ] **Step 4: Run ruff and mypy on entire project**

Run:
```bash
uv run ruff check src/ tests/ && uv run mypy src/
```
Expected: No errors (or only expected warnings for protocol implementations).

- [ ] **Step 5: Commit**

```bash
git add src/smart_pid/main.py
git commit -m "feat: add main entry point with Phase 1 bootstrap"
```

---

## Task 14: Final Verification and Phase 1 Commit

- [ ] **Step 1: Run complete test suite with coverage**

Run:
```bash
uv run pytest tests/ -v --tb=short
```
Expected: All tests pass. Should have tests for: PID engine (proportional, integral, derivative, anti-windup, bumpless, SP ramp, deadband), mode manager (transitions, forced modes), event bus (pub/sub, filtering, cross-thread), SQLite repo (CRUD), historian (batch write, query, cleanup).

- [ ] **Step 2: Run linting and type checking**

Run:
```bash
uv run ruff check src/ tests/ && uv run mypy src/
```
Expected: Clean.

- [ ] **Step 3: Run the application**

Run:
```bash
uv run smart-pid
```
Expected: Clean startup and shutdown log messages.

- [ ] **Step 4: Create Phase 1 completion commit**

```bash
git add -A
git commit -m "milestone: Phase 1 complete — Foundation + PID Core

Implemented:
- Project scaffold with uv, pyproject.toml, structlog
- Domain models: Controller, PIDParams, TelemetryFrame, enums
- Domain events: TelemetryReceived, ControlActionComputed
- Domain ports: TelemetrySource, ControllerRepository, HistorianWriter
- PID engine: velocity form, anti-windup, bumpless transfer, SP ramp
- PID mode manager: 8-mode state machine with forced transitions
- ZeroMQ event bus: XPUB/XSUB proxy with msgpack serialization
- SQLite repository: full DDL schema, CRUD operations, WAL mode
- SQLite historian: batch insert, time-range query, retention cleanup
- PID worker thread: scan rate loop, bus integration
- DB worker thread: buffered batch inserts

Ready for Phase 2: Basic UI + Operational Dashboard"
```
