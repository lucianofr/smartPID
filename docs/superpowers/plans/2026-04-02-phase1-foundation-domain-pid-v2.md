# Phase 1: Foundation + Domain + PID Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the project into a monorepo with 3 uv workspace packages, migrate existing domain code, and build core Backend infrastructure (event bus, workers, SQLite).

**Architecture:** Monorepo with `smart_pid_domain` (shared models/events/enums), `smart_pid_core` (backend daemon), and `smart_pid_hmi` (stub). The backend uses ZeroMQ `inproc://` XPUB/XSUB for inter-thread messaging, a PID Worker thread per controller, and a shared DB Worker for SQLite batch writes.

**Tech Stack:** Python 3.13+, uv workspaces, pyzmq, msgpack, aiosqlite, pydantic, pydantic-settings, structlog, numpy, pytest

**Spec Reference:** `docs/superpowers/specs/2026-04-02-smart-pid-v2-architecture-design.md`

---

## File Map

### New files to create

```
packages/
├── smart_pid_domain/
│   ├── pyproject.toml
│   └── src/smart_pid_domain/
│       ├── __init__.py
│       ├── enums.py                    # All StrEnum types extracted from controller.py
│       ├── models/
│       │   ├── __init__.py
│       │   ├── controller.py           # Migrated from src/smart_pid/domain/models/controller.py
│       │   └── telemetry.py            # Migrated from src/smart_pid/domain/models/telemetry.py
│       ├── events.py                   # Migrated from src/smart_pid/domain/events.py
│       └── exceptions.py              # Migrated + extended from src/smart_pid/exceptions.py
│
├── smart_pid_core/
│   ├── pyproject.toml
│   └── src/smart_pid_core/
│       ├── __init__.py
│       ├── config.py                   # Backend settings (pydantic-settings)
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── ports/
│       │   │   ├── __init__.py
│       │   │   ├── inbound.py          # Migrated from src/smart_pid/domain/ports/inbound.py
│       │   │   └── outbound.py         # Migrated from src/smart_pid/domain/ports/outbound.py
│       │   └── services/
│       │       ├── __init__.py
│       │       ├── pid_engine.py       # Migrated from src/smart_pid/domain/services/pid_engine.py
│       │       └── pid_mode_manager.py # Migrated from src/smart_pid/domain/services/pid_mode_manager.py
│       └── application/
│           ├── __init__.py
│           ├── event_bus.py            # ZeroMQ inproc:// XPUB/XSUB proxy
│           ├── workers/
│           │   ├── __init__.py
│           │   ├── pid_worker.py       # High-priority PID thread
│           │   └── db_worker.py        # Shared SQLite batch writer
│           └── loop_manager.py         # Controller lifecycle management
│
│── smart_pid_hmi/
│   ├── pyproject.toml
│   └── src/smart_pid_hmi/
│       └── __init__.py                 # Stub only
│
tests/
├── conftest.py                         # Updated root conftest
├── domain/
│   ├── __init__.py
│   ├── test_models.py                  # Model construction tests
│   └── test_events.py                  # Event creation tests
├── core/
│   ├── __init__.py
│   ├── conftest.py                     # Core-specific fixtures
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_pid_engine.py          # Migrated + updated imports
│   │   └── test_pid_mode_manager.py    # Migrated + updated imports
│   └── integration/
│       ├── __init__.py
│       ├── test_event_bus.py           # ZeroMQ bus tests
│       ├── test_sqlite_repo.py         # Repository CRUD tests
│       ├── test_historian.py           # Batch insert + query + cleanup
│       ├── test_db_worker.py           # DB Worker integration
│       └── test_pid_worker.py          # PID Worker integration
└── hmi/
    └── __init__.py                     # Stub only
```

### Files to delete (after migration)

```
src/smart_pid/                          # Entire old package removed
tests/unit/                             # Old test directory
tests/integration/                      # Old test directory
```

---

## Task 1: Scaffold uv Workspace with 3 Packages

**Files:**
- Modify: `pyproject.toml` (root)
- Create: `packages/smart_pid_domain/pyproject.toml`
- Create: `packages/smart_pid_domain/src/smart_pid_domain/__init__.py`
- Create: `packages/smart_pid_core/pyproject.toml`
- Create: `packages/smart_pid_core/src/smart_pid_core/__init__.py`
- Create: `packages/smart_pid_hmi/pyproject.toml`
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/__init__.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p packages/smart_pid_domain/src/smart_pid_domain
mkdir -p packages/smart_pid_core/src/smart_pid_core
mkdir -p packages/smart_pid_hmi/src/smart_pid_hmi
```

- [ ] **Step 2: Write root pyproject.toml as workspace**

Replace the entire `pyproject.toml` with:

```toml
[project]
name = "smart-pid-workspace"
version = "0.1.0"
description = "Smart PID Edge Platform — Workspace Root"
requires-python = ">=3.13"

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv.sources]
smart-pid-domain = { workspace = true }
smart-pid-core = { workspace = true }
smart-pid-hmi = { workspace = true }

[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "TCH"]

[tool.ruff.lint.isort]
known-first-party = ["smart_pid_domain", "smart_pid_core", "smart_pid_hmi"]

[tool.mypy]
strict = true
python_version = "3.13"
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Write smart_pid_domain/pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "smart-pid-domain"
version = "0.1.0"
description = "Smart PID — Shared domain models, events, enums"
requires-python = ">=3.13"
dependencies = [
    "pydantic>=2.7",
    "msgpack>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "mypy>=1.10",
    "ruff>=0.4",
]

[tool.hatch.build.targets.wheel]
packages = ["src/smart_pid_domain"]
```

- [ ] **Step 4: Write smart_pid_core/pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "smart-pid-core"
version = "0.1.0"
description = "Smart PID — Backend daemon (Core Engine)"
requires-python = ">=3.13"
dependencies = [
    "smart-pid-domain",
    "pyzmq>=26.0",
    "msgpack>=1.0",
    "aiosqlite>=0.20",
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
smart-pid-core = "smart_pid_core.main:main"

[tool.hatch.build.targets.wheel]
packages = ["src/smart_pid_core"]
```

- [ ] **Step 5: Write smart_pid_hmi/pyproject.toml (stub)**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "smart-pid-hmi"
version = "0.1.0"
description = "Smart PID — Desktop HMI Client"
requires-python = ">=3.13"
dependencies = [
    "smart-pid-domain",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "mypy>=1.10",
    "ruff>=0.4",
]

[tool.hatch.build.targets.wheel]
packages = ["src/smart_pid_hmi"]
```

- [ ] **Step 6: Write __init__.py files**

`packages/smart_pid_domain/src/smart_pid_domain/__init__.py`:
```python
"""Smart PID — Shared domain models, events, and enums."""

__version__ = "0.1.0"
```

`packages/smart_pid_core/src/smart_pid_core/__init__.py`:
```python
"""Smart PID — Backend daemon (Core Engine)."""

__version__ = "0.1.0"
```

`packages/smart_pid_hmi/src/smart_pid_hmi/__init__.py`:
```python
"""Smart PID — Desktop HMI Client (stub)."""

__version__ = "0.1.0"
```

- [ ] **Step 7: Sync workspace**

```bash
uv sync
```

Expected: All 3 packages installed in editable mode. No errors.

- [ ] **Step 8: Verify imports**

```bash
uv run python -c "import smart_pid_domain; print(smart_pid_domain.__version__)"
uv run python -c "import smart_pid_core; print(smart_pid_core.__version__)"
uv run python -c "import smart_pid_hmi; print(smart_pid_hmi.__version__)"
```

Expected: Each prints `0.1.0`.

- [ ] **Step 9: Commit**

```bash
git add packages/ pyproject.toml
git commit -m "chore: scaffold uv workspace with 3 packages (domain, core, hmi)"
```

---

## Task 2: Migrate Enums to smart_pid_domain

**Files:**
- Create: `packages/smart_pid_domain/src/smart_pid_domain/enums.py`
- Test: `tests/domain/__init__.py`, `tests/domain/test_models.py`

- [ ] **Step 1: Write test for enums**

Create `tests/domain/__init__.py` (empty).

Create `tests/domain/test_models.py`:

```python
from __future__ import annotations

from smart_pid_domain.enums import (
    AIEngine,
    ConnectionState,
    ControllerMode,
    ControlObjective,
    ExecutionMode,
    IntegralType,
    OptimizerState,
    PIDStructure,
    ProcessSpeed,
    SignalStatus,
    UserRole,
)


class TestEnums:
    def test_controller_mode_has_eight_values(self) -> None:
        assert len(ControllerMode) == 8
        assert ControllerMode.OOS == "OOS"
        assert ControllerMode.AUTO == "AUTO"

    def test_execution_mode_values(self) -> None:
        assert ExecutionMode.SUPERVISORY == "SUPERVISORY"
        assert ExecutionMode.DDC == "DDC"

    def test_ai_engine_values(self) -> None:
        assert AIEngine.NONE == "NONE"
        assert AIEngine.FUZZY == "FUZZY"
        assert AIEngine.RL == "RL"

    def test_control_objective_values(self) -> None:
        assert len(ControlObjective) == 3

    def test_process_speed_values(self) -> None:
        assert len(ProcessSpeed) == 3

    def test_connection_state_values(self) -> None:
        assert len(ConnectionState) == 3

    def test_signal_status_values(self) -> None:
        assert len(SignalStatus) == 3

    def test_pid_structure_values(self) -> None:
        assert len(PIDStructure) == 3

    def test_integral_type_values(self) -> None:
        assert len(IntegralType) == 2

    def test_optimizer_state_values(self) -> None:
        assert OptimizerState.RUN == "RUN"
        assert OptimizerState.PAUSE == "PAUSE"
        assert OptimizerState.STOP == "STOP"

    def test_user_role_values(self) -> None:
        assert UserRole.ADMIN == "ADMIN"
        assert UserRole.SUPERVISOR == "SUPERVISOR"
        assert UserRole.OPERATOR == "OPERATOR"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/domain/test_models.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_domain.enums'`

- [ ] **Step 3: Create enums.py**

Create `packages/smart_pid_domain/src/smart_pid_domain/enums.py`:

```python
"""All shared enumerations for the Smart PID platform."""

from __future__ import annotations

from enum import StrEnum


class ControllerMode(StrEnum):
    """Operating modes for the PID block (bloco_pid.md Section 3.2)."""

    OOS = "OOS"
    IMAN = "IMAN"
    LO = "LO"
    MAN = "MAN"
    AUTO = "AUTO"
    CAS = "CAS"
    RCAS = "RCAS"
    ROUT = "ROUT"


class ExecutionMode(StrEnum):
    """How the PID loop executes — supervisory (PLC owns PID) or DDC (backend owns PID)."""

    SUPERVISORY = "SUPERVISORY"
    DDC = "DDC"


class PIDStructure(StrEnum):
    ISA = "ISA"
    PARALLEL = "PARALLEL"
    SERIES = "SERIES"


class IntegralType(StrEnum):
    GAIN_KI = "GAIN_KI"
    TIME_TI = "TIME_TI"


class AIEngine(StrEnum):
    NONE = "NONE"
    FUZZY = "FUZZY"
    RL = "RL"


class ControlObjective(StrEnum):
    SP_TRACKING = "SP_TRACKING"
    DISTURBANCE_REJECTION = "DISTURBANCE_REJECTION"
    SURGE_LEVEL = "SURGE_LEVEL"


class ProcessSpeed(StrEnum):
    SLOW = "SLOW"
    MEDIUM = "MEDIUM"
    FAST = "FAST"


class ConnectionState(StrEnum):
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"
    RECONNECTING = "RECONNECTING"


class SignalStatus(StrEnum):
    GOOD = "GOOD"
    BAD = "BAD"
    UNCERTAIN = "UNCERTAIN"


class OptimizerState(StrEnum):
    RUN = "RUN"
    PAUSE = "PAUSE"
    STOP = "STOP"


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    OPERATOR = "OPERATOR"


class AlarmPriority(StrEnum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    ADVISORY = "ADVISORY"
    LOG = "LOG"


class AlarmType(StrEnum):
    HIHI = "HIHI"
    HI = "HI"
    LO = "LO"
    LOLO = "LOLO"
    DV_HI = "DV_HI"
    DV_LO = "DV_LO"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
uv run pytest tests/domain/test_models.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/enums.py tests/domain/
git commit -m "feat(domain): add shared enums to smart_pid_domain"
```

---

## Task 3: Migrate Domain Models to smart_pid_domain

**Files:**
- Create: `packages/smart_pid_domain/src/smart_pid_domain/models/__init__.py`
- Create: `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py`
- Create: `packages/smart_pid_domain/src/smart_pid_domain/models/telemetry.py`
- Modify: `tests/domain/test_models.py`

- [ ] **Step 1: Add model construction tests**

Append to `tests/domain/test_models.py`:

```python
from datetime import datetime, timezone

from smart_pid_domain.models.controller import (
    AIConfig,
    ControlOpts,
    Controller,
    IOOpts,
    PIDParams,
    ScaleConfig,
    TagBindings,
)
from smart_pid_domain.models.telemetry import ControlAction, TelemetryFrame


class TestPIDParams:
    def test_defaults(self) -> None:
        p = PIDParams()
        assert p.gain == 1.0
        assert p.reset == 10.0
        assert p.rate == 0.0
        assert p.alpha == 0.125
        assert p.deadband == 0.0


class TestScaleConfig:
    def test_span(self) -> None:
        s = ScaleConfig(eu_min=0.0, eu_max=100.0, unit="degC")
        assert s.span == 100.0

    def test_negative_range(self) -> None:
        s = ScaleConfig(eu_min=-50.0, eu_max=50.0, unit="%")
        assert s.span == 100.0


class TestTelemetryFrame:
    def test_is_frozen(self) -> None:
        now = datetime.now(tz=timezone.utc)
        frame = TelemetryFrame(
            controller_id=1, pv=50.0, sp=50.0, co=25.0,
            integral_val=1.0, timestamp=now, status=SignalStatus.GOOD,
        )
        assert frame.pv == 50.0
        # Frozen — assignment raises
        import pytest
        with pytest.raises(AttributeError):
            frame.pv = 99.0  # type: ignore[misc]


class TestControlAction:
    def test_construction(self) -> None:
        now = datetime.now(tz=timezone.utc)
        action = ControlAction(controller_id=1, co=45.0, integral_val=1.5, timestamp=now)
        assert action.co == 45.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/domain/test_models.py::TestPIDParams -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_domain.models'`

- [ ] **Step 3: Create models directory and controller.py**

Create `packages/smart_pid_domain/src/smart_pid_domain/models/__init__.py`:

```python
"""Domain models for the Smart PID platform."""

from __future__ import annotations

from smart_pid_domain.models.controller import (
    AIConfig,
    ControlOpts,
    Controller,
    IOOpts,
    PIDParams,
    ScaleConfig,
    TagBindings,
)
from smart_pid_domain.models.telemetry import ControlAction, TelemetryFrame

__all__ = [
    "AIConfig",
    "ControlAction",
    "ControlOpts",
    "Controller",
    "IOOpts",
    "PIDParams",
    "ScaleConfig",
    "TagBindings",
    "TelemetryFrame",
]
```

Create `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py`:

```python
"""Controller configuration and related dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field

from smart_pid_domain.enums import (
    AIEngine,
    ControllerMode,
    ControlObjective,
    ExecutionMode,
    IntegralType,
    PIDStructure,
    ProcessSpeed,
)


@dataclass
class ScaleConfig:
    eu_min: float
    eu_max: float
    unit: str = ""

    @property
    def span(self) -> float:
        return self.eu_max - self.eu_min


@dataclass
class PIDParams:
    gain: float = 1.0
    reset: float = 10.0
    rate: float = 0.0
    alpha: float = 0.125
    deadband: float = 0.0


@dataclass
class AIConfig:
    engine: AIEngine = AIEngine.NONE
    objective: ControlObjective = ControlObjective.DISTURBANCE_REJECTION
    process_speed: ProcessSpeed = ProcessSpeed.MEDIUM
    dead_time_l: float = 1.0
    limit_min: float = 0.1
    limit_max: float = 100.0


@dataclass
class TagBindings:
    node_id_pv: str = ""
    node_id_sp: str = ""
    node_id_co: str = ""
    node_id_integral: str = ""


@dataclass
class ControlOpts:
    no_out_limits_in_manual: bool = False
    obey_sp_limits_if_cas: bool = False
    use_pv_for_bkcal_out: bool = False
    track_in_manual: bool = False
    track_enable: bool = False
    direct_acting: bool = False
    sp_track_retained_target: bool = False
    sp_pv_track_in_lo_or_iman: bool = False
    sp_pv_track_in_man: bool = False


@dataclass
class IOOpts:
    low_cutoff: bool = False
    target_to_man_if_fault: bool = False
    fault_state_to_value: bool = False
    increase_to_close: bool = False
    sp_pv_track_in_lo_or_iman: bool = False
    sp_pv_track_in_man: bool = False


@dataclass
class Controller:
    id: int
    name: str
    description: str = ""
    execution_mode: ExecutionMode = ExecutionMode.DDC
    scan_rate_ms: int = 1000
    pid_params: PIDParams = field(default_factory=PIDParams)
    pid_structure: PIDStructure = PIDStructure.ISA
    integral_type: IntegralType = IntegralType.TIME_TI
    pv_scale: ScaleConfig = field(default_factory=lambda: ScaleConfig(0.0, 100.0, "%"))
    out_scale: ScaleConfig = field(default_factory=lambda: ScaleConfig(0.0, 100.0, "%"))
    tag_bindings: TagBindings = field(default_factory=TagBindings)
    control_opts: ControlOpts = field(default_factory=ControlOpts)
    io_opts: IOOpts = field(default_factory=IOOpts)
    ai_config: AIConfig = field(default_factory=AIConfig)
    permitted_modes: set[ControllerMode] = field(
        default_factory=lambda: {ControllerMode.MAN, ControllerMode.AUTO}
    )
    mode_normal: ControllerMode = ControllerMode.AUTO
    sp_hi_lim: float = 100.0
    sp_lo_lim: float = 0.0
    sp_rate_up: float = 0.0
    sp_rate_dn: float = 0.0
    out_hi_lim: float = 100.0
    out_lo_lim: float = 0.0
    arw_hi_lim: float = 100.0
    arw_lo_lim: float = 0.0
    pv_ftime: float = 0.0
    sp_ftime: float = 0.0
    low_cut: float = 0.0
    shed_opt: ControllerMode = ControllerMode.MAN
    shed_time_s: float = 30.0
```

Create `packages/smart_pid_domain/src/smart_pid_domain/models/telemetry.py`:

```python
"""Telemetry and control action dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from smart_pid_domain.enums import SignalStatus

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class TelemetryFrame:
    controller_id: int
    pv: float
    sp: float
    co: float
    integral_val: float
    timestamp: datetime
    status: SignalStatus


@dataclass(frozen=True)
class ControlAction:
    controller_id: int
    co: float
    integral_val: float
    timestamp: datetime
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/domain/test_models.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/models/
git commit -m "feat(domain): add shared models (Controller, PIDParams, TelemetryFrame, etc.)"
```

---

## Task 4: Migrate Events and Exceptions to smart_pid_domain

**Files:**
- Create: `packages/smart_pid_domain/src/smart_pid_domain/events.py`
- Create: `packages/smart_pid_domain/src/smart_pid_domain/exceptions.py`
- Create: `tests/domain/test_events.py`

- [ ] **Step 1: Write event tests**

Create `tests/domain/test_events.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from smart_pid_domain.enums import ConnectionState, SignalStatus
from smart_pid_domain.events import (
    ControlActionComputed,
    SystemStateChanged,
    TelemetryReceived,
)
from smart_pid_domain.models.telemetry import TelemetryFrame


class TestTelemetryReceived:
    def test_auto_generates_event_id(self) -> None:
        now = datetime.now(tz=timezone.utc)
        frame = TelemetryFrame(
            controller_id=1, pv=50.0, sp=50.0, co=25.0,
            integral_val=1.0, timestamp=now, status=SignalStatus.GOOD,
        )
        event = TelemetryReceived(controller_id=1, frame=frame)
        assert isinstance(event.event_id, UUID)

    def test_is_frozen(self) -> None:
        now = datetime.now(tz=timezone.utc)
        frame = TelemetryFrame(
            controller_id=1, pv=50.0, sp=50.0, co=25.0,
            integral_val=1.0, timestamp=now, status=SignalStatus.GOOD,
        )
        event = TelemetryReceived(controller_id=1, frame=frame)
        import pytest
        with pytest.raises(AttributeError):
            event.controller_id = 2  # type: ignore[misc]


class TestControlActionComputed:
    def test_construction(self) -> None:
        now = datetime.now(tz=timezone.utc)
        event = ControlActionComputed(
            controller_id=1, co=45.0, integral_val=1.5,
            delta_cv=0.5, timestamp=now,
        )
        assert event.delta_cv == 0.5


class TestSystemStateChanged:
    def test_construction(self) -> None:
        event = SystemStateChanged(
            new_state=ConnectionState.RECONNECTING,
            reason="Network timeout",
        )
        assert event.new_state == ConnectionState.RECONNECTING
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/domain/test_events.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_domain.events'`

- [ ] **Step 3: Create events.py**

Create `packages/smart_pid_domain/src/smart_pid_domain/events.py`:

```python
"""Frozen domain events published on the ZeroMQ event bus."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from smart_pid_domain.enums import ConnectionState

if TYPE_CHECKING:
    from datetime import datetime

    from smart_pid_domain.models.telemetry import TelemetryFrame


@dataclass(frozen=True)
class TelemetryReceived:
    controller_id: int
    frame: TelemetryFrame
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ControlActionComputed:
    controller_id: int
    co: float
    integral_val: float
    delta_cv: float
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class SystemStateChanged:
    new_state: ConnectionState
    reason: str
    event_id: UUID = field(default_factory=uuid4)
```

- [ ] **Step 4: Create exceptions.py**

Create `packages/smart_pid_domain/src/smart_pid_domain/exceptions.py`:

```python
"""Typed exception hierarchy for the Smart PID platform."""

from __future__ import annotations


class SmartPIDError(Exception):
    """Base exception for all Smart PID errors."""


# --- Domain errors ---

class DomainError(SmartPIDError):
    pass


class PIDComputationError(DomainError):
    pass


class InvalidModeTransition(DomainError):
    def __init__(self, current: str, target: str, reason: str) -> None:
        self.current = current
        self.target = target
        self.reason = reason
        super().__init__(f"Cannot transition from {current} to {target}: {reason}")


class AIInferenceError(DomainError):
    pass


class AlarmConfigError(DomainError):
    pass


# --- Infrastructure errors ---

class InfrastructureError(SmartPIDError):
    pass


class OPCUAConnectionError(InfrastructureError):
    pass


class OPCUAReadError(InfrastructureError):
    pass


class OPCUAWriteError(InfrastructureError):
    pass


class DatabaseError(InfrastructureError):
    pass


class ExportError(InfrastructureError):
    pass


# --- Communication errors (network between HMI and Backend) ---

class CommunicationError(SmartPIDError):
    pass


class APIConnectionError(CommunicationError):
    pass


class APIAuthError(CommunicationError):
    pass


class APITimeoutError(CommunicationError):
    pass


class TelemetryStreamError(CommunicationError):
    pass


# --- Project errors ---

class ProjectError(SmartPIDError):
    pass


class ProjectNotFoundError(ProjectError):
    pass


class ProjectCorruptedError(ProjectError):
    pass


# --- Auth errors ---

class AuthenticationError(SmartPIDError):
    pass


class AuthorizationError(SmartPIDError):
    pass
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/domain/ -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/events.py packages/smart_pid_domain/src/smart_pid_domain/exceptions.py tests/domain/test_events.py
git commit -m "feat(domain): add shared events and exception hierarchy"
```

---

## Task 5: Migrate PID Engine and Mode Manager to smart_pid_core

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/__init__.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/services/__init__.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/services/pid_engine.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/services/pid_mode_manager.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/ports/__init__.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/ports/inbound.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/ports/outbound.py`
- Create: `tests/core/__init__.py`, `tests/core/unit/__init__.py`
- Create: `tests/core/unit/test_pid_engine.py`
- Create: `tests/core/unit/test_pid_mode_manager.py`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p packages/smart_pid_core/src/smart_pid_core/domain/services
mkdir -p packages/smart_pid_core/src/smart_pid_core/domain/ports
mkdir -p tests/core/unit
mkdir -p tests/core/integration
mkdir -p tests/hmi
```

Create empty `__init__.py` files:
- `packages/smart_pid_core/src/smart_pid_core/domain/__init__.py`
- `packages/smart_pid_core/src/smart_pid_core/domain/services/__init__.py`
- `packages/smart_pid_core/src/smart_pid_core/domain/ports/__init__.py`
- `tests/core/__init__.py`
- `tests/core/unit/__init__.py`
- `tests/core/integration/__init__.py`
- `tests/hmi/__init__.py`

- [ ] **Step 2: Migrate pid_engine.py**

Create `packages/smart_pid_core/src/smart_pid_core/domain/services/pid_engine.py`:

Copy the content from `src/smart_pid/domain/services/pid_engine.py` and update imports:

```python
"""PID engine — velocity form with anti-windup and bumpless transfer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_domain.models.controller import PIDParams


@dataclass
class PIDState:
    cv: float = 0.0
    error_prev: float = 0.0
    pv_prev: float = 0.0
    pv_prev2: float = 0.0
    sp_working: float = 0.0
    derivative_filtered: float = 0.0
    is_saturated: bool = False


@dataclass(frozen=True)
class PIDResult:
    cv: float
    delta_cv: float
    error: float
    new_state: PIDState


class PIDEngine:
    """Stateless PID calculator — all mutable state lives in PIDState."""

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
        error = sp - pv
        if direct_acting:
            error = -error

        # Proportional (velocity form)
        delta_p = params.gain * (error - state.error_prev)

        # Integral (velocity form) — paused if saturated and error would worsen
        delta_i = 0.0
        winding_up = (state.is_saturated and error * state.cv > 0)
        in_deadband = abs(error) <= params.deadband
        if not winding_up and not in_deadband and params.reset > 0:
            delta_i = params.gain * (dt / params.reset) * error

        # Derivative on PV (filtered)
        d_pv = pv - 2 * state.pv_prev + state.pv_prev2
        raw_derivative = -params.gain * params.rate * d_pv / dt if dt > 0 else 0.0
        alpha = params.alpha
        derivative_filtered = alpha * raw_derivative + (1 - alpha) * state.derivative_filtered

        delta_cv = delta_p + delta_i + derivative_filtered

        new_cv = state.cv + delta_cv
        lo, hi = out_limits
        clamped_cv = max(lo, min(hi, new_cv))
        is_saturated = clamped_cv != new_cv

        new_state = PIDState(
            cv=clamped_cv,
            error_prev=error,
            pv_prev=pv,
            pv_prev2=state.pv_prev,
            sp_working=sp,
            derivative_filtered=derivative_filtered,
            is_saturated=is_saturated,
        )

        return PIDResult(
            cv=clamped_cv,
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
        return PIDState(
            cv=current_co,
            error_prev=0.0,
            pv_prev=current_pv,
            pv_prev2=current_pv,
            sp_working=current_pv,
            derivative_filtered=0.0,
            is_saturated=state.is_saturated,
        )

    def apply_sp_ramp(
        self,
        sp_target: float,
        sp_current: float,
        rate_up: float,
        rate_dn: float,
        dt: float,
    ) -> float:
        diff = sp_target - sp_current
        if diff > 0 and rate_up > 0:
            max_step = rate_up * dt
            return sp_current + min(diff, max_step)
        if diff < 0 and rate_dn > 0:
            max_step = rate_dn * dt
            return sp_current - min(-diff, max_step)
        return sp_target
```

- [ ] **Step 3: Migrate pid_mode_manager.py**

Create `packages/smart_pid_core/src/smart_pid_core/domain/services/pid_mode_manager.py`:

```python
"""PID mode manager — 8-mode state machine with forced transitions."""

from __future__ import annotations

from dataclasses import dataclass

from smart_pid_domain.enums import ControllerMode, SignalStatus

_BUMPLESS_REQUIRED_TARGETS = {ControllerMode.AUTO, ControllerMode.CAS, ControllerMode.RCAS}


@dataclass
class BlockStatus:
    pv_status: SignalStatus = SignalStatus.GOOD
    tracking_active: bool = False
    shed_timeout_expired: bool = False
    simulate_active: bool = False


@dataclass(frozen=True)
class ModeTransition:
    accepted: bool
    new_mode: ControllerMode
    requires_bumpless: bool = False
    rejection_reason: str = ""


class ModeManager:
    """Validates and executes mode transitions for a PID block."""

    def request_mode(
        self,
        current: ControllerMode,
        target: ControllerMode,
        permitted: set[ControllerMode],
        block_status: BlockStatus,
    ) -> ModeTransition:
        if target not in permitted:
            return ModeTransition(
                accepted=False,
                new_mode=current,
                rejection_reason=f"Mode {target} is not in permitted modes",
            )

        requires_bumpless = target in _BUMPLESS_REQUIRED_TARGETS and current not in _BUMPLESS_REQUIRED_TARGETS

        return ModeTransition(
            accepted=True,
            new_mode=target,
            requires_bumpless=requires_bumpless,
        )

    def evaluate_forced_transitions(
        self,
        current: ControllerMode,
        block_status: BlockStatus,
        shed_mode: ControllerMode = ControllerMode.MAN,
    ) -> ControllerMode | None:
        if block_status.pv_status == SignalStatus.BAD:
            return ControllerMode.MAN

        if block_status.tracking_active:
            return ControllerMode.LO

        if block_status.shed_timeout_expired:
            return shed_mode

        return None
```

- [ ] **Step 4: Migrate ports**

Create `packages/smart_pid_core/src/smart_pid_core/domain/ports/inbound.py`:

```python
"""Inbound port interfaces — data flows into the domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from smart_pid_domain.models.telemetry import TelemetryFrame


class TelemetrySource(Protocol):
    async def read_telemetry(self, controller_id: int) -> TelemetryFrame: ...
    async def connect(self, endpoint: str) -> None: ...
    async def disconnect(self) -> None: ...


class TagBrowser(Protocol):
    async def browse_children(self, node_id: str) -> list[dict[str, str]]: ...
    async def search(self, query: str) -> list[dict[str, str]]: ...
```

Create `packages/smart_pid_core/src/smart_pid_core/domain/ports/outbound.py`:

```python
"""Outbound port interfaces — domain pushes data to infrastructure."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

    from smart_pid_domain.models.controller import Controller
    from smart_pid_domain.models.telemetry import TelemetryFrame


class ControlWriter(Protocol):
    async def write_output(self, controller_id: int, co: float) -> None: ...
    async def write_parameter(self, controller_id: int, param: str, value: float) -> None: ...


class ControllerRepository(Protocol):
    async def get(self, controller_id: int) -> Controller: ...
    async def list_all(self) -> list[Controller]: ...
    async def save(self, controller: Controller) -> None: ...
    async def delete(self, controller_id: int) -> None: ...


class HistorianWriter(Protocol):
    async def write_batch(self, frames: list[TelemetryFrame]) -> None: ...
    async def query(
        self, controller_id: int, start: datetime, end: datetime
    ) -> list[TelemetryFrame]: ...
    async def cleanup_older_than(self, days: int) -> int: ...


class ProjectStore(Protocol):
    async def create(self, path: Path) -> None: ...
    async def open(self, path: Path) -> None: ...
    async def close(self) -> None: ...
```

- [ ] **Step 5: Migrate unit tests with updated imports**

Create `tests/core/unit/test_pid_engine.py`:

```python
from __future__ import annotations

import pytest

from smart_pid_domain.models.controller import PIDParams
from smart_pid_core.domain.services.pid_engine import PIDEngine, PIDState


class TestPIDCompute:
    def setup_method(self) -> None:
        self.engine = PIDEngine()
        self.params = PIDParams(gain=1.5, reset=10.0, rate=2.0)
        self.limits = (0.0, 100.0)

    def test_zero_error_produces_zero_delta(self) -> None:
        state = PIDState(pv_prev=50.0, pv_prev2=50.0)
        result = self.engine.compute(self.params, state, pv=50.0, sp=50.0, dt=1.0, out_limits=self.limits)
        assert abs(result.delta_cv) < 1e-9

    def test_proportional_action_on_error_step(self) -> None:
        state = PIDState(pv_prev=50.0, pv_prev2=50.0, error_prev=0.0)
        result = self.engine.compute(self.params, state, pv=50.0, sp=60.0, dt=1.0, out_limits=self.limits)
        assert result.error == pytest.approx(10.0)
        assert result.delta_cv > 0

    def test_integral_action_accumulates(self) -> None:
        state = PIDState(pv_prev=50.0, pv_prev2=50.0, error_prev=10.0)
        result = self.engine.compute(self.params, state, pv=50.0, sp=60.0, dt=1.0, out_limits=self.limits)
        expected_integral = self.params.gain * (1.0 / self.params.reset) * 10.0
        assert result.delta_cv >= expected_integral

    def test_derivative_action_on_pv_change(self) -> None:
        state = PIDState(pv_prev=50.0, pv_prev2=48.0, error_prev=10.0)
        result = self.engine.compute(self.params, state, pv=52.0, sp=60.0, dt=1.0, out_limits=self.limits)
        assert result.cv != 0.0

    def test_output_clamped_to_limits(self) -> None:
        state = PIDState(cv=99.0, pv_prev=50.0, pv_prev2=50.0, error_prev=0.0)
        result = self.engine.compute(self.params, state, pv=10.0, sp=100.0, dt=1.0, out_limits=self.limits)
        assert result.cv <= 100.0

    def test_direct_acting_reverses_error(self) -> None:
        state = PIDState(pv_prev=50.0, pv_prev2=50.0, error_prev=0.0)
        result = self.engine.compute(self.params, state, pv=50.0, sp=60.0, dt=1.0, out_limits=self.limits, direct_acting=True)
        assert result.error == pytest.approx(-10.0)


class TestAntiWindup:
    def setup_method(self) -> None:
        self.engine = PIDEngine()
        self.params = PIDParams(gain=1.5, reset=10.0, rate=0.0)
        self.limits = (0.0, 100.0)

    def test_integral_paused_when_saturated_high(self) -> None:
        state = PIDState(cv=100.0, pv_prev=50.0, pv_prev2=50.0, error_prev=50.0, is_saturated=True)
        result = self.engine.compute(self.params, state, pv=50.0, sp=100.0, dt=1.0, out_limits=self.limits)
        assert result.cv == 100.0

    def test_integral_resumes_when_error_reverses(self) -> None:
        state = PIDState(cv=100.0, pv_prev=50.0, pv_prev2=50.0, error_prev=50.0, is_saturated=True)
        result = self.engine.compute(self.params, state, pv=110.0, sp=100.0, dt=1.0, out_limits=self.limits)
        assert result.new_state.is_saturated is False or result.cv < 100.0


class TestBumplessTransfer:
    def test_bumpless_sets_cv_to_current_co(self) -> None:
        engine = PIDEngine()
        params = PIDParams()
        state = PIDState(cv=30.0, error_prev=5.0)
        new_state = engine.bumpless_transfer(state, current_pv=50.0, current_co=45.0, params=params)
        assert new_state.cv == 45.0
        assert new_state.pv_prev == 50.0
        assert new_state.error_prev == 0.0


class TestSPRamp:
    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_ramp_up_limits_sp_increase(self) -> None:
        result = self.engine.apply_sp_ramp(sp_target=100.0, sp_current=50.0, rate_up=10.0, rate_dn=10.0, dt=1.0)
        assert result == pytest.approx(60.0)

    def test_ramp_down_limits_sp_decrease(self) -> None:
        result = self.engine.apply_sp_ramp(sp_target=30.0, sp_current=50.0, rate_up=10.0, rate_dn=5.0, dt=1.0)
        assert result == pytest.approx(45.0)

    def test_zero_rate_means_immediate(self) -> None:
        result = self.engine.apply_sp_ramp(sp_target=100.0, sp_current=50.0, rate_up=0.0, rate_dn=0.0, dt=1.0)
        assert result == pytest.approx(100.0)


class TestDeadband:
    def test_integral_stops_within_deadband(self) -> None:
        engine = PIDEngine()
        params = PIDParams(gain=1.5, reset=10.0, rate=0.0, deadband=5.0)
        state = PIDState(cv=50.0, pv_prev=50.0, pv_prev2=50.0, error_prev=2.0)
        result = engine.compute(params, state, pv=48.0, sp=50.0, dt=1.0, out_limits=(0.0, 100.0))
        # Error is 2.0, within deadband of 5.0 — integral should be zero
        # Only proportional component expected
        proportional = params.gain * (2.0 - 2.0)  # error - error_prev = 0
        assert abs(result.delta_cv) < 1e-6
```

Create `tests/core/unit/test_pid_mode_manager.py`:

```python
from __future__ import annotations

from smart_pid_domain.enums import ControllerMode, SignalStatus
from smart_pid_core.domain.services.pid_mode_manager import (
    BlockStatus,
    ModeManager,
)


class TestModeTransitions:
    def setup_method(self) -> None:
        self.manager = ModeManager()
        self.permitted = {
            ControllerMode.OOS, ControllerMode.MAN, ControllerMode.AUTO,
            ControllerMode.CAS, ControllerMode.LO,
        }
        self.status = BlockStatus()

    def test_man_to_auto_allowed(self) -> None:
        result = self.manager.request_mode(ControllerMode.MAN, ControllerMode.AUTO, self.permitted, self.status)
        assert result.accepted is True
        assert result.new_mode == ControllerMode.AUTO
        assert result.requires_bumpless is True

    def test_auto_to_man_allowed(self) -> None:
        result = self.manager.request_mode(ControllerMode.AUTO, ControllerMode.MAN, self.permitted, self.status)
        assert result.accepted is True
        assert result.new_mode == ControllerMode.MAN
        assert result.requires_bumpless is False

    def test_transition_to_unpermitted_mode_rejected(self) -> None:
        result = self.manager.request_mode(ControllerMode.MAN, ControllerMode.RCAS, self.permitted, self.status)
        assert result.accepted is False

    def test_auto_to_cas_allowed(self) -> None:
        result = self.manager.request_mode(ControllerMode.AUTO, ControllerMode.CAS, self.permitted, self.status)
        assert result.accepted is True
        assert result.requires_bumpless is False  # AUTO is already in closed-loop

    def test_oos_to_man_allowed(self) -> None:
        result = self.manager.request_mode(ControllerMode.OOS, ControllerMode.MAN, self.permitted, self.status)
        assert result.accepted is True


class TestForcedTransitions:
    def setup_method(self) -> None:
        self.manager = ModeManager()

    def test_bad_pv_forces_manual(self) -> None:
        status = BlockStatus(pv_status=SignalStatus.BAD)
        result = self.manager.evaluate_forced_transitions(ControllerMode.AUTO, status)
        assert result == ControllerMode.MAN

    def test_tracking_active_forces_lo(self) -> None:
        status = BlockStatus(tracking_active=True)
        result = self.manager.evaluate_forced_transitions(ControllerMode.AUTO, status)
        assert result == ControllerMode.LO

    def test_good_pv_no_force(self) -> None:
        status = BlockStatus()
        result = self.manager.evaluate_forced_transitions(ControllerMode.AUTO, status)
        assert result is None

    def test_shed_timeout_forces_configured_mode(self) -> None:
        status = BlockStatus(shed_timeout_expired=True)
        result = self.manager.evaluate_forced_transitions(
            ControllerMode.AUTO, status, shed_mode=ControllerMode.MAN,
        )
        assert result == ControllerMode.MAN
```

- [ ] **Step 6: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: All tests PASS. Old tests in `tests/unit/` and `tests/integration/` may fail due to old imports — that is expected and we will remove them in a later step.

```bash
uv run pytest tests/domain/ tests/core/unit/ -v
```

Expected: All new tests PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/ tests/core/
git commit -m "feat(core): migrate PID engine, mode manager, and ports to smart_pid_core"
```

---

## Task 6: Remove Old Package and Update Test Structure

**Files:**
- Delete: `src/smart_pid/` (entire directory)
- Delete: `tests/unit/`, `tests/integration/` (old test dirs)
- Modify: `tests/conftest.py`

- [ ] **Step 1: Remove old source and test directories**

```bash
rm -rf src/
rm -rf tests/unit/
rm -rf tests/integration/
rm -f tests/__init__.py
```

- [ ] **Step 2: Update root conftest.py**

Rewrite `tests/conftest.py`:

```python
"""Root test configuration for the Smart PID platform."""

from __future__ import annotations

import pytest

from smart_pid_domain.models.controller import PIDParams


@pytest.fixture
def sample_pid_params() -> PIDParams:
    return PIDParams(gain=1.5, reset=10.0, rate=2.0, alpha=0.125, deadband=0.0)
```

- [ ] **Step 3: Run all tests to ensure nothing is broken**

```bash
uv run pytest tests/ -v
```

Expected: All tests in `tests/domain/` and `tests/core/unit/` PASS. No stale test files remain.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove old src/smart_pid package, consolidate test structure"
```

---

## Task 7: Backend Config (pydantic-settings)

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/config.py`
- Create: `tests/core/unit/test_config.py`

- [ ] **Step 1: Write config test**

Create `tests/core/unit/test_config.py`:

```python
from __future__ import annotations

from smart_pid_core.config import CoreSettings


class TestCoreSettings:
    def test_defaults(self) -> None:
        settings = CoreSettings(jwt_secret="test-secret")
        assert settings.api_port == 8000
        assert settings.api_host == "0.0.0.0"
        assert settings.zmq_internal_url == "inproc://bus"
        assert settings.zmq_publish_port == 5555
        assert settings.db_flush_interval_s == 5.0
        assert settings.db_retention_process_days == 7
        assert settings.db_retention_alarm_days == 30
        assert settings.simulator_enabled is False
        assert settings.log_level == "INFO"

    def test_jwt_secret_required(self) -> None:
        import pytest
        with pytest.raises(Exception):
            CoreSettings()  # type: ignore[call-arg]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/core/unit/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_core.config'`

- [ ] **Step 3: Implement config.py**

Create `packages/smart_pid_core/src/smart_pid_core/config.py`:

```python
"""Backend daemon settings loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SPID_")

    # OPC-UA
    opcua_endpoint: str = "opc.tcp://localhost:4840"
    opcua_timeout_s: int = 5

    # ZeroMQ
    zmq_internal_url: str = "inproc://bus"
    zmq_publish_port: int = 5555

    # FastAPI
    api_port: int = 8000
    api_host: str = "0.0.0.0"

    # JWT
    jwt_secret: str
    jwt_expiry_hours: int = 8

    # Database
    db_path: Path = Path("./project.spid")
    db_flush_interval_s: float = 5.0
    db_retention_process_days: int = 7
    db_retention_alarm_days: int = 30
    db_batch_size: int = 500

    # Simulator
    simulator_enabled: bool = False
    simulator_port: int = 4841

    # Logging
    log_level: str = "INFO"
```

- [ ] **Step 4: Run test**

```bash
uv run pytest tests/core/unit/test_config.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/config.py tests/core/unit/test_config.py
git commit -m "feat(core): add backend settings via pydantic-settings"
```

---

## Task 8: ZeroMQ Event Bus (inproc:// XPUB/XSUB)

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/application/__init__.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/application/event_bus.py`
- Create: `tests/core/integration/test_event_bus.py`

- [ ] **Step 1: Create application directory**

```bash
mkdir -p packages/smart_pid_core/src/smart_pid_core/application/workers
```

Create empty `__init__.py`:
- `packages/smart_pid_core/src/smart_pid_core/application/__init__.py`
- `packages/smart_pid_core/src/smart_pid_core/application/workers/__init__.py`

- [ ] **Step 2: Write event bus tests**

Create `tests/core/integration/test_event_bus.py`:

```python
from __future__ import annotations

import threading
import time

import pytest

from smart_pid_core.application.event_bus import EventBus


class TestEventBus:
    def test_publish_and_receive(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"TEST")

            time.sleep(0.05)  # Let subscriptions propagate

            pub.send(b"TEST.hello", b"world")
            msg = sub.recv(timeout_ms=1000)

            assert msg is not None
            topic, payload = msg
            assert topic == b"TEST.hello"
            assert payload == b"world"
        finally:
            bus.stop()

    def test_subscriber_filters_by_prefix(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"TELEM")

            time.sleep(0.05)

            pub.send(b"ALARM.fire", b"alarm_data")
            pub.send(b"TELEM.1", b"telem_data")

            msg = sub.recv(timeout_ms=1000)
            assert msg is not None
            assert msg[0] == b"TELEM.1"

            # Should not receive ALARM topic
            msg2 = sub.recv(timeout_ms=100)
            assert msg2 is None
        finally:
            bus.stop()

    def test_multiple_subscribers(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            pub = bus.create_publisher()
            sub1 = bus.create_subscriber(b"DATA")
            sub2 = bus.create_subscriber(b"DATA")

            time.sleep(0.05)

            pub.send(b"DATA.x", b"payload")

            msg1 = sub1.recv(timeout_ms=1000)
            msg2 = sub2.recv(timeout_ms=1000)
            assert msg1 is not None
            assert msg2 is not None
            assert msg1[1] == msg2[1] == b"payload"
        finally:
            bus.stop()

    def test_noblock_returns_none_when_empty(self) -> None:
        bus = EventBus()
        bus.start()
        try:
            sub = bus.create_subscriber(b"EMPTY")
            time.sleep(0.05)
            msg = sub.recv(timeout_ms=50)
            assert msg is None
        finally:
            bus.stop()

    def test_cross_thread_communication(self) -> None:
        bus = EventBus()
        bus.start()
        received: list[bytes] = []
        try:
            sub = bus.create_subscriber(b"THREAD")
            time.sleep(0.05)

            def publisher_thread() -> None:
                pub = bus.create_publisher()
                time.sleep(0.02)
                pub.send(b"THREAD.test", b"from_thread")

            t = threading.Thread(target=publisher_thread)
            t.start()

            msg = sub.recv(timeout_ms=2000)
            assert msg is not None
            assert msg[1] == b"from_thread"

            t.join(timeout=2.0)
        finally:
            bus.stop()

    def test_msgpack_round_trip(self) -> None:
        import msgpack

        bus = EventBus()
        bus.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(b"MP")

            time.sleep(0.05)

            data = {"pv": 50.5, "sp": 50.0, "co": 25.0}
            pub.send(b"MP.telem", msgpack.packb(data))

            msg = sub.recv(timeout_ms=1000)
            assert msg is not None
            decoded = msgpack.unpackb(msg[1])
            assert decoded["pv"] == 50.5
        finally:
            bus.stop()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/core/integration/test_event_bus.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_core.application.event_bus'`

- [ ] **Step 4: Implement event_bus.py**

Create `packages/smart_pid_core/src/smart_pid_core/application/event_bus.py`:

```python
"""ZeroMQ inproc:// event bus with XPUB/XSUB proxy for many-to-many messaging."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import zmq

if TYPE_CHECKING:
    pass


class BusPublisher:
    """Wrapper around a ZMQ PUB socket connected to the bus."""

    def __init__(self, socket: zmq.Socket[bytes]) -> None:
        self._socket = socket

    def send(self, topic: bytes, payload: bytes) -> None:
        self._socket.send_multipart([topic, payload])


class BusSubscriber:
    """Wrapper around a ZMQ SUB socket connected to the bus."""

    def __init__(self, socket: zmq.Socket[bytes]) -> None:
        self._socket = socket

    def recv(self, timeout_ms: int = 0) -> tuple[bytes, bytes] | None:
        if self._socket.poll(timeout=timeout_ms):
            parts = self._socket.recv_multipart()
            if len(parts) == 2:
                return (parts[0], parts[1])
        return None


class EventBus:
    """XPUB/XSUB proxy running in a daemon thread.

    Publishers connect to the XSUB frontend.
    Subscribers connect to the XPUB backend.
    The proxy relays messages between them.
    """

    def __init__(self, url_prefix: str = "inproc://smartpid") -> None:
        self._ctx = zmq.Context()
        self._url_frontend = f"{url_prefix}_xsub"
        self._url_backend = f"{url_prefix}_xpub"
        self._proxy_thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return

        self._xsub = self._ctx.socket(zmq.XSUB)
        self._xsub.bind(self._url_frontend)

        self._xpub = self._ctx.socket(zmq.XPUB)
        self._xpub.bind(self._url_backend)

        self._running = True
        self._proxy_thread = threading.Thread(
            target=self._run_proxy, daemon=True, name="zmq-proxy",
        )
        self._proxy_thread.start()

    def _run_proxy(self) -> None:
        try:
            zmq.proxy(self._xsub, self._xpub)
        except zmq.ContextTerminated:
            pass

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._ctx.term()

    def create_publisher(self) -> BusPublisher:
        socket = self._ctx.socket(zmq.PUB)
        socket.connect(self._url_frontend)
        return BusPublisher(socket)

    def create_subscriber(self, topic_prefix: bytes) -> BusSubscriber:
        socket = self._ctx.socket(zmq.SUB)
        socket.connect(self._url_backend)
        socket.subscribe(topic_prefix)
        return BusSubscriber(socket)
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/core/integration/test_event_bus.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/ tests/core/integration/test_event_bus.py
git commit -m "feat(core): implement ZeroMQ inproc event bus with XPUB/XSUB proxy"
```

---

## Task 9: SQLite Repository (DDL + Controller CRUD)

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/__init__.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/__init__.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py`
- Create: `tests/core/integration/test_sqlite_repo.py`

- [ ] **Step 1: Create adapter directory**

```bash
mkdir -p packages/smart_pid_core/src/smart_pid_core/adapters/outbound
```

Create empty `__init__.py`:
- `packages/smart_pid_core/src/smart_pid_core/adapters/__init__.py`
- `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/__init__.py`

- [ ] **Step 2: Write SQLite repository tests**

Create `tests/core/integration/test_sqlite_repo.py`:

```python
from __future__ import annotations

import pytest

from smart_pid_domain.models.controller import Controller
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository


@pytest.fixture
async def repo(tmp_path) -> SQLiteRepository:
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    return repo


class TestSQLiteRepository:
    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, repo: SQLiteRepository) -> None:
        tables = await repo._get_table_names()
        assert "Controladores" in tables
        assert "Log_Processo" in tables
        assert "Log_Alarmes" in tables
        assert "Log_Sintonia_IA" in tables
        assert "Log_Auditoria" in tables
        assert "Usuarios" in tables
        assert "Configuracao_Alarmes" in tables

    @pytest.mark.asyncio
    async def test_save_and_get_controller(self, repo: SQLiteRepository) -> None:
        ctrl = Controller(id=0, name="TIC-101", description="Temperature loop")
        saved = await repo.save(ctrl)
        assert saved.id > 0

        loaded = await repo.get(saved.id)
        assert loaded.name == "TIC-101"
        assert loaded.description == "Temperature loop"

    @pytest.mark.asyncio
    async def test_list_all_controllers(self, repo: SQLiteRepository) -> None:
        await repo.save(Controller(id=0, name="TIC-101"))
        await repo.save(Controller(id=0, name="FIC-201"))
        controllers = await repo.list_all()
        assert len(controllers) == 2
        names = {c.name for c in controllers}
        assert names == {"TIC-101", "FIC-201"}

    @pytest.mark.asyncio
    async def test_update_controller(self, repo: SQLiteRepository) -> None:
        ctrl = Controller(id=0, name="TIC-101", description="Old")
        saved = await repo.save(ctrl)

        saved_copy = Controller(
            id=saved.id, name="TIC-101", description="New",
            scan_rate_ms=500,
        )
        await repo.save(saved_copy)

        loaded = await repo.get(saved.id)
        assert loaded.description == "New"
        assert loaded.scan_rate_ms == 500

    @pytest.mark.asyncio
    async def test_delete_controller(self, repo: SQLiteRepository) -> None:
        ctrl = Controller(id=0, name="TIC-101")
        saved = await repo.save(ctrl)
        await repo.delete(saved.id)

        with pytest.raises(KeyError):
            await repo.get(saved.id)

    @pytest.mark.asyncio
    async def test_get_nonexistent_raises(self, repo: SQLiteRepository) -> None:
        with pytest.raises(KeyError):
            await repo.get(9999)

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, repo: SQLiteRepository) -> None:
        mode = await repo._get_journal_mode()
        assert mode == "wal"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/core/integration/test_sqlite_repo.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_core.adapters'`

- [ ] **Step 4: Implement sqlite_repo.py**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py`:

```python
"""SQLite repository — controller CRUD and schema management."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

from smart_pid_domain.enums import (
    AIEngine,
    ControlObjective,
    ControllerMode,
    ExecutionMode,
    IntegralType,
    PIDStructure,
    ProcessSpeed,
)
from smart_pid_domain.models.controller import (
    AIConfig,
    Controller,
    PIDParams,
    ScaleConfig,
)

if TYPE_CHECKING:
    pass

_DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS Usuarios (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    password_hash TEXT,
    role TEXT CHECK(role IN ('ADMIN','SUPERVISOR','OPERATOR'))
);

CREATE TABLE IF NOT EXISTS Controladores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT UNIQUE NOT NULL,
    descricao TEXT DEFAULT '',
    modo_execucao TEXT CHECK(modo_execucao IN ('SUPERVISORY', 'DDC')) DEFAULT 'DDC',
    scan_rate_ms INTEGER DEFAULT 1000,
    node_id_pv TEXT DEFAULT '',
    node_id_sp TEXT DEFAULT '',
    node_id_co TEXT DEFAULT '',
    node_id_integral TEXT DEFAULT '',
    is_scaled BOOLEAN DEFAULT 0,
    pv_min REAL DEFAULT 0.0,
    pv_max REAL DEFAULT 100.0,
    co_min REAL DEFAULT 0.0,
    co_max REAL DEFAULT 100.0,
    pid_structure TEXT CHECK(pid_structure IN ('ISA', 'PARALLEL', 'SERIES')) DEFAULT 'ISA',
    integral_type TEXT CHECK(integral_type IN ('GAIN_KI', 'TIME_TI')) DEFAULT 'TIME_TI',
    kp_manual REAL DEFAULT 1.0,
    kd_manual REAL DEFAULT 0.0,
    ki_inicial REAL DEFAULT 10.0,
    ai_engine TEXT DEFAULT 'NONE' CHECK(ai_engine IN ('NONE', 'FUZZY', 'RL')),
    ai_thread_status TEXT DEFAULT 'STOPPED',
    objetivo_controle TEXT DEFAULT 'DISTURBANCE_REJECTION',
    process_speed TEXT CHECK(process_speed IN ('SLOW', 'MEDIUM', 'FAST')) DEFAULT 'MEDIUM',
    tempo_morto_l REAL DEFAULT 1.0,
    ai_limit_min REAL DEFAULT 0.1,
    ai_limit_max REAL DEFAULT 100.0
);

CREATE TABLE IF NOT EXISTS Configuracao_Alarmes (
    controlador_id INTEGER,
    deadband_percent REAL,
    hihi_val REAL,
    hihi_prioridade TEXT,
    hi_val REAL,
    hi_prioridade TEXT,
    lo_val REAL,
    lo_prioridade TEXT,
    lolo_val REAL,
    lolo_prioridade TEXT,
    FOREIGN KEY(controlador_id) REFERENCES Controladores(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Log_Processo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    controlador_id INTEGER,
    pv REAL,
    sp REAL,
    co REAL,
    integral_val REAL,
    FOREIGN KEY(controlador_id) REFERENCES Controladores(id)
);

CREATE INDEX IF NOT EXISTS idx_log_processo_time
    ON Log_Processo(timestamp, controlador_id);

CREATE TABLE IF NOT EXISTS Log_Sintonia_IA (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    controlador_id INTEGER,
    valor_anterior REAL,
    valor_novo REAL,
    justificativa TEXT
);

CREATE TABLE IF NOT EXISTS Log_Auditoria (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    usuario_id INTEGER,
    acao TEXT,
    valor_antigo TEXT,
    valor_novo TEXT
);

CREATE TABLE IF NOT EXISTS Log_Alarmes (
    id INTEGER PRIMARY KEY,
    controlador_id INTEGER,
    tipo TEXT,
    prioridade TEXT,
    timestamp_in DATETIME,
    timestamp_out DATETIME,
    timestamp_ack DATETIME,
    usuario_ack_id INTEGER
);
"""


class SQLiteRepository:
    """SQLite-backed controller repository with full DDL management."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_DDL)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            msg = "Repository not initialized. Call initialize() first."
            raise RuntimeError(msg)
        return self._db

    async def save(self, controller: Controller) -> Controller:
        if controller.id == 0:
            return await self._insert(controller)
        await self._update(controller)
        return controller

    async def _insert(self, ctrl: Controller) -> Controller:
        cursor = await self.db.execute(
            """INSERT INTO Controladores (
                nome, descricao, modo_execucao, scan_rate_ms,
                node_id_pv, node_id_sp, node_id_co, node_id_integral,
                pv_min, pv_max, co_min, co_max,
                pid_structure, integral_type, kp_manual, kd_manual, ki_inicial,
                ai_engine, objetivo_controle, process_speed,
                tempo_morto_l, ai_limit_min, ai_limit_max
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ctrl.name, ctrl.description, ctrl.execution_mode.value, ctrl.scan_rate_ms,
                ctrl.tag_bindings.node_id_pv, ctrl.tag_bindings.node_id_sp,
                ctrl.tag_bindings.node_id_co, ctrl.tag_bindings.node_id_integral,
                ctrl.pv_scale.eu_min, ctrl.pv_scale.eu_max,
                ctrl.out_scale.eu_min, ctrl.out_scale.eu_max,
                ctrl.pid_structure.value, ctrl.integral_type.value,
                ctrl.pid_params.gain, ctrl.pid_params.rate, ctrl.pid_params.reset,
                ctrl.ai_config.engine.value, ctrl.ai_config.objective.value,
                ctrl.ai_config.process_speed.value,
                ctrl.ai_config.dead_time_l, ctrl.ai_config.limit_min, ctrl.ai_config.limit_max,
            ),
        )
        await self.db.commit()
        new_id = cursor.lastrowid
        assert new_id is not None
        return Controller(
            id=new_id, name=ctrl.name, description=ctrl.description,
            execution_mode=ctrl.execution_mode, scan_rate_ms=ctrl.scan_rate_ms,
            pid_params=ctrl.pid_params, pid_structure=ctrl.pid_structure,
            integral_type=ctrl.integral_type, pv_scale=ctrl.pv_scale,
            out_scale=ctrl.out_scale, tag_bindings=ctrl.tag_bindings,
            control_opts=ctrl.control_opts, io_opts=ctrl.io_opts,
            ai_config=ctrl.ai_config,
        )

    async def _update(self, ctrl: Controller) -> None:
        await self.db.execute(
            """UPDATE Controladores SET
                nome=?, descricao=?, modo_execucao=?, scan_rate_ms=?,
                node_id_pv=?, node_id_sp=?, node_id_co=?, node_id_integral=?,
                pv_min=?, pv_max=?, co_min=?, co_max=?,
                pid_structure=?, integral_type=?, kp_manual=?, kd_manual=?, ki_inicial=?,
                ai_engine=?, objetivo_controle=?, process_speed=?,
                tempo_morto_l=?, ai_limit_min=?, ai_limit_max=?
            WHERE id=?""",
            (
                ctrl.name, ctrl.description, ctrl.execution_mode.value, ctrl.scan_rate_ms,
                ctrl.tag_bindings.node_id_pv, ctrl.tag_bindings.node_id_sp,
                ctrl.tag_bindings.node_id_co, ctrl.tag_bindings.node_id_integral,
                ctrl.pv_scale.eu_min, ctrl.pv_scale.eu_max,
                ctrl.out_scale.eu_min, ctrl.out_scale.eu_max,
                ctrl.pid_structure.value, ctrl.integral_type.value,
                ctrl.pid_params.gain, ctrl.pid_params.rate, ctrl.pid_params.reset,
                ctrl.ai_config.engine.value, ctrl.ai_config.objective.value,
                ctrl.ai_config.process_speed.value,
                ctrl.ai_config.dead_time_l, ctrl.ai_config.limit_min, ctrl.ai_config.limit_max,
                ctrl.id,
            ),
        )
        await self.db.commit()

    async def get(self, controller_id: int) -> Controller:
        cursor = await self.db.execute(
            "SELECT * FROM Controladores WHERE id=?", (controller_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            msg = f"Controller {controller_id} not found"
            raise KeyError(msg)
        return self._row_to_controller(row)

    async def list_all(self) -> list[Controller]:
        cursor = await self.db.execute("SELECT * FROM Controladores ORDER BY id")
        rows = await cursor.fetchall()
        return [self._row_to_controller(row) for row in rows]

    async def delete(self, controller_id: int) -> None:
        cursor = await self.db.execute(
            "DELETE FROM Controladores WHERE id=?", (controller_id,),
        )
        await self.db.commit()
        if cursor.rowcount == 0:
            msg = f"Controller {controller_id} not found"
            raise KeyError(msg)

    def _row_to_controller(self, row: aiosqlite.Row) -> Controller:
        return Controller(
            id=row["id"],
            name=row["nome"],
            description=row["descricao"] or "",
            execution_mode=ExecutionMode(row["modo_execucao"]),
            scan_rate_ms=row["scan_rate_ms"],
            pid_params=PIDParams(
                gain=row["kp_manual"],
                reset=row["ki_inicial"],
                rate=row["kd_manual"],
            ),
            pid_structure=PIDStructure(row["pid_structure"]),
            integral_type=IntegralType(row["integral_type"]),
            pv_scale=ScaleConfig(eu_min=row["pv_min"], eu_max=row["pv_max"]),
            out_scale=ScaleConfig(eu_min=row["co_min"], eu_max=row["co_max"]),
            ai_config=AIConfig(
                engine=AIEngine(row["ai_engine"]),
                objective=ControlObjective(row["objetivo_controle"]),
                process_speed=ProcessSpeed(row["process_speed"]),
                dead_time_l=row["tempo_morto_l"],
                limit_min=row["ai_limit_min"],
                limit_max=row["ai_limit_max"],
            ),
        )

    async def _get_table_names(self) -> list[str]:
        cursor = await self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [row["name"] for row in rows]

    async def _get_journal_mode(self) -> str:
        cursor = await self.db.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        return row[0] if row else ""
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/core/integration/test_sqlite_repo.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/ tests/core/integration/test_sqlite_repo.py
git commit -m "feat(core): implement SQLite repository with full DDL and controller CRUD"
```

---

## Task 10: SQLite Historian (Batch Insert + Query + Cleanup)

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/historian.py`
- Create: `tests/core/integration/test_historian.py`

- [ ] **Step 1: Write historian tests**

Create `tests/core/integration/test_historian.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from smart_pid_domain.enums import SignalStatus
from smart_pid_domain.models.telemetry import TelemetryFrame
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository


@pytest.fixture
async def historian(tmp_path) -> SQLiteHistorian:
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    hist = SQLiteHistorian(repo.db)
    return hist


def _make_frame(controller_id: int, pv: float, ts: datetime) -> TelemetryFrame:
    return TelemetryFrame(
        controller_id=controller_id, pv=pv, sp=50.0, co=25.0,
        integral_val=1.0, timestamp=ts, status=SignalStatus.GOOD,
    )


class TestSQLiteHistorian:
    @pytest.mark.asyncio
    async def test_write_batch_and_query(self, historian: SQLiteHistorian) -> None:
        now = datetime.now(tz=timezone.utc)
        frames = [_make_frame(1, pv=50.0 + i, ts=now + timedelta(seconds=i)) for i in range(10)]

        await historian.write_batch(frames)

        result = await historian.query(1, now - timedelta(seconds=1), now + timedelta(seconds=20))
        assert len(result) == 10
        assert result[0].pv == 50.0
        assert result[9].pv == 59.0

    @pytest.mark.asyncio
    async def test_query_filters_by_controller(self, historian: SQLiteHistorian) -> None:
        now = datetime.now(tz=timezone.utc)
        frames = [
            _make_frame(1, pv=10.0, ts=now),
            _make_frame(2, pv=20.0, ts=now),
        ]
        await historian.write_batch(frames)

        result = await historian.query(1, now - timedelta(seconds=1), now + timedelta(seconds=1))
        assert len(result) == 1
        assert result[0].controller_id == 1

    @pytest.mark.asyncio
    async def test_query_filters_by_time_range(self, historian: SQLiteHistorian) -> None:
        now = datetime.now(tz=timezone.utc)
        frames = [
            _make_frame(1, pv=10.0, ts=now - timedelta(hours=2)),
            _make_frame(1, pv=20.0, ts=now),
        ]
        await historian.write_batch(frames)

        result = await historian.query(1, now - timedelta(hours=1), now + timedelta(hours=1))
        assert len(result) == 1
        assert result[0].pv == 20.0

    @pytest.mark.asyncio
    async def test_cleanup_removes_old_data(self, historian: SQLiteHistorian) -> None:
        now = datetime.now(tz=timezone.utc)
        frames = [
            _make_frame(1, pv=10.0, ts=now - timedelta(days=10)),
            _make_frame(1, pv=20.0, ts=now),
        ]
        await historian.write_batch(frames)

        deleted = await historian.cleanup_older_than(7)
        assert deleted == 1

        result = await historian.query(1, now - timedelta(days=20), now + timedelta(days=1))
        assert len(result) == 1
        assert result[0].pv == 20.0

    @pytest.mark.asyncio
    async def test_empty_batch_is_noop(self, historian: SQLiteHistorian) -> None:
        await historian.write_batch([])
        # Should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/core/integration/test_historian.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_core.adapters.outbound.historian'`

- [ ] **Step 3: Implement historian.py**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/historian.py`:

```python
"""SQLite historian — batch insert, query, and retention cleanup for process data."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import aiosqlite

from smart_pid_domain.enums import SignalStatus
from smart_pid_domain.models.telemetry import TelemetryFrame

if TYPE_CHECKING:
    pass


class SQLiteHistorian:
    """Batch writer and reader for the Log_Processo table."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def write_batch(self, frames: list[TelemetryFrame]) -> None:
        if not frames:
            return
        await self._db.executemany(
            """INSERT INTO Log_Processo (timestamp, controlador_id, pv, sp, co, integral_val)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [
                (
                    frame.timestamp.isoformat(),
                    frame.controller_id,
                    frame.pv,
                    frame.sp,
                    frame.co,
                    frame.integral_val,
                )
                for frame in frames
            ],
        )
        await self._db.commit()

    async def query(
        self, controller_id: int, start: datetime, end: datetime
    ) -> list[TelemetryFrame]:
        cursor = await self._db.execute(
            """SELECT timestamp, controlador_id, pv, sp, co, integral_val
               FROM Log_Processo
               WHERE controlador_id = ? AND timestamp >= ? AND timestamp <= ?
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
                timestamp=datetime.fromisoformat(row[0]).replace(tzinfo=timezone.utc),
                status=SignalStatus.GOOD,
            )
            for row in rows
        ]

    async def cleanup_older_than(self, days: int) -> int:
        cursor = await self._db.execute(
            "DELETE FROM Log_Processo WHERE timestamp <= datetime('now', ?)",
            (f"-{days} days",),
        )
        await self._db.commit()
        return cursor.rowcount
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/core/integration/test_historian.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/historian.py tests/core/integration/test_historian.py
git commit -m "feat(core): implement SQLite historian with batch insert, query, and cleanup"
```

---

## Task 11: DB Worker (Bus Subscriber + Batch SQLite Writer)

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/application/workers/db_worker.py`
- Create: `tests/core/integration/test_db_worker.py`

- [ ] **Step 1: Write DB Worker tests**

Create `tests/core/integration/test_db_worker.py`:

```python
from __future__ import annotations

import time
from datetime import datetime, timezone

import msgpack
import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.db_worker import DBWorker


@pytest.fixture
async def setup(tmp_path):
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    bus = EventBus()
    bus.start()
    return bus, historian, repo


class TestDBWorker:
    @pytest.mark.asyncio
    async def test_flushes_telemetry_to_db(self, setup) -> None:
        bus, historian, repo = await setup
        worker = DBWorker(bus=bus, historian=historian, flush_interval_s=0.1)
        worker.start()

        try:
            pub = bus.create_publisher()
            time.sleep(0.05)

            now = datetime.now(tz=timezone.utc)
            frame_data = {
                "controller_id": 1,
                "pv": 55.0,
                "sp": 50.0,
                "co": 30.0,
                "integral_val": 1.2,
                "timestamp": now.isoformat(),
                "status": "GOOD",
            }
            pub.send(b"TELEMETRY.1", msgpack.packb(frame_data))

            # Wait for flush
            time.sleep(0.3)

            from datetime import timedelta
            result = await historian.query(1, now - timedelta(seconds=5), now + timedelta(seconds=5))
            assert len(result) >= 1
            assert result[0].pv == 55.0
        finally:
            worker.stop()
            bus.stop()

    @pytest.mark.asyncio
    async def test_handles_multiple_frames(self, setup) -> None:
        bus, historian, repo = await setup
        worker = DBWorker(bus=bus, historian=historian, flush_interval_s=0.1)
        worker.start()

        try:
            pub = bus.create_publisher()
            time.sleep(0.05)

            now = datetime.now(tz=timezone.utc)
            for i in range(5):
                frame_data = {
                    "controller_id": 1,
                    "pv": 50.0 + i,
                    "sp": 50.0,
                    "co": 25.0,
                    "integral_val": 1.0,
                    "timestamp": now.isoformat(),
                    "status": "GOOD",
                }
                pub.send(b"TELEMETRY.1", msgpack.packb(frame_data))

            time.sleep(0.3)

            from datetime import timedelta
            result = await historian.query(1, now - timedelta(seconds=5), now + timedelta(seconds=5))
            assert len(result) == 5
        finally:
            worker.stop()
            bus.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/core/integration/test_db_worker.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_core.application.workers.db_worker'`

- [ ] **Step 3: Implement db_worker.py**

Create `packages/smart_pid_core/src/smart_pid_core/application/workers/db_worker.py`:

```python
"""DB Worker — subscribes to bus, buffers telemetry, flushes to SQLite in batches."""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import msgpack

from smart_pid_domain.enums import SignalStatus
from smart_pid_domain.models.telemetry import TelemetryFrame

if TYPE_CHECKING:
    from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
    from smart_pid_core.application.event_bus import EventBus


class DBWorker:
    """Daemon thread that subscribes to TELEMETRY.* and flushes batches to SQLite."""

    def __init__(
        self,
        bus: EventBus,
        historian: SQLiteHistorian,
        flush_interval_s: float = 5.0,
        batch_size: int = 500,
    ) -> None:
        self._bus = bus
        self._historian = historian
        self._flush_interval_s = flush_interval_s
        self._batch_size = batch_size
        self._buffer: deque[TelemetryFrame] = deque(maxlen=10_000)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="db-worker",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._run_async())
        finally:
            loop.close()

    async def _run_async(self) -> None:
        sub = self._bus.create_subscriber(b"TELEMETRY")

        while not self._stop_event.is_set():
            # Drain messages from bus
            msg = sub.recv(timeout_ms=int(self._flush_interval_s * 1000))
            if msg is not None:
                self._process_message(msg)

            # Continue draining without blocking
            while True:
                msg = sub.recv(timeout_ms=0)
                if msg is None:
                    break
                self._process_message(msg)

            # Flush buffer
            await self._flush()

        # Final flush on shutdown
        await self._flush()

    def _process_message(self, msg: tuple[bytes, bytes]) -> None:
        _topic, payload = msg
        try:
            data = msgpack.unpackb(payload)
            frame = TelemetryFrame(
                controller_id=data["controller_id"],
                pv=data["pv"],
                sp=data["sp"],
                co=data["co"],
                integral_val=data["integral_val"],
                timestamp=datetime.fromisoformat(data["timestamp"]).replace(tzinfo=timezone.utc),
                status=SignalStatus(data.get("status", "GOOD")),
            )
            self._buffer.append(frame)
        except (KeyError, ValueError, msgpack.UnpackException):
            pass  # Log and skip malformed messages

    async def _flush(self) -> None:
        if not self._buffer:
            return
        batch = list(self._buffer)
        self._buffer.clear()
        await self._historian.write_batch(batch)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/core/integration/test_db_worker.py -v
```

Expected: All 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/db_worker.py tests/core/integration/test_db_worker.py
git commit -m "feat(core): implement DB Worker with bus subscription and batch SQLite writes"
```

---

## Task 12: PID Worker (Scan Rate Thread)

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py`
- Create: `tests/core/integration/test_pid_worker.py`

- [ ] **Step 1: Write PID Worker tests**

Create `tests/core/integration/test_pid_worker.py`:

```python
from __future__ import annotations

import time
from datetime import datetime, timezone

import msgpack
import pytest

from smart_pid_domain.models.controller import Controller, PIDParams
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager


class TestPIDWorker:
    def test_publishes_control_action(self) -> None:
        bus = EventBus()
        bus.start()

        try:
            controller = Controller(
                id=1, name="TIC-101",
                pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
                scan_rate_ms=100,
            )

            worker = PIDWorker(
                bus=bus,
                controller=controller,
                engine=PIDEngine(),
                mode_manager=ModeManager(),
            )
            worker.start()

            # Subscribe to control actions
            sub = bus.create_subscriber(b"ACTION.CTRL.1")
            pub = bus.create_publisher()
            time.sleep(0.05)

            # Inject telemetry
            now = datetime.now(tz=timezone.utc)
            frame_data = {
                "controller_id": 1,
                "pv": 40.0,
                "sp": 50.0,
                "co": 0.0,
                "integral_val": 0.0,
                "timestamp": now.isoformat(),
                "status": "GOOD",
            }
            pub.send(b"TELEMETRY.1", msgpack.packb(frame_data))

            # Wait for PID to compute
            msg = sub.recv(timeout_ms=2000)
            assert msg is not None
            topic, payload = msg
            assert topic == b"ACTION.CTRL.1"

            action = msgpack.unpackb(payload)
            assert "co" in action
            assert "integral_val" in action
        finally:
            worker.stop()
            bus.stop()

    def test_worker_survives_missing_telemetry(self) -> None:
        bus = EventBus()
        bus.start()

        try:
            controller = Controller(
                id=2, name="FIC-201",
                scan_rate_ms=100,
            )

            worker = PIDWorker(
                bus=bus,
                controller=controller,
                engine=PIDEngine(),
                mode_manager=ModeManager(),
            )
            worker.start()

            # Let it run for a bit without telemetry
            time.sleep(0.3)
            assert worker.is_alive()
        finally:
            worker.stop()
            bus.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/core/integration/test_pid_worker.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'smart_pid_core.application.workers.pid_worker'`

- [ ] **Step 3: Implement pid_worker.py**

Create `packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py`:

```python
"""PID Worker — high-priority daemon thread executing PID at the controller's scan rate."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import msgpack

from smart_pid_domain.enums import ControllerMode
from smart_pid_core.domain.services.pid_engine import PIDState
from smart_pid_core.domain.services.pid_mode_manager import BlockStatus

if TYPE_CHECKING:
    from smart_pid_domain.models.controller import Controller
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_core.domain.services.pid_engine import PIDEngine
    from smart_pid_core.domain.services.pid_mode_manager import ModeManager


class PIDWorker:
    """Daemon thread that runs the PID equation at the controller's scan rate.

    Subscribes to TELEMETRY.{id} and ACTION.AI.{id}.
    Publishes ACTION.CTRL.{id} with computed CO and integral value.
    """

    def __init__(
        self,
        bus: EventBus,
        controller: Controller,
        engine: PIDEngine,
        mode_manager: ModeManager,
    ) -> None:
        self._bus = bus
        self._controller = controller
        self._engine = engine
        self._mode_manager = mode_manager
        self._state = PIDState()
        self._mode = ControllerMode.MAN
        self._block_status = BlockStatus()
        self._last_pv: float = 0.0
        self._last_sp: float = 0.0
        self._last_co: float = 0.0
        self._has_telemetry = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def controller_id(self) -> int:
        return self._controller.id

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True,
            name=f"pid-worker-{self.controller_id}",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        telem_sub = self._bus.create_subscriber(f"TELEMETRY.{self.controller_id}".encode())
        ai_sub = self._bus.create_subscriber(f"ACTION.AI.{self.controller_id}".encode())
        pub = self._bus.create_publisher()

        scan_s = self._controller.scan_rate_ms / 1000.0

        # Allow subscriptions to propagate
        import time as _time
        _time.sleep(0.02)

        while not self._stop_event.is_set():
            tick_start = time.monotonic()

            # Drain telemetry
            self._drain_telemetry(telem_sub)

            # Drain AI actions
            self._drain_ai_actions(ai_sub)

            # Compute PID if we have telemetry and in a computing mode
            if self._has_telemetry and self._mode in {ControllerMode.AUTO, ControllerMode.CAS, ControllerMode.RCAS}:
                dt = scan_s
                params = self._controller.pid_params
                out_limits = (self._controller.out_lo_lim, self._controller.out_hi_lim)
                direct_acting = self._controller.control_opts.direct_acting

                result = self._engine.compute(
                    params=params,
                    state=self._state,
                    pv=self._last_pv,
                    sp=self._last_sp,
                    dt=dt,
                    out_limits=out_limits,
                    direct_acting=direct_acting,
                )

                self._state = result.new_state
                self._last_co = result.cv

                # Publish control action
                action_data = {
                    "controller_id": self.controller_id,
                    "co": result.cv,
                    "integral_val": result.new_state.cv,
                    "delta_cv": result.delta_cv,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                }
                pub.send(
                    f"ACTION.CTRL.{self.controller_id}".encode(),
                    msgpack.packb(action_data),
                )

            # Also republish telemetry with current CO for DB worker
            if self._has_telemetry:
                telem_data = {
                    "controller_id": self.controller_id,
                    "pv": self._last_pv,
                    "sp": self._last_sp,
                    "co": self._last_co,
                    "integral_val": self._state.cv,
                    "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                    "status": "GOOD",
                }
                pub.send(
                    f"TELEMETRY.{self.controller_id}".encode(),
                    msgpack.packb(telem_data),
                )

            # Sleep for remainder of scan period
            elapsed = time.monotonic() - tick_start
            sleep_time = scan_s - elapsed
            if sleep_time > 0:
                self._stop_event.wait(timeout=sleep_time)

    def _drain_telemetry(self, sub) -> None:
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                self._last_pv = data["pv"]
                self._last_sp = data["sp"]
                if not self._has_telemetry:
                    self._last_co = data.get("co", 0.0)
                self._has_telemetry = True
            except (KeyError, ValueError, msgpack.UnpackException):
                pass

    def _drain_ai_actions(self, sub) -> None:
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            # AI actions will be handled in Phase 5
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/core/integration/test_pid_worker.py -v
```

Expected: All 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py tests/core/integration/test_pid_worker.py
git commit -m "feat(core): implement PID Worker with scan rate loop and bus integration"
```

---

## Task 13: Loop Manager (Controller Lifecycle)

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py`
- Create: `tests/core/integration/test_loop_manager.py`

- [ ] **Step 1: Write loop manager tests**

Create `tests/core/integration/test_loop_manager.py`:

```python
from __future__ import annotations

import time

import pytest

from smart_pid_domain.models.controller import Controller
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager


class TestLoopManager:
    def test_start_and_stop_loop(self) -> None:
        bus = EventBus()
        bus.start()

        try:
            manager = LoopManager(bus=bus)
            controller = Controller(id=1, name="TIC-101", scan_rate_ms=100)

            manager.start_loop(controller)
            time.sleep(0.1)
            assert manager.is_loop_running(1)

            manager.stop_loop(1)
            time.sleep(0.1)
            assert not manager.is_loop_running(1)
        finally:
            bus.stop()

    def test_stop_all_loops(self) -> None:
        bus = EventBus()
        bus.start()

        try:
            manager = LoopManager(bus=bus)
            ctrl1 = Controller(id=1, name="TIC-101", scan_rate_ms=100)
            ctrl2 = Controller(id=2, name="FIC-201", scan_rate_ms=100)

            manager.start_loop(ctrl1)
            manager.start_loop(ctrl2)
            time.sleep(0.1)
            assert manager.is_loop_running(1)
            assert manager.is_loop_running(2)

            manager.stop_all()
            time.sleep(0.1)
            assert not manager.is_loop_running(1)
            assert not manager.is_loop_running(2)
        finally:
            bus.stop()

    def test_double_start_is_safe(self) -> None:
        bus = EventBus()
        bus.start()

        try:
            manager = LoopManager(bus=bus)
            controller = Controller(id=1, name="TIC-101", scan_rate_ms=100)

            manager.start_loop(controller)
            manager.start_loop(controller)  # Should not raise
            time.sleep(0.1)
            assert manager.is_loop_running(1)

            manager.stop_all()
        finally:
            bus.stop()

    def test_stop_nonexistent_is_safe(self) -> None:
        bus = EventBus()
        bus.start()

        try:
            manager = LoopManager(bus=bus)
            manager.stop_loop(999)  # Should not raise
        finally:
            bus.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/core/integration/test_loop_manager.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement loop_manager.py**

Create `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py`:

```python
"""Loop Manager — lifecycle management for controller PID loops."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager

if TYPE_CHECKING:
    from smart_pid_domain.models.controller import Controller
    from smart_pid_core.application.event_bus import EventBus


@dataclass
class LoopContext:
    """Holds references to all active components for one control loop."""

    controller: Controller
    pid_worker: PIDWorker
    engine: PIDEngine = field(default_factory=PIDEngine)
    mode_manager: ModeManager = field(default_factory=ModeManager)


class LoopManager:
    """Manages the lifecycle of PID control loops.

    start_loop() creates domain services and spawns workers.
    stop_loop() signals workers to stop.
    """

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._loops: dict[int, LoopContext] = {}

    def start_loop(self, controller: Controller) -> None:
        if controller.id in self._loops:
            return  # Already running

        engine = PIDEngine()
        mode_manager = ModeManager()

        pid_worker = PIDWorker(
            bus=self._bus,
            controller=controller,
            engine=engine,
            mode_manager=mode_manager,
        )

        ctx = LoopContext(
            controller=controller,
            pid_worker=pid_worker,
            engine=engine,
            mode_manager=mode_manager,
        )

        self._loops[controller.id] = ctx
        pid_worker.start()

    def stop_loop(self, controller_id: int) -> None:
        ctx = self._loops.pop(controller_id, None)
        if ctx is None:
            return
        ctx.pid_worker.stop()

    def stop_all(self) -> None:
        for controller_id in list(self._loops.keys()):
            self.stop_loop(controller_id)

    def is_loop_running(self, controller_id: int) -> bool:
        ctx = self._loops.get(controller_id)
        return ctx is not None and ctx.pid_worker.is_alive()

    def get_context(self, controller_id: int) -> LoopContext | None:
        return self._loops.get(controller_id)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/core/integration/test_loop_manager.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py tests/core/integration/test_loop_manager.py
git commit -m "feat(core): implement Loop Manager for controller lifecycle management"
```

---

## Task 14: Backend Entry Point (main.py)

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/main.py`
- Modify: `.env.example`

- [ ] **Step 1: Implement main.py**

Create `packages/smart_pid_core/src/smart_pid_core/main.py`:

```python
"""Smart PID Core Engine — backend daemon entry point."""

from __future__ import annotations

import asyncio
import signal
import sys

import structlog

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings

logger = structlog.get_logger()


async def run_daemon(settings: CoreSettings) -> None:
    """Bootstrap and run the backend daemon until interrupted."""
    logger.info("starting_daemon", api_port=settings.api_port, zmq_port=settings.zmq_publish_port)

    # Initialize event bus
    bus = EventBus()
    bus.start()
    logger.info("event_bus_started")

    # Initialize loop manager
    loop_manager = LoopManager(bus=bus)

    # Set up graceful shutdown
    stop_event = asyncio.Event()

    def handle_signal() -> None:
        logger.info("shutdown_signal_received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    logger.info("daemon_ready")

    # Wait for shutdown signal
    await stop_event.wait()

    # Graceful shutdown
    logger.info("shutting_down")
    loop_manager.stop_all()
    bus.stop()
    logger.info("daemon_stopped")


def main() -> None:
    """CLI entry point."""
    try:
        settings = CoreSettings()  # type: ignore[call-arg]
    except Exception as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        print("Ensure SPID_JWT_SECRET is set in environment or .env file.", file=sys.stderr)
        sys.exit(1)

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.get_level_from_name(settings.log_level)
        ),
    )

    asyncio.run(run_daemon(settings))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update .env.example**

Rewrite `.env.example`:

```env
# Smart PID Core Engine — environment configuration
SPID_JWT_SECRET=change-me-in-production
SPID_LOG_LEVEL=INFO
SPID_OPCUA_ENDPOINT=opc.tcp://localhost:4840
SPID_API_PORT=8000
SPID_API_HOST=0.0.0.0
SPID_ZMQ_PUBLISH_PORT=5555
SPID_SIMULATOR_ENABLED=false
SPID_SIMULATOR_PORT=4841
```

- [ ] **Step 3: Verify entry point runs**

```bash
SPID_JWT_SECRET=test-secret uv run smart-pid-core &
sleep 2
kill %1
```

Expected: Logs show `starting_daemon`, `event_bus_started`, `daemon_ready`. Clean shutdown on kill.

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/main.py .env.example
git commit -m "feat(core): add backend daemon entry point with graceful shutdown"
```

---

## Task 15: Run Full Test Suite and Final Cleanup

- [ ] **Step 1: Run all tests**

```bash
uv run pytest tests/ -v --tb=short
```

Expected: All tests pass. Count should be approximately:
- `tests/domain/`: ~15 tests (enums, models, events)
- `tests/core/unit/`: ~16 tests (PID engine, mode manager, config)
- `tests/core/integration/`: ~20 tests (event bus, SQLite repo, historian, DB worker, PID worker, loop manager)

- [ ] **Step 2: Run linter**

```bash
uv run ruff check packages/ tests/
```

Expected: No errors.

- [ ] **Step 3: Run type checker**

```bash
uv run mypy packages/smart_pid_domain/src packages/smart_pid_core/src --ignore-missing-imports
```

Expected: No errors (or only minor issues to fix).

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "chore: fix lint and type check issues from Phase 1"
```

---

## Summary of Phase 1 Deliverables

After completing all 15 tasks:

1. **Monorepo** with 3 uv workspace packages (`smart_pid_domain`, `smart_pid_core`, `smart_pid_hmi` stub)
2. **Shared domain** with all enums, models (Controller, PIDParams, TelemetryFrame), events, and exceptions
3. **PID Engine** (velocity form, anti-windup, bumpless transfer, SP ramp) migrated to `smart_pid_core`
4. **PID Mode Manager** (8-mode state machine) migrated to `smart_pid_core`
5. **ZeroMQ Event Bus** (`inproc://` XPUB/XSUB proxy)
6. **SQLite Repository** (full DDL with 7 tables, controller CRUD, WAL mode)
7. **SQLite Historian** (batch insert, time-range query, retention cleanup)
8. **DB Worker** (bus subscriber, telemetry buffering, batch flush)
9. **PID Worker** (scan rate thread, PID computation, control action publishing)
10. **Loop Manager** (controller lifecycle management)
11. **Backend daemon entry point** with graceful shutdown
12. **~50 tests** covering domain, unit, and integration
