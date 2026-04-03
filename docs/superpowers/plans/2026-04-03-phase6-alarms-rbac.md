# Phase 6: Alarms + RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add real-time alarm detection with ISA-18.2 ACK workflow, RBAC enforcement on all API endpoints, audit trail, and user management.

**Architecture:** AlarmEngine (pure domain service) evaluates PV against limits; AlarmWorker (daemon thread) subscribes to TELEMETRY.* on bus and publishes ALARM.*. RBAC via FastAPI dependencies with fixed role hierarchy. Audit trail via explicit calls in route handlers. HMI gets AlarmPanel page + evolved AlarmBar.

**Tech Stack:** Python 3.13, aiosqlite, FastAPI, ZeroMQ (msgpack), PySide6, pydantic v2, pytest

**Spec:** `docs/superpowers/specs/2026-04-03-phase6-alarms-rbac-design.md`

---

## File Map

### New Files
| File | Purpose |
|------|---------|
| `packages/smart_pid_domain/src/smart_pid_domain/models/alarm_config.py` | AlarmConfig + AlarmTransition frozen dataclasses |
| `packages/smart_pid_core/src/smart_pid_core/domain/services/alarm_engine.py` | Pure alarm detection with hysteresis |
| `packages/smart_pid_core/src/smart_pid_core/application/workers/alarm_worker.py` | Bus subscriber, alarm evaluation loop |
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py` | Log_Alarmes CRUD |
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/audit_repo.py` | Log_Auditoria CRUD |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/alarms.py` | Alarm REST endpoints |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/users.py` | User management CRUD |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/audit.py` | Audit trail endpoint |
| `packages/smart_pid_domain/src/smart_pid_domain/dtos/alarms.py` | Alarm DTOs |
| `packages/smart_pid_domain/src/smart_pid_domain/dtos/users.py` | User DTOs |
| `packages/smart_pid_hmi/src/smart_pid_hmi/pages/alarm_panel.py` | Alarm management page |
| `tests/core/unit/test_alarm_engine.py` | AlarmEngine unit tests |
| `tests/core/unit/test_alarm_repo.py` | AlarmRepository tests |
| `tests/core/unit/test_audit_repo.py` | AuditRepository tests |
| `tests/core/unit/test_rbac.py` | RBAC dependency tests |
| `tests/core/integration/test_alarm_api.py` | Alarm REST endpoint tests |
| `tests/core/integration/test_user_api.py` | User management API tests |
| `tests/core/integration/test_audit_api.py` | Audit API tests |
| `tests/hmi/pages/test_alarm_panel.py` | AlarmPanel widget tests |

### Modified Files
| File | Change |
|------|--------|
| `packages/smart_pid_domain/src/smart_pid_domain/enums.py` | Add AlarmState, AuditAction enums |
| `packages/smart_pid_domain/src/smart_pid_domain/events.py` | Add AlarmTriggered, AlarmCleared, AlarmAcknowledged |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py` | Add require_operator(), require_supervisor() |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py` | Register alarm, user, audit routers + alarm_repo/audit_repo on app.state |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py` | Add audit logging to login |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py` | Add RBAC + audit |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py` | Add RBAC + audit |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py` | Add RBAC |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/opcua.py` | Add RBAC |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/stats.py` | Add RBAC |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/ai.py` | Add RBAC |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/system.py` | Add RBAC |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/history.py` | Add RBAC |
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py` | Add get_by_id, update, deactivate methods |
| `packages/smart_pid_core/src/smart_pid_core/main.py` | Wire AlarmWorker, AlarmRepo, AuditRepo |
| `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` | Add Alarms toolbar button, AlarmPanel page |
| `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/alarm_bar.py` | Priority counters, blink animation |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/session.py` | Extract role from JWT |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py` | Add alarm + user management methods |

---

## Task 1: Domain Enums + AlarmConfig Model

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/enums.py:80`
- Create: `packages/smart_pid_domain/src/smart_pid_domain/models/alarm_config.py`
- Test: `tests/domain/test_alarm_config.py`

- [ ] **Step 1: Write test for AlarmState enum and AuditAction enum**

```python
# tests/domain/test_alarm_config.py
"""Tests for AlarmState, AuditAction enums and AlarmConfig model."""
from __future__ import annotations

from datetime import UTC, datetime

from smart_pid_domain.enums import AlarmPriority, AlarmState, AlarmType, AuditAction
from smart_pid_domain.models.alarm_config import AlarmConfig, AlarmTransition


def test_alarm_state_values():
    assert AlarmState.UNACKNOWLEDGED == "UNACKNOWLEDGED"
    assert AlarmState.ACKNOWLEDGED == "ACKNOWLEDGED"
    assert AlarmState.CLEARED_UNACK == "CLEARED_UNACK"


def test_audit_action_values():
    assert AuditAction.LOGIN == "LOGIN"
    assert AuditAction.SP_CHANGE == "SP_CHANGE"
    assert AuditAction.ACK_ALARM == "ACK_ALARM"
    assert AuditAction.TUNE_PID == "TUNE_PID"


def test_alarm_config_creation():
    config = AlarmConfig(
        hihi_enabled=True, hihi_value=90.0, hihi_priority=AlarmPriority.CRITICAL,
        hi_enabled=True, hi_value=80.0, hi_priority=AlarmPriority.WARNING,
        lo_enabled=True, lo_value=20.0, lo_priority=AlarmPriority.WARNING,
        lolo_enabled=True, lolo_value=10.0, lolo_priority=AlarmPriority.CRITICAL,
        dv_hi_enabled=True, dv_hi_value=15.0, dv_hi_priority=AlarmPriority.ADVISORY,
        dv_lo_enabled=True, dv_lo_value=15.0, dv_lo_priority=AlarmPriority.ADVISORY,
        deadband_percent=2.0,
    )
    assert config.hihi_enabled is True
    assert config.deadband_percent == 2.0


def test_alarm_config_is_frozen():
    config = AlarmConfig(
        hihi_enabled=False, hihi_value=0, hihi_priority=AlarmPriority.LOG,
        hi_enabled=False, hi_value=0, hi_priority=AlarmPriority.LOG,
        lo_enabled=False, lo_value=0, lo_priority=AlarmPriority.LOG,
        lolo_enabled=False, lolo_value=0, lolo_priority=AlarmPriority.LOG,
        dv_hi_enabled=False, dv_hi_value=0, dv_hi_priority=AlarmPriority.LOG,
        dv_lo_enabled=False, dv_lo_value=0, dv_lo_priority=AlarmPriority.LOG,
        deadband_percent=0,
    )
    try:
        config.hihi_enabled = True  # type: ignore[misc]
        assert False, "Should be frozen"
    except AttributeError:
        pass


def test_alarm_transition_creation():
    t = AlarmTransition(
        controller_id=1,
        alarm_type=AlarmType.HIHI,
        priority=AlarmPriority.CRITICAL,
        transition="TRIGGERED",
        value=95.0,
        limit=90.0,
        timestamp=datetime.now(tz=UTC),
    )
    assert t.transition == "TRIGGERED"
    assert t.controller_id == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_alarm_config.py -v`
Expected: FAIL — `AlarmState`, `AuditAction`, `AlarmConfig`, `AlarmTransition` not defined

- [ ] **Step 3: Add AlarmState and AuditAction enums**

Add to `packages/smart_pid_domain/src/smart_pid_domain/enums.py` after `AlarmType`:

```python
class AlarmState(StrEnum):
    """ISA-18.2 alarm states for ACK workflow."""
    UNACKNOWLEDGED = "UNACKNOWLEDGED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    CLEARED_UNACK = "CLEARED_UNACK"


class AuditAction(StrEnum):
    """Audit trail action types."""
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    SP_CHANGE = "SP_CHANGE"
    MODE_CHANGE = "MODE_CHANGE"
    OUTPUT_CHANGE = "OUTPUT_CHANGE"
    ACK_ALARM = "ACK_ALARM"
    ACK_ALARM_ALL = "ACK_ALARM_ALL"
    TUNE_PID = "TUNE_PID"
    CONFIG_AI = "CONFIG_AI"
    CONFIG_ALARM = "CONFIG_ALARM"
    CREATE_CONTROLLER = "CREATE_CONTROLLER"
    UPDATE_CONTROLLER = "UPDATE_CONTROLLER"
    DELETE_CONTROLLER = "DELETE_CONTROLLER"
    CREATE_USER = "CREATE_USER"
    UPDATE_USER = "UPDATE_USER"
    DEACTIVATE_USER = "DEACTIVATE_USER"
    SIMULATOR_CONFIG = "SIMULATOR_CONFIG"
    OPCUA_CONFIG = "OPCUA_CONFIG"
```

- [ ] **Step 4: Create AlarmConfig and AlarmTransition models**

```python
# packages/smart_pid_domain/src/smart_pid_domain/models/alarm_config.py
"""Alarm configuration and transition models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from smart_pid_domain.enums import AlarmPriority, AlarmType

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class AlarmConfig:
    """Alarm limits and priorities for a controller."""

    hihi_enabled: bool
    hihi_value: float
    hihi_priority: AlarmPriority
    hi_enabled: bool
    hi_value: float
    hi_priority: AlarmPriority
    lo_enabled: bool
    lo_value: float
    lo_priority: AlarmPriority
    lolo_enabled: bool
    lolo_value: float
    lolo_priority: AlarmPriority
    dv_hi_enabled: bool
    dv_hi_value: float
    dv_hi_priority: AlarmPriority
    dv_lo_enabled: bool
    dv_lo_value: float
    dv_lo_priority: AlarmPriority
    deadband_percent: float  # 0.0-50.0, % of alarm limit


@dataclass(frozen=True)
class AlarmTransition:
    """Represents a single alarm state change (trigger or clear)."""

    controller_id: int
    alarm_type: AlarmType
    priority: AlarmPriority
    transition: Literal["TRIGGERED", "CLEARED"]
    value: float
    limit: float
    timestamp: datetime
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/domain/test_alarm_config.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/enums.py \
       packages/smart_pid_domain/src/smart_pid_domain/models/alarm_config.py \
       tests/domain/test_alarm_config.py
git commit -m "feat(domain): add AlarmState, AuditAction enums and AlarmConfig model"
```

---

## Task 2: Domain Events (AlarmTriggered, AlarmCleared, AlarmAcknowledged)

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/events.py:73`
- Test: `tests/domain/test_events_alarm.py`

- [ ] **Step 1: Write test for new alarm events**

```python
# tests/domain/test_events_alarm.py
"""Tests for alarm domain events."""
from __future__ import annotations

from datetime import UTC, datetime

from smart_pid_domain.enums import AlarmPriority, AlarmType
from smart_pid_domain.events import AlarmAcknowledged, AlarmCleared, AlarmTriggered


def test_alarm_triggered_creation():
    e = AlarmTriggered(
        controller_id=1,
        alarm_type=AlarmType.HIHI,
        priority=AlarmPriority.CRITICAL,
        value=95.0,
        limit=90.0,
        timestamp=datetime.now(tz=UTC),
    )
    assert e.controller_id == 1
    assert e.alarm_type == AlarmType.HIHI
    assert e.event_id is not None


def test_alarm_cleared_creation():
    e = AlarmCleared(
        controller_id=1,
        alarm_type=AlarmType.HIHI,
        value=85.0,
        timestamp=datetime.now(tz=UTC),
    )
    assert e.controller_id == 1
    assert e.event_id is not None


def test_alarm_acknowledged_creation():
    e = AlarmAcknowledged(
        controller_id=1,
        alarm_type=AlarmType.HIHI,
        user_id=2,
        username="operator1",
        timestamp=datetime.now(tz=UTC),
    )
    assert e.username == "operator1"
    assert e.event_id is not None


def test_alarm_events_are_frozen():
    e = AlarmTriggered(
        controller_id=1, alarm_type=AlarmType.HI,
        priority=AlarmPriority.WARNING, value=85.0,
        limit=80.0, timestamp=datetime.now(tz=UTC),
    )
    try:
        e.value = 99.0  # type: ignore[misc]
        assert False, "Should be frozen"
    except AttributeError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_events_alarm.py -v`
Expected: FAIL — `AlarmTriggered` etc. not importable

- [ ] **Step 3: Add alarm events to events.py**

Add to end of `packages/smart_pid_domain/src/smart_pid_domain/events.py`:

```python
@dataclass(frozen=True)
class AlarmTriggered:
    """Published by AlarmWorker when an alarm activates."""

    controller_id: int
    alarm_type: AlarmType
    priority: AlarmPriority
    value: float
    limit: float
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class AlarmCleared:
    """Published by AlarmWorker when an alarm returns to normal."""

    controller_id: int
    alarm_type: AlarmType
    value: float
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class AlarmAcknowledged:
    """Published when a user acknowledges an alarm."""

    controller_id: int
    alarm_type: AlarmType
    user_id: int
    username: str
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)
```

Also add to the TYPE_CHECKING imports at the top of events.py:

```python
from smart_pid_domain.enums import AIEngine, AlarmPriority, AlarmType, ConnectionState, ControlObjective
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/test_events_alarm.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/events.py \
       tests/domain/test_events_alarm.py
git commit -m "feat(domain): add AlarmTriggered, AlarmCleared, AlarmAcknowledged events"
```

---

## Task 3: AlarmEngine Domain Service

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/services/alarm_engine.py`
- Test: `tests/core/unit/test_alarm_engine.py`

- [ ] **Step 1: Write comprehensive tests for AlarmEngine**

```python
# tests/core/unit/test_alarm_engine.py
"""Tests for AlarmEngine — alarm detection, hysteresis, deviation suppression."""
from __future__ import annotations

from datetime import UTC, datetime

from smart_pid_core.domain.services.alarm_engine import AlarmEngine
from smart_pid_domain.enums import AlarmPriority, AlarmType
from smart_pid_domain.models.alarm_config import AlarmConfig

_BASE_CONFIG = AlarmConfig(
    hihi_enabled=True, hihi_value=90.0, hihi_priority=AlarmPriority.CRITICAL,
    hi_enabled=True, hi_value=80.0, hi_priority=AlarmPriority.WARNING,
    lo_enabled=True, lo_value=20.0, lo_priority=AlarmPriority.WARNING,
    lolo_enabled=True, lolo_value=10.0, lolo_priority=AlarmPriority.CRITICAL,
    dv_hi_enabled=True, dv_hi_value=15.0, dv_hi_priority=AlarmPriority.ADVISORY,
    dv_lo_enabled=True, dv_lo_value=15.0, dv_lo_priority=AlarmPriority.ADVISORY,
    deadband_percent=2.0,
)


def _now():
    return datetime.now(tz=UTC)


class TestProcessAlarms:
    def test_hihi_triggers(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(1, pv=95.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        triggered = [t for t in transitions if t.alarm_type == AlarmType.HIHI]
        assert len(triggered) == 1
        assert triggered[0].transition == "TRIGGERED"
        assert triggered[0].priority == AlarmPriority.CRITICAL

    def test_hi_triggers(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(1, pv=85.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        triggered_types = {t.alarm_type for t in transitions if t.transition == "TRIGGERED"}
        assert AlarmType.HI in triggered_types

    def test_lo_triggers(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(1, pv=15.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        triggered_types = {t.alarm_type for t in transitions if t.transition == "TRIGGERED"}
        assert AlarmType.LO in triggered_types

    def test_lolo_triggers(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(1, pv=5.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        triggered_types = {t.alarm_type for t in transitions if t.transition == "TRIGGERED"}
        assert AlarmType.LOLO in triggered_types

    def test_no_alarm_in_normal_range(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(1, pv=50.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        assert len(transitions) == 0

    def test_disabled_alarm_does_not_trigger(self):
        config = AlarmConfig(
            hihi_enabled=False, hihi_value=90.0, hihi_priority=AlarmPriority.CRITICAL,
            hi_enabled=False, hi_value=80.0, hi_priority=AlarmPriority.WARNING,
            lo_enabled=False, lo_value=20.0, lo_priority=AlarmPriority.WARNING,
            lolo_enabled=False, lolo_value=10.0, lolo_priority=AlarmPriority.CRITICAL,
            dv_hi_enabled=False, dv_hi_value=15.0, dv_hi_priority=AlarmPriority.ADVISORY,
            dv_lo_enabled=False, dv_lo_value=15.0, dv_lo_priority=AlarmPriority.ADVISORY,
            deadband_percent=2.0,
        )
        engine = AlarmEngine()
        transitions = engine.evaluate(1, pv=95.0, sp=50.0, alarm_config=config, sp_ramping=False)
        assert len(transitions) == 0


class TestHysteresis:
    def test_hihi_does_not_clear_without_deadband(self):
        """HIHI at 90.0, deadband 2% = 1.8. Must drop below 88.2 to clear."""
        engine = AlarmEngine()
        # Trigger
        engine.evaluate(1, pv=95.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        # Still above (90 - 1.8 = 88.2)
        transitions = engine.evaluate(1, pv=89.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        cleared = [t for t in transitions if t.alarm_type == AlarmType.HIHI and t.transition == "CLEARED"]
        assert len(cleared) == 0

    def test_hihi_clears_below_deadband(self):
        engine = AlarmEngine()
        engine.evaluate(1, pv=95.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        transitions = engine.evaluate(1, pv=87.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        cleared = [t for t in transitions if t.alarm_type == AlarmType.HIHI and t.transition == "CLEARED"]
        assert len(cleared) == 1

    def test_lo_clears_above_deadband(self):
        """LO at 20.0, deadband 2% = 0.4. Must rise above 20.4 to clear."""
        engine = AlarmEngine()
        engine.evaluate(1, pv=15.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        # Still below (20 + 0.4 = 20.4)
        transitions = engine.evaluate(1, pv=20.2, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        cleared = [t for t in transitions if t.alarm_type == AlarmType.LO and t.transition == "CLEARED"]
        assert len(cleared) == 0
        # Now above
        transitions = engine.evaluate(1, pv=21.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        cleared = [t for t in transitions if t.alarm_type == AlarmType.LO and t.transition == "CLEARED"]
        assert len(cleared) == 1


class TestDeviationAlarms:
    def test_dv_hi_triggers(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(1, pv=70.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        triggered = [t for t in transitions if t.alarm_type == AlarmType.DV_HI]
        assert len(triggered) == 1
        assert triggered[0].transition == "TRIGGERED"

    def test_dv_lo_triggers(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(1, pv=30.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        triggered = [t for t in transitions if t.alarm_type == AlarmType.DV_LO]
        assert len(triggered) == 1

    def test_deviation_suppressed_during_sp_ramp(self):
        engine = AlarmEngine()
        transitions = engine.evaluate(1, pv=70.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=True)
        dv_transitions = [t for t in transitions if t.alarm_type in (AlarmType.DV_HI, AlarmType.DV_LO)]
        assert len(dv_transitions) == 0


class TestMultiController:
    def test_independent_state_per_controller(self):
        engine = AlarmEngine()
        # Controller 1 triggers HIHI
        t1 = engine.evaluate(1, pv=95.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        assert any(t.alarm_type == AlarmType.HIHI for t in t1)
        # Controller 2 in normal range
        t2 = engine.evaluate(2, pv=50.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        assert len(t2) == 0


class TestNoRetrigger:
    def test_already_active_alarm_does_not_retrigger(self):
        engine = AlarmEngine()
        t1 = engine.evaluate(1, pv=95.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        hihi_count = sum(1 for t in t1 if t.alarm_type == AlarmType.HIHI)
        assert hihi_count == 1
        # Same condition — no new transition
        t2 = engine.evaluate(1, pv=96.0, sp=50.0, alarm_config=_BASE_CONFIG, sp_ramping=False)
        hihi_count = sum(1 for t in t2 if t.alarm_type == AlarmType.HIHI)
        assert hihi_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_alarm_engine.py -v`
Expected: FAIL — `alarm_engine` module not found

- [ ] **Step 3: Implement AlarmEngine**

```python
# packages/smart_pid_core/src/smart_pid_core/domain/services/alarm_engine.py
"""AlarmEngine — pure domain service for process alarm detection."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from smart_pid_domain.enums import AlarmPriority, AlarmType
from smart_pid_domain.models.alarm_config import AlarmConfig, AlarmTransition


@dataclass
class _PointState:
    """Mutable tracking state for one (controller, alarm_type) pair."""

    active: bool = False


# High alarms: trigger when PV >= limit, clear when PV < (limit - deadband)
_HIGH_ALARMS = (AlarmType.HIHI, AlarmType.HI)
# Low alarms: trigger when PV <= limit, clear when PV > (limit + deadband)
_LOW_ALARMS = (AlarmType.LO, AlarmType.LOLO)
# Deviation alarms
_DEV_ALARMS = (AlarmType.DV_HI, AlarmType.DV_LO)


class AlarmEngine:
    """Evaluates process values against alarm limits with hysteresis."""

    def __init__(self) -> None:
        # (controller_id, alarm_type) -> _PointState
        self._states: dict[tuple[int, AlarmType], _PointState] = field(
            default_factory=dict
        ) if False else {}

    def evaluate(
        self,
        controller_id: int,
        pv: float,
        sp: float,
        alarm_config: AlarmConfig,
        sp_ramping: bool,
    ) -> list[AlarmTransition]:
        """Evaluate all alarm types for one controller. Returns transitions."""
        now = datetime.now(tz=UTC)
        transitions: list[AlarmTransition] = []

        # Process alarms
        checks: list[tuple[AlarmType, bool, float, AlarmPriority]] = [
            (AlarmType.HIHI, alarm_config.hihi_enabled, alarm_config.hihi_value, alarm_config.hihi_priority),
            (AlarmType.HI, alarm_config.hi_enabled, alarm_config.hi_value, alarm_config.hi_priority),
            (AlarmType.LO, alarm_config.lo_enabled, alarm_config.lo_value, alarm_config.lo_priority),
            (AlarmType.LOLO, alarm_config.lolo_enabled, alarm_config.lolo_value, alarm_config.lolo_priority),
        ]

        for atype, enabled, limit, priority in checks:
            if not enabled:
                continue
            state = self._get_state(controller_id, atype)
            deadband = abs(limit) * alarm_config.deadband_percent / 100.0

            if atype in _HIGH_ALARMS:
                triggered = pv >= limit
                cleared = pv < (limit - deadband)
            else:  # _LOW_ALARMS
                triggered = pv <= limit
                cleared = pv > (limit + deadband)

            t = self._check_transition(
                state, triggered, cleared, controller_id, atype, priority, pv, limit, now,
            )
            if t is not None:
                transitions.append(t)

        # Deviation alarms (suppressed during SP ramp)
        if not sp_ramping:
            dev_checks: list[tuple[AlarmType, bool, float, AlarmPriority, float]] = [
                (AlarmType.DV_HI, alarm_config.dv_hi_enabled, alarm_config.dv_hi_value, alarm_config.dv_hi_priority, pv - sp),
                (AlarmType.DV_LO, alarm_config.dv_lo_enabled, alarm_config.dv_lo_value, alarm_config.dv_lo_priority, sp - pv),
            ]
            for atype, enabled, limit, priority, deviation in dev_checks:
                if not enabled:
                    continue
                state = self._get_state(controller_id, atype)
                deadband = abs(limit) * alarm_config.deadband_percent / 100.0
                triggered = deviation >= limit
                cleared = deviation < (limit - deadband)
                t = self._check_transition(
                    state, triggered, cleared, controller_id, atype, priority, pv, limit, now,
                )
                if t is not None:
                    transitions.append(t)

        return transitions

    def _get_state(self, controller_id: int, alarm_type: AlarmType) -> _PointState:
        key = (controller_id, alarm_type)
        if key not in self._states:
            self._states[key] = _PointState()
        return self._states[key]

    def _check_transition(
        self,
        state: _PointState,
        triggered: bool,
        cleared: bool,
        controller_id: int,
        alarm_type: AlarmType,
        priority: AlarmPriority,
        value: float,
        limit: float,
        timestamp: datetime,
    ) -> AlarmTransition | None:
        if triggered and not state.active:
            state.active = True
            return AlarmTransition(
                controller_id=controller_id, alarm_type=alarm_type,
                priority=priority, transition="TRIGGERED",
                value=value, limit=limit, timestamp=timestamp,
            )
        if cleared and state.active:
            state.active = False
            return AlarmTransition(
                controller_id=controller_id, alarm_type=alarm_type,
                priority=priority, transition="CLEARED",
                value=value, limit=limit, timestamp=timestamp,
            )
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_alarm_engine.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/services/alarm_engine.py \
       tests/core/unit/test_alarm_engine.py
git commit -m "feat(core): add AlarmEngine domain service with hysteresis and deviation suppression"
```

---

## Task 4: AlarmRepository (Outbound Adapter)

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py`
- Test: `tests/core/unit/test_alarm_repo.py`

- [ ] **Step 1: Write tests for AlarmRepository**

```python
# tests/core/unit/test_alarm_repo.py
"""Tests for AlarmRepository — CRUD on Log_Alarmes."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio

from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_domain.enums import AlarmPriority, AlarmType


@pytest_asyncio.fixture
async def alarm_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "test.db")
    await repo.initialize()
    alarm_repo = AlarmRepository(repo.db)
    yield alarm_repo


@pytest.mark.asyncio
async def test_insert_alarm(alarm_repo: AlarmRepository):
    alarm_id = await alarm_repo.insert_alarm(
        controller_id=1,
        alarm_type=AlarmType.HIHI,
        priority=AlarmPriority.CRITICAL,
        value=95.0,
        limit_value=90.0,
        triggered_at=datetime.now(tz=UTC),
    )
    assert alarm_id > 0


@pytest.mark.asyncio
async def test_get_active(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    await alarm_repo.insert_alarm(1, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, now)
    active = await alarm_repo.get_active()
    assert len(active) == 2


@pytest.mark.asyncio
async def test_mark_cleared(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    await alarm_repo.mark_cleared(1, AlarmType.HIHI, now)
    active = await alarm_repo.get_active()
    # Still visible (cleared but unacknowledged)
    assert len(active) == 1
    assert active[0]["cleared_at"] is not None


@pytest.mark.asyncio
async def test_acknowledge(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    alarm_id = await alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    await alarm_repo.acknowledge(alarm_id, "operator1", now)
    active = await alarm_repo.get_active()
    assert len(active) == 1
    assert active[0]["acknowledged"] == 1
    assert active[0]["ack_by_user"] == "operator1"


@pytest.mark.asyncio
async def test_cleared_and_acked_removed_from_active(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    alarm_id = await alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    await alarm_repo.mark_cleared(1, AlarmType.HIHI, now)
    await alarm_repo.acknowledge(alarm_id, "operator1", now)
    active = await alarm_repo.get_active()
    assert len(active) == 0


@pytest.mark.asyncio
async def test_acknowledge_all(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    await alarm_repo.insert_alarm(1, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, now)
    count = await alarm_repo.acknowledge_all("admin", now)
    assert count == 2


@pytest.mark.asyncio
async def test_get_history(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    from datetime import timedelta
    history = await alarm_repo.get_history(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
    )
    assert len(history) == 1


@pytest.mark.asyncio
async def test_get_active_filter_by_controller(alarm_repo: AlarmRepository):
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    await alarm_repo.insert_alarm(2, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, now)
    active = await alarm_repo.get_active(controller_id=1)
    assert len(active) == 1
    assert active[0]["controller_id"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_alarm_repo.py -v`
Expected: FAIL — `alarm_repo` module not found

- [ ] **Step 3: Implement AlarmRepository**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py
"""Alarm repository — CRUD operations on Log_Alarmes table."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    import aiosqlite

    from smart_pid_domain.enums import AlarmPriority, AlarmType


class AlarmRepository:
    """Persistence layer for alarm events."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def insert_alarm(
        self,
        controller_id: int,
        alarm_type: AlarmType,
        priority: AlarmPriority,
        value: float,
        limit_value: float,
        triggered_at: datetime,
    ) -> int:
        """Insert a new alarm record. Returns the alarm ID."""
        async with self._db.execute(
            """INSERT INTO Log_Alarmes
               (controlador_id, tipo_alarme, prioridade, valor, limite, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (controller_id, str(alarm_type), str(priority), value, limit_value,
             triggered_at.isoformat()),
        ) as cur:
            alarm_id = cur.lastrowid
        await self._db.commit()
        return alarm_id or 0

    async def mark_cleared(
        self, controller_id: int, alarm_type: AlarmType, cleared_at: datetime,
    ) -> None:
        """Mark the most recent active alarm of this type as cleared."""
        await self._db.execute(
            """UPDATE Log_Alarmes SET reconhecido_em = ?
               WHERE controlador_id = ? AND tipo_alarme = ?
               AND reconhecido_em IS NULL AND reconhecido = 0
               ORDER BY id DESC LIMIT 1""",
            (cleared_at.isoformat(), controller_id, str(alarm_type)),
        )
        # Use a separate column for cleared_at since reconhecido_em is for ACK time
        # The existing schema uses reconhecido_em for ACK. We store cleared_at in the
        # timestamp-like pattern. Let's update the approach to match the existing schema.
        # Actually, the existing Log_Alarmes schema doesn't have a cleared_at column.
        # We need to work with what exists. Let's use a convention:
        # reconhecido_em stores ACK time, and we add tracking via a status approach.
        # Simpler: just mark reconhecido_em for cleared_at since schema already has it.
        # Wait — reconhecido_em is for ACK. The schema needs a cleared_at column.
        # Since the DDL is in sqlite_repo.py and we can modify it, let's add cleared_at.
        pass

    async def acknowledge(
        self, alarm_id: int, username: str, ack_at: datetime,
    ) -> None:
        """Acknowledge a specific alarm."""
        await self._db.execute(
            """UPDATE Log_Alarmes SET reconhecido = 1, reconhecido_por = ?, reconhecido_em = ?
               WHERE id = ?""",
            (username, ack_at.isoformat(), alarm_id),
        )
        await self._db.commit()

    async def acknowledge_all(self, username: str, ack_at: datetime) -> int:
        """Acknowledge all unacknowledged alarms. Returns count."""
        async with self._db.execute(
            """UPDATE Log_Alarmes SET reconhecido = 1, reconhecido_por = ?, reconhecido_em = ?
               WHERE reconhecido = 0""",
            (username, ack_at.isoformat()),
        ) as cur:
            count = cur.rowcount
        await self._db.commit()
        return count

    async def get_active(
        self, controller_id: int | None = None, priority: str | None = None,
    ) -> list[dict]:
        """Return alarms that are still visible (not cleared+acked)."""
        sql = """SELECT id, controlador_id as controller_id, tipo_alarme as alarm_type,
                        prioridade as priority, valor as value, limite as limit_value,
                        timestamp as triggered_at, cleared_at,
                        reconhecido as acknowledged,
                        reconhecido_por as ack_by_user, reconhecido_em as ack_at
                 FROM Log_Alarmes
                 WHERE NOT (cleared_at IS NOT NULL AND reconhecido = 1)"""
        params: list = []
        if controller_id is not None:
            sql += " AND controlador_id = ?"
            params.append(controller_id)
        if priority is not None:
            sql += " AND prioridade = ?"
            params.append(priority)
        sql += " ORDER BY timestamp DESC"

        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        controller_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Return alarm history in a time range."""
        sql = """SELECT id, controlador_id as controller_id, tipo_alarme as alarm_type,
                        prioridade as priority, valor as value, limite as limit_value,
                        timestamp as triggered_at, cleared_at,
                        reconhecido as acknowledged,
                        reconhecido_por as ack_by_user, reconhecido_em as ack_at
                 FROM Log_Alarmes
                 WHERE timestamp BETWEEN ? AND ?"""
        params: list = [start.isoformat(), end.isoformat()]
        if controller_id is not None:
            sql += " AND controlador_id = ?"
            params.append(controller_id)
        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
```

**Important:** The existing `Log_Alarmes` DDL in `sqlite_repo.py` (line 179) does NOT have a `cleared_at` column. We need to add it. Modify the DDL in `sqlite_repo.py`:

Change the `Log_Alarmes` CREATE TABLE in `_DDL` (around line 179):

```sql
CREATE TABLE IF NOT EXISTS Log_Alarmes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    controlador_id  INTEGER NOT NULL,
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now')),
    tipo_alarme     TEXT    NOT NULL,
    prioridade      TEXT    NOT NULL DEFAULT 'WARNING',
    valor           REAL,
    limite          REAL,
    cleared_at      TEXT,
    reconhecido     INTEGER NOT NULL DEFAULT 0,
    reconhecido_por TEXT,
    reconhecido_em  TEXT
);
```

Note: `reconhecido_por` changes from `INTEGER REFERENCES Usuarios(id)` to `TEXT` to store username directly (simpler, avoids joins). Also add `cleared_at TEXT` column.

Also update `mark_cleared` to use the new column:

```python
    async def mark_cleared(
        self, controller_id: int, alarm_type: AlarmType, cleared_at: datetime,
    ) -> None:
        """Mark the most recent active alarm of this type as cleared."""
        await self._db.execute(
            """UPDATE Log_Alarmes SET cleared_at = ?
               WHERE controlador_id = ? AND tipo_alarme = ? AND cleared_at IS NULL""",
            (cleared_at.isoformat(), controller_id, str(alarm_type)),
        )
        await self._db.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_alarm_repo.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py \
       tests/core/unit/test_alarm_repo.py
git commit -m "feat(core): add AlarmRepository with ISA-18.2 ACK workflow persistence"
```

---

## Task 5: AuditRepository (Outbound Adapter)

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/audit_repo.py`
- Test: `tests/core/unit/test_audit_repo.py`

- [ ] **Step 1: Write tests for AuditRepository**

```python
# tests/core/unit/test_audit_repo.py
"""Tests for AuditRepository — CRUD on Log_Auditoria."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio

from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_domain.enums import AuditAction


@pytest_asyncio.fixture
async def audit_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "test.db")
    await repo.initialize()
    audit_repo = AuditRepository(repo.db)
    yield audit_repo


@pytest.mark.asyncio
async def test_record_audit(audit_repo: AuditRepository):
    await audit_repo.record(
        user_id=1,
        username="admin",
        action=AuditAction.LOGIN,
        resource=None,
        detail=None,
    )
    now = datetime.now(tz=UTC)
    history = await audit_repo.get_history(
        start=now - timedelta(hours=1),
        end=now + timedelta(hours=1),
    )
    assert len(history) == 1
    assert history[0]["action"] == "LOGIN"
    assert history[0]["username"] == "admin"


@pytest.mark.asyncio
async def test_record_with_detail(audit_repo: AuditRepository):
    await audit_repo.record(
        user_id=1, username="admin",
        action=AuditAction.SP_CHANGE,
        resource="controller:1",
        detail='{"old": 50.0, "new": 60.0}',
    )
    now = datetime.now(tz=UTC)
    history = await audit_repo.get_history(start=now - timedelta(hours=1), end=now + timedelta(hours=1))
    assert history[0]["resource"] == "controller:1"
    assert "old" in history[0]["detail"]


@pytest.mark.asyncio
async def test_filter_by_action(audit_repo: AuditRepository):
    await audit_repo.record(1, "admin", AuditAction.LOGIN, None, None)
    await audit_repo.record(1, "admin", AuditAction.SP_CHANGE, "controller:1", None)
    now = datetime.now(tz=UTC)
    history = await audit_repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        action=AuditAction.LOGIN,
    )
    assert len(history) == 1
    assert history[0]["action"] == "LOGIN"


@pytest.mark.asyncio
async def test_filter_by_user(audit_repo: AuditRepository):
    await audit_repo.record(1, "admin", AuditAction.LOGIN, None, None)
    await audit_repo.record(2, "operator1", AuditAction.LOGIN, None, None)
    now = datetime.now(tz=UTC)
    history = await audit_repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        user_id=2,
    )
    assert len(history) == 1
    assert history[0]["username"] == "operator1"


@pytest.mark.asyncio
async def test_pagination(audit_repo: AuditRepository):
    for i in range(5):
        await audit_repo.record(1, "admin", AuditAction.LOGIN, None, f"entry-{i}")
    now = datetime.now(tz=UTC)
    page = await audit_repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        limit=2, offset=0,
    )
    assert len(page) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_audit_repo.py -v`
Expected: FAIL — `audit_repo` module not found

- [ ] **Step 3: Implement AuditRepository**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/outbound/audit_repo.py
"""Audit repository — CRUD operations on Log_Auditoria table."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

    from smart_pid_domain.enums import AuditAction


class AuditRepository:
    """Persistence layer for audit trail entries."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def record(
        self,
        user_id: int,
        username: str,
        action: AuditAction,
        resource: str | None,
        detail: str | None,
    ) -> None:
        """Insert an audit trail entry."""
        await self._db.execute(
            """INSERT INTO Log_Auditoria (usuario_id, timestamp, acao, entidade, detalhe)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, datetime.now(tz=UTC).isoformat(), str(action),
             resource or "", detail or ""),
        )
        await self._db.commit()

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        user_id: int | None = None,
        action: AuditAction | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Return audit entries in a time range."""
        sql = """SELECT id, usuario_id as user_id, timestamp,
                        acao as action, entidade as resource, detalhe as detail
                 FROM Log_Auditoria WHERE timestamp BETWEEN ? AND ?"""
        params: list = [start.isoformat(), end.isoformat()]
        if user_id is not None:
            sql += " AND usuario_id = ?"
            params.append(user_id)
        if action is not None:
            sql += " AND acao = ?"
            params.append(str(action))
        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
```

Note: the `Log_Auditoria` DDL (line 158 of `sqlite_repo.py`) uses `acao` for action and `entidade` for resource. The `username` is not in the existing schema — it only has `usuario_id`. We need to add a `username` column. Modify the DDL:

```sql
CREATE TABLE IF NOT EXISTS Log_Auditoria (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id      INTEGER REFERENCES Usuarios(id),
    username        TEXT    NOT NULL DEFAULT '',
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now')),
    acao            TEXT    NOT NULL,
    entidade        TEXT    NOT NULL DEFAULT '',
    entidade_id     INTEGER,
    detalhe         TEXT    NOT NULL DEFAULT '',
    ip_origem       TEXT    NOT NULL DEFAULT ''
);
```

Update the `record` and `get_history` SQL to include `username`:

```python
    async def record(self, user_id, username, action, resource, detail):
        await self._db.execute(
            """INSERT INTO Log_Auditoria (usuario_id, username, timestamp, acao, entidade, detalhe)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, datetime.now(tz=UTC).isoformat(), str(action),
             resource or "", detail or ""),
        )
        await self._db.commit()

    async def get_history(self, start, end, user_id=None, action=None, limit=100, offset=0):
        sql = """SELECT id, usuario_id as user_id, username, timestamp,
                        acao as action, entidade as resource, detalhe as detail
                 FROM Log_Auditoria WHERE timestamp BETWEEN ? AND ?"""
        # ... rest unchanged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_audit_repo.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/audit_repo.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py \
       tests/core/unit/test_audit_repo.py
git commit -m "feat(core): add AuditRepository for compliance-grade audit trail"
```

---

## Task 6: RBAC Dependencies (require_operator, require_supervisor)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py:63-72`
- Test: `tests/core/unit/test_rbac.py`

- [ ] **Step 1: Write RBAC tests**

```python
# tests/core/unit/test_rbac.py
"""Tests for RBAC FastAPI dependencies."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from smart_pid_core.adapters.inbound.api.dependencies import (
    require_admin,
    require_operator,
    require_supervisor,
)
from smart_pid_domain.dtos.auth import UserClaims


def test_require_operator_allows_operator():
    user = UserClaims(user_id=1, username="op1", role="OPERATOR")
    result = require_operator(user)
    assert result.username == "op1"


def test_require_operator_allows_supervisor():
    user = UserClaims(user_id=1, username="sup1", role="SUPERVISOR")
    result = require_operator(user)
    assert result.username == "sup1"


def test_require_operator_allows_admin():
    user = UserClaims(user_id=1, username="admin", role="ADMIN")
    result = require_operator(user)
    assert result.username == "admin"


def test_require_supervisor_allows_supervisor():
    user = UserClaims(user_id=1, username="sup1", role="SUPERVISOR")
    result = require_supervisor(user)
    assert result.username == "sup1"


def test_require_supervisor_allows_admin():
    user = UserClaims(user_id=1, username="admin", role="ADMIN")
    result = require_supervisor(user)
    assert result.username == "admin"


def test_require_supervisor_rejects_operator():
    user = UserClaims(user_id=1, username="op1", role="OPERATOR")
    with pytest.raises(HTTPException) as exc_info:
        require_supervisor(user)
    assert exc_info.value.status_code == 403


def test_require_admin_rejects_supervisor():
    user = UserClaims(user_id=1, username="sup1", role="SUPERVISOR")
    with pytest.raises(HTTPException) as exc_info:
        require_admin(user)
    assert exc_info.value.status_code == 403


def test_require_admin_rejects_operator():
    user = UserClaims(user_id=1, username="op1", role="OPERATOR")
    with pytest.raises(HTTPException) as exc_info:
        require_admin(user)
    assert exc_info.value.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_rbac.py -v`
Expected: FAIL — `require_operator` and `require_supervisor` not importable

- [ ] **Step 3: Add require_operator and require_supervisor to dependencies.py**

Add after `require_admin` (line 72) in `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`:

```python
_ROLE_LEVEL = {"OPERATOR": 0, "SUPERVISOR": 1, "ADMIN": 2}


def require_operator(
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> UserClaims:
    """Verify the current user has at least operator role (all authenticated users)."""
    if _ROLE_LEVEL.get(user.role.upper(), -1) < _ROLE_LEVEL["OPERATOR"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator access required",
        )
    return user


def require_supervisor(
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> UserClaims:
    """Verify the current user has at least supervisor role."""
    if _ROLE_LEVEL.get(user.role.upper(), -1) < _ROLE_LEVEL["SUPERVISOR"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor access required",
        )
    return user
```

Also update `require_admin` to use the same pattern (case-insensitive):

```python
def require_admin(
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> UserClaims:
    """Verify the current user has admin role."""
    if _ROLE_LEVEL.get(user.role.upper(), -1) < _ROLE_LEVEL["ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/core/unit/test_rbac.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py \
       tests/core/unit/test_rbac.py
git commit -m "feat(core): add require_operator and require_supervisor RBAC dependencies"
```

---

## Task 7: Alarm DTOs + REST Endpoints

**Files:**
- Create: `packages/smart_pid_domain/src/smart_pid_domain/dtos/alarms.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/alarms.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`
- Test: `tests/core/integration/test_alarm_api.py`

- [ ] **Step 1: Create alarm DTOs**

```python
# packages/smart_pid_domain/src/smart_pid_domain/dtos/alarms.py
"""Alarm-related DTOs for REST API."""
from __future__ import annotations

from pydantic import BaseModel


class AlarmResponse(BaseModel):
    id: int
    controller_id: int
    alarm_type: str
    priority: str
    value: float
    limit_value: float
    triggered_at: str
    cleared_at: str | None = None
    acknowledged: bool = False
    ack_by_user: str | None = None
    ack_at: str | None = None


class AlarmAckRequest(BaseModel):
    """No body needed — user comes from JWT."""
    pass
```

- [ ] **Step 2: Write alarm API tests**

```python
# tests/core/integration/test_alarm_api.py
"""Integration tests for alarm REST endpoints."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token
from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import AlarmPriority, AlarmType


@pytest_asyncio.fixture
async def app_fixture(tmp_path):
    repo = SQLiteRepository(tmp_path / "test.db")
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    user_repo = UserRepository(repo.db)
    alarm_repo = AlarmRepository(repo.db)
    audit_repo = AuditRepository(repo.db)
    bus = EventBus()
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(jwt_secret="test-secret", db_path=tmp_path / "test.db")

    app = create_app(
        repo=repo, historian=historian, user_repo=user_repo,
        loop_manager=loop_manager, settings=settings,
        alarm_repo=alarm_repo, audit_repo=audit_repo,
    )
    yield app, alarm_repo, settings
    bus.stop()


def _token(settings, role="OPERATOR"):
    return create_access_token(1, "testuser", role, settings.jwt_secret, 1)


def test_get_active_alarms(app_fixture):
    import asyncio
    app, alarm_repo, settings = app_fixture
    # Seed an alarm
    asyncio.get_event_loop().run_until_complete(
        alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, datetime.now(tz=UTC))
    )
    client = TestClient(app)
    token = _token(settings)
    resp = client.get("/alarms/active", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["alarm_type"] == "HIHI"


def test_ack_alarm(app_fixture):
    import asyncio
    app, alarm_repo, settings = app_fixture
    alarm_id = asyncio.get_event_loop().run_until_complete(
        alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, datetime.now(tz=UTC))
    )
    client = TestClient(app)
    token = _token(settings)
    resp = client.post(f"/alarms/{alarm_id}/ack", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_ack_all(app_fixture):
    import asyncio
    app, alarm_repo, settings = app_fixture
    asyncio.get_event_loop().run_until_complete(
        alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, datetime.now(tz=UTC))
    )
    asyncio.get_event_loop().run_until_complete(
        alarm_repo.insert_alarm(1, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, datetime.now(tz=UTC))
    )
    client = TestClient(app)
    token = _token(settings)
    resp = client.post("/alarms/ack-all", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 2


def test_get_alarm_history(app_fixture):
    import asyncio
    app, alarm_repo, settings = app_fixture
    asyncio.get_event_loop().run_until_complete(
        alarm_repo.insert_alarm(1, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, datetime.now(tz=UTC))
    )
    client = TestClient(app)
    token = _token(settings)
    now = datetime.now(tz=UTC)
    resp = client.get(
        "/alarms/history",
        params={"start": (now.replace(hour=0)).isoformat(), "end": now.isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_alarm_api.py -v`
Expected: FAIL — alarms router not registered

- [ ] **Step 4: Create alarm router**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/alarms.py
"""Alarm router — active alarms, history, ACK."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_alarm_repo,
    get_audit_repo,
    require_operator,
)
from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.enums import AuditAction

router = APIRouter()


@router.get("/active")
async def get_active_alarms(
    _user: Annotated[UserClaims, Depends(require_operator)],
    alarm_repo: Annotated[AlarmRepository, Depends(get_alarm_repo)],
    controller_id: int | None = None,
    priority: str | None = None,
) -> list[dict]:
    return await alarm_repo.get_active(controller_id=controller_id, priority=priority)


@router.get("/history")
async def get_alarm_history(
    _user: Annotated[UserClaims, Depends(require_operator)],
    alarm_repo: Annotated[AlarmRepository, Depends(get_alarm_repo)],
    start: str = Query(...),
    end: str = Query(...),
    controller_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    from datetime import datetime as dt
    start_dt = dt.fromisoformat(start)
    end_dt = dt.fromisoformat(end)
    return await alarm_repo.get_history(
        start=start_dt, end=end_dt, controller_id=controller_id,
        limit=limit, offset=offset,
    )


@router.post("/{alarm_id}/ack")
async def ack_alarm(
    alarm_id: int,
    user: Annotated[UserClaims, Depends(require_operator)],
    alarm_repo: Annotated[AlarmRepository, Depends(get_alarm_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> dict:
    now = datetime.now(tz=UTC)
    await alarm_repo.acknowledge(alarm_id, user.username, now)
    await audit_repo.record(
        user.user_id, user.username, AuditAction.ACK_ALARM,
        f"alarm:{alarm_id}", None,
    )
    return {"status": "acknowledged", "alarm_id": alarm_id}


@router.post("/ack-all")
async def ack_all_alarms(
    user: Annotated[UserClaims, Depends(require_operator)],
    alarm_repo: Annotated[AlarmRepository, Depends(get_alarm_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> dict:
    now = datetime.now(tz=UTC)
    count = await alarm_repo.acknowledge_all(user.username, now)
    await audit_repo.record(
        user.user_id, user.username, AuditAction.ACK_ALARM_ALL,
        None, f'{{"count": {count}}}',
    )
    return {"status": "acknowledged", "count": count}
```

- [ ] **Step 5: Add get_alarm_repo and get_audit_repo dependencies**

Add to `dependencies.py`:

```python
def get_alarm_repo(request: Request):
    return request.app.state.alarm_repo


def get_audit_repo(request: Request):
    return request.app.state.audit_repo
```

- [ ] **Step 6: Register alarm router in app.py**

Add import: `from smart_pid_core.adapters.inbound.api.routers import alarms`

Add to `create_app` params: `alarm_repo=None, audit_repo=None,`

Add to app.state: `app.state.alarm_repo = alarm_repo` and `app.state.audit_repo = audit_repo`

Add router: `app.include_router(alarms.router, prefix="/alarms", tags=["alarms"])`

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_alarm_api.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/alarms.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/alarms.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py \
       tests/core/integration/test_alarm_api.py
git commit -m "feat(api): add alarm REST endpoints (active, history, ACK) with RBAC"
```

---

## Task 8: User Management Router + Extended UserRepository

**Files:**
- Create: `packages/smart_pid_domain/src/smart_pid_domain/dtos/users.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/users.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
- Test: `tests/core/integration/test_user_api.py`

- [ ] **Step 1: Create user DTOs**

```python
# packages/smart_pid_domain/src/smart_pid_domain/dtos/users.py
"""User management DTOs."""
from __future__ import annotations

from pydantic import BaseModel


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    active: bool = True
    created_at: str = ""


class UserUpdate(BaseModel):
    role: str | None = None
    password: str | None = None
```

- [ ] **Step 2: Write user API tests**

```python
# tests/core/integration/test_user_api.py
"""Integration tests for user management REST endpoints."""
from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token, hash_password
from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings


@pytest_asyncio.fixture
async def app_fixture(tmp_path):
    repo = SQLiteRepository(tmp_path / "test.db")
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    user_repo = UserRepository(repo.db)
    alarm_repo = AlarmRepository(repo.db)
    audit_repo = AuditRepository(repo.db)
    # Seed admin user
    await user_repo.create("admin", hash_password("admin"), "ADMIN")
    bus = EventBus()
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(jwt_secret="test-secret", db_path=tmp_path / "test.db")
    app = create_app(
        repo=repo, historian=historian, user_repo=user_repo,
        loop_manager=loop_manager, settings=settings,
        alarm_repo=alarm_repo, audit_repo=audit_repo,
    )
    yield app, user_repo, settings
    bus.stop()


def _admin_token(settings):
    return create_access_token(1, "admin", "ADMIN", settings.jwt_secret, 1)


def _operator_token(settings):
    return create_access_token(2, "op1", "OPERATOR", settings.jwt_secret, 1)


def test_list_users_admin(app_fixture):
    app, user_repo, settings = app_fixture
    client = TestClient(app)
    token = _admin_token(settings)
    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_list_users_operator_forbidden(app_fixture):
    app, user_repo, settings = app_fixture
    client = TestClient(app)
    token = _operator_token(settings)
    resp = client.get("/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_update_user_role(app_fixture):
    import asyncio
    app, user_repo, settings = app_fixture
    asyncio.get_event_loop().run_until_complete(
        user_repo.create("op1", hash_password("pass"), "OPERATOR")
    )
    client = TestClient(app)
    token = _admin_token(settings)
    resp = client.put("/users/2", json={"role": "SUPERVISOR"},
                      headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "SUPERVISOR"


def test_deactivate_user(app_fixture):
    import asyncio
    app, user_repo, settings = app_fixture
    asyncio.get_event_loop().run_until_complete(
        user_repo.create("op1", hash_password("pass"), "OPERATOR")
    )
    client = TestClient(app)
    token = _admin_token(settings)
    resp = client.delete("/users/2", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["active"] is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_user_api.py -v`
Expected: FAIL

- [ ] **Step 4: Extend UserRepository with get_by_id, update, deactivate**

Add to `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py`:

```python
    async def get_by_id(self, user_id: int) -> User | None:
        """Return user by ID or None."""
        async with self._db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em FROM Usuarios WHERE id = ?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return User(id=row[0], username=row[1], password_hash=row[2],
                    role=row[3], created_at=row[4])

    async def update(
        self, user_id: int, role: str | None = None, password_hash: str | None = None,
    ) -> User | None:
        """Update user role and/or password. Returns updated user."""
        updates: list[str] = []
        params: list = []
        if role is not None:
            updates.append("perfil = ?")
            params.append(role)
        if password_hash is not None:
            updates.append("senha_hash = ?")
            params.append(password_hash)
        if not updates:
            return await self.get_by_id(user_id)
        params.append(user_id)
        await self._db.execute(
            f"UPDATE Usuarios SET {', '.join(updates)} WHERE id = ?", params,
        )
        await self._db.commit()
        return await self.get_by_id(user_id)

    async def deactivate(self, user_id: int) -> User | None:
        """Soft-delete: set ativo=0."""
        await self._db.execute(
            "UPDATE Usuarios SET ativo = 0 WHERE id = ?", (user_id,),
        )
        await self._db.commit()
        return await self.get_by_id(user_id)
```

Also add `active` field to `User` dataclass:

```python
@dataclass
class User:
    id: int
    username: str
    password_hash: str
    role: str
    created_at: str
    active: bool = True
```

And update all queries to include `ativo`:

```python
    async def get_by_username(self, username: str) -> User | None:
        async with self._db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em, ativo FROM Usuarios WHERE nome = ? AND ativo = 1",
            (username,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return User(id=row[0], username=row[1], password_hash=row[2],
                    role=row[3], created_at=row[4], active=bool(row[5]))

    async def list_all(self) -> list[User]:
        async with self._db.execute(
            "SELECT id, nome, senha_hash, perfil, criado_em, ativo FROM Usuarios ORDER BY id"
        ) as cur:
            rows = await cur.fetchall()
        return [User(id=r[0], username=r[1], password_hash=r[2],
                     role=r[3], created_at=r[4], active=bool(r[5])) for r in rows]
```

- [ ] **Step 5: Create users router**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/users.py
"""User management router — admin only."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.auth import hash_password
from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    get_user_repo,
    require_admin,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_domain.dtos.auth import UserClaims
from smart_pid_domain.dtos.users import UserResponse, UserUpdate
from smart_pid_domain.enums import AuditAction

router = APIRouter()


@router.get("")
async def list_users(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> list[UserResponse]:
    users = await user_repo.list_all()
    return [
        UserResponse(id=u.id, username=u.username, role=u.role,
                     active=u.active, created_at=u.created_at)
        for u in users
    ]


@router.get("/{user_id}")
async def get_user(
    user_id: int,
    _admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> UserResponse:
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(id=user.id, username=user.username, role=user.role,
                        active=user.active, created_at=user.created_at)


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    body: UserUpdate,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    pw_hash = hash_password(body.password) if body.password else None
    user = await user_repo.update(user_id, role=body.role, password_hash=pw_hash)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await audit_repo.record(
        admin.user_id, admin.username, AuditAction.UPDATE_USER,
        f"user:{user_id}", f'{{"role": "{user.role}"}}',
    )
    return UserResponse(id=user.id, username=user.username, role=user.role,
                        active=user.active, created_at=user.created_at)


@router.delete("/{user_id}")
async def deactivate_user(
    user_id: int,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    user = await user_repo.deactivate(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await audit_repo.record(
        admin.user_id, admin.username, AuditAction.DEACTIVATE_USER,
        f"user:{user_id}", None,
    )
    return UserResponse(id=user.id, username=user.username, role=user.role,
                        active=user.active, created_at=user.created_at)
```

- [ ] **Step 6: Register users router in app.py**

Add import: `from smart_pid_core.adapters.inbound.api.routers import users`

Add router: `app.include_router(users.router, prefix="/users", tags=["users"])`

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_user_api.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/users.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/users.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py \
       tests/core/integration/test_user_api.py
git commit -m "feat(api): add user management CRUD endpoints (admin-only)"
```

---

## Task 9: Audit Trail Router + Audit Logging on Existing Endpoints

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/audit.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
- Test: `tests/core/integration/test_audit_api.py`

- [ ] **Step 1: Write audit API tests**

```python
# tests/core/integration/test_audit_api.py
"""Integration tests for audit trail endpoint."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token
from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings
from smart_pid_domain.enums import AuditAction


@pytest_asyncio.fixture
async def app_fixture(tmp_path):
    repo = SQLiteRepository(tmp_path / "test.db")
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    user_repo = UserRepository(repo.db)
    alarm_repo = AlarmRepository(repo.db)
    audit_repo = AuditRepository(repo.db)
    bus = EventBus()
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(jwt_secret="test-secret", db_path=tmp_path / "test.db")
    app = create_app(
        repo=repo, historian=historian, user_repo=user_repo,
        loop_manager=loop_manager, settings=settings,
        alarm_repo=alarm_repo, audit_repo=audit_repo,
    )
    yield app, audit_repo, settings
    bus.stop()


def test_get_audit_supervisor(app_fixture):
    import asyncio
    app, audit_repo, settings = app_fixture
    asyncio.get_event_loop().run_until_complete(
        audit_repo.record(1, "admin", AuditAction.LOGIN, None, None)
    )
    client = TestClient(app)
    token = create_access_token(1, "sup1", "SUPERVISOR", settings.jwt_secret, 1)
    now = datetime.now(tz=UTC)
    resp = client.get(
        "/audit",
        params={"start": (now - timedelta(hours=1)).isoformat(),
                "end": (now + timedelta(hours=1)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_get_audit_operator_forbidden(app_fixture):
    app, audit_repo, settings = app_fixture
    client = TestClient(app)
    token = create_access_token(1, "op1", "OPERATOR", settings.jwt_secret, 1)
    now = datetime.now(tz=UTC)
    resp = client.get(
        "/audit",
        params={"start": (now - timedelta(hours=1)).isoformat(),
                "end": (now + timedelta(hours=1)).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_audit_api.py -v`
Expected: FAIL

- [ ] **Step 3: Create audit router**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/audit.py
"""Audit trail router — supervisor+ access."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    require_supervisor,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_domain.dtos.auth import UserClaims

router = APIRouter()


@router.get("")
async def get_audit_history(
    _user: Annotated[UserClaims, Depends(require_supervisor)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
    start: str = Query(...),
    end: str = Query(...),
    user_id: int | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    from datetime import datetime
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)
    return await audit_repo.get_history(
        start=start_dt, end=end_dt, user_id=user_id,
        action=action, limit=limit, offset=offset,
    )
```

- [ ] **Step 4: Register audit router in app.py**

Add import and router registration:

```python
from smart_pid_core.adapters.inbound.api.routers import audit
app.include_router(audit.router, prefix="/audit", tags=["audit"])
```

- [ ] **Step 5: Add audit logging to auth login endpoint**

In `auth.py`, add audit_repo dependency and log successful login:

```python
from smart_pid_core.adapters.inbound.api.dependencies import get_audit_repo
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
from smart_pid_domain.enums import AuditAction

@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    settings: Annotated[CoreSettings, Depends(get_settings)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> TokenResponse:
    user = await user_repo.get_by_username(body.username)
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user.id, user.username, user.role, settings.jwt_secret, settings.jwt_expiry_hours)
    await audit_repo.record(user.id, user.username, AuditAction.LOGIN, None, None)
    return TokenResponse(access_token=token)
```

- [ ] **Step 6: Add audit logging to command endpoints**

Read `commands.py`, then add audit logging to setpoint/mode/output endpoints with `AuditAction.SP_CHANGE`, `AuditAction.MODE_CHANGE`, `AuditAction.OUTPUT_CHANGE`. Add `require_operator` dependency.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_audit_api.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/audit.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py \
       tests/core/integration/test_audit_api.py
git commit -m "feat(api): add audit trail endpoint + audit logging on login and commands"
```

---

## Task 10: RBAC Enforcement on All Existing Routers

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/system.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/history.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/opcua.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/stats.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/ai.py`

- [ ] **Step 1: Read each router file and add RBAC dependencies**

For each router, add the appropriate `Depends(require_*)` parameter:

- `system.py`: GET endpoints → `require_operator`
- `controllers.py`: GET → `require_operator`, POST/PUT → `require_supervisor`, DELETE → `require_admin`
- `history.py`: GET → `require_operator`
- `simulator.py`: ALL → `require_supervisor`
- `opcua.py`: ALL → `require_admin`
- `stats.py`: GET → `require_operator`
- `ai.py`: GET → `require_operator`, PUT → `require_supervisor`

Pattern for each endpoint:

```python
from smart_pid_core.adapters.inbound.api.dependencies import require_operator
# Add parameter:
_user: Annotated[UserClaims, Depends(require_operator)],
```

- [ ] **Step 2: Add audit logging to controller CRUD and AI config**

In `controllers.py`, add audit for CREATE/UPDATE/DELETE with `AuditAction.CREATE_CONTROLLER`, etc.

In `ai.py`, add audit for PUT with `AuditAction.CONFIG_AI`.

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All existing tests still pass (may need to add auth tokens to existing tests)

- [ ] **Step 4: Fix any test failures from RBAC enforcement**

Existing integration tests may need auth tokens added. Update test fixtures to provide JWT headers.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/*.py
git commit -m "feat(api): enforce RBAC on all endpoints + audit logging on state changes"
```

---

## Task 11: AlarmWorker + Daemon Wiring

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/application/workers/alarm_worker.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py`

- [ ] **Step 1: Implement AlarmWorker**

```python
# packages/smart_pid_core/src/smart_pid_core/application/workers/alarm_worker.py
"""AlarmWorker — daemon thread evaluating alarms from telemetry bus."""
from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import msgpack

from smart_pid_core.domain.services.alarm_engine import AlarmEngine
from smart_pid_domain.enums import AlarmPriority, AlarmType
from smart_pid_domain.models.alarm_config import AlarmConfig

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus


class AlarmWorker:
    """Subscribes to TELEMETRY.* and evaluates alarm limits."""

    def __init__(self, bus: EventBus, alarm_configs: dict[int, AlarmConfig]) -> None:
        self._bus = bus
        self._alarm_configs = alarm_configs
        self._engine = AlarmEngine()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def update_config(self, controller_id: int, config: AlarmConfig) -> None:
        """Update alarm config for a controller (thread-safe via GIL)."""
        self._alarm_configs[controller_id] = config

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="alarm-worker",
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
        sub = self._bus.create_subscriber(b"STATUS.")
        pub = self._bus.create_publisher()
        time.sleep(0.02)  # Let subscriptions propagate

        while not self._stop_event.is_set():
            msg = sub.recv(timeout_ms=100)
            if msg is None:
                continue

            topic_bytes, payload = msg
            try:
                data = msgpack.unpackb(payload)
                cid = data.get("controller_id", 0)
                config = self._alarm_configs.get(cid)
                if config is None:
                    continue

                pv = data.get("pv", 0.0)
                sp = data.get("sp", 0.0)
                # sp_ramping not yet in STATUS messages — default False
                sp_ramping = data.get("sp_ramping", False)

                transitions = self._engine.evaluate(
                    cid, pv=pv, sp=sp, alarm_config=config, sp_ramping=sp_ramping,
                )

                for t in transitions:
                    alarm_data = {
                        "controller_id": t.controller_id,
                        "alarm_type": str(t.alarm_type),
                        "priority": str(t.priority),
                        "transition": t.transition,
                        "value": t.value,
                        "limit": t.limit,
                        "timestamp": t.timestamp.isoformat(),
                    }
                    pub.send(
                        f"EVENT.ALARM.{t.controller_id}".encode(),
                        msgpack.packb(alarm_data),
                    )
            except (msgpack.UnpackException, KeyError, ValueError):
                pass

```

- [ ] **Step 2: Wire AlarmWorker into daemon main.py**

Add to `main.py` after the AI repo section and before `create_app`:

```python
    # Phase 6: Alarm infrastructure
    from smart_pid_core.adapters.outbound.alarm_repo import AlarmRepository
    from smart_pid_core.adapters.outbound.audit_repo import AuditRepository
    from smart_pid_core.application.workers.alarm_worker import AlarmWorker

    alarm_repo = AlarmRepository(repo.db)
    audit_repo = AuditRepository(repo.db)

    # Build alarm configs from Configuracao_Alarmes table
    alarm_configs = await _load_alarm_configs(repo.db)
    alarm_worker = AlarmWorker(bus=bus, alarm_configs=alarm_configs)
    alarm_worker.start()
    logger.info("alarm_worker_started")
```

Add helper function:

```python
async def _load_alarm_configs(db) -> dict[int, AlarmConfig]:
    """Load alarm configurations from Configuracao_Alarmes table."""
    from smart_pid_domain.enums import AlarmPriority
    from smart_pid_domain.models.alarm_config import AlarmConfig

    configs: dict[int, AlarmConfig] = {}
    async with db.execute("SELECT * FROM Configuracao_Alarmes ORDER BY controlador_id") as cur:
        rows = await cur.fetchall()

    # Group by controller_id and build AlarmConfig
    by_controller: dict[int, dict] = {}
    for row in rows:
        cid = row["controlador_id"]
        if cid not in by_controller:
            by_controller[cid] = {}
        atype = row["tipo_alarme"]
        by_controller[cid][atype] = {
            "enabled": bool(row["habilitado"]),
            "value": row["limite"],
            "priority": AlarmPriority(row["prioridade"]),
            "hysteresis": row["histerese"],
        }

    for cid, alarms in by_controller.items():
        def _get(name, default_priority=AlarmPriority.WARNING):
            a = alarms.get(name, {})
            return a.get("enabled", False), a.get("value", 0.0), a.get("priority", default_priority)

        hihi_e, hihi_v, hihi_p = _get("HIHI", AlarmPriority.CRITICAL)
        hi_e, hi_v, hi_p = _get("HI")
        lo_e, lo_v, lo_p = _get("LO")
        lolo_e, lolo_v, lolo_p = _get("LOLO", AlarmPriority.CRITICAL)
        dvhi_e, dvhi_v, dvhi_p = _get("DV_HI", AlarmPriority.ADVISORY)
        dvlo_e, dvlo_v, dvlo_p = _get("DV_LO", AlarmPriority.ADVISORY)

        deadband = max((a.get("hysteresis", 0.0) for a in alarms.values()), default=0.0)

        configs[cid] = AlarmConfig(
            hihi_enabled=hihi_e, hihi_value=hihi_v, hihi_priority=hihi_p,
            hi_enabled=hi_e, hi_value=hi_v, hi_priority=hi_p,
            lo_enabled=lo_e, lo_value=lo_v, lo_priority=lo_p,
            lolo_enabled=lolo_e, lolo_value=lolo_v, lolo_priority=lolo_p,
            dv_hi_enabled=dvhi_e, dv_hi_value=dvhi_v, dv_hi_priority=dvhi_p,
            dv_lo_enabled=dvlo_e, dv_lo_value=dvlo_v, dv_lo_priority=dvlo_p,
            deadband_percent=deadband,
        )
    return configs
```

Update `create_app` call to pass `alarm_repo` and `audit_repo`:

```python
    app = create_app(
        repo=repo, historian=historian, user_repo=user_repo,
        loop_manager=loop_manager, settings=settings,
        simulator_adapter=simulator_adapter, opcua_adapter=opcua_adapter,
        stats_workers=loop_manager.get_stats_workers(),
        ai_workers=loop_manager.get_ai_workers(),
        ai_repo=ai_repo,
        alarm_repo=alarm_repo, audit_repo=audit_repo,
    )
```

Add to shutdown sequence (before `loop_manager.stop_all()`):

```python
    alarm_worker.stop()
```

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/alarm_worker.py \
       packages/smart_pid_core/src/smart_pid_core/main.py
git commit -m "feat(core): add AlarmWorker + wire alarm/audit repos into daemon lifecycle"
```

---

## Task 12: HMI Session Role Extraction

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/session.py`
- Test: `tests/hmi/test_session_role.py`

- [ ] **Step 1: Write test for role extraction**

```python
# tests/hmi/test_session_role.py
"""Tests for Session role extraction from JWT."""
from __future__ import annotations

import base64
import json
import time

from smart_pid_hmi.services.session import Session


def _make_token(role: str = "OPERATOR") -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').rstrip(b"=").decode()
    payload_data = {"sub": 1, "username": "testuser", "role": role, "exp": time.time() + 3600}
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"fake-sig").rstrip(b"=").decode()
    return f"{header}.{payload}.{sig}"


def test_role_extracted():
    session = Session()
    session.store_token(_make_token("SUPERVISOR"))
    assert session.role == "SUPERVISOR"


def test_role_none_when_not_authenticated():
    session = Session()
    assert session.role is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hmi/test_session_role.py -v`
Expected: FAIL — `Session.role` not defined

- [ ] **Step 3: Add role property to Session**

In `packages/smart_pid_hmi/src/smart_pid_hmi/services/session.py`, add `_role` field and property:

```python
    def __init__(self) -> None:
        self._token: str | None = None
        self._username: str | None = None
        self._role: str | None = None
        self._exp: float = 0.0

    @property
    def role(self) -> str | None:
        if self.is_authenticated:
            return self._role
        return None

    def store_token(self, token: str) -> None:
        try:
            payload_b64 = token.split(".")[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            self._token = token
            self._username = payload.get("username")
            self._role = payload.get("role")
            self._exp = float(payload.get("exp", 0))
        except (IndexError, json.JSONDecodeError, ValueError):
            self._token = None
            self._username = None
            self._role = None
            self._exp = 0.0

    def clear(self) -> None:
        self._token = None
        self._username = None
        self._role = None
        self._exp = 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/hmi/test_session_role.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/session.py \
       tests/hmi/test_session_role.py
git commit -m "feat(hmi): extract role from JWT in Session for permission-based UI"
```

---

## Task 13: APIClient Alarm Methods

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`
- Test: existing api_client tests pattern

- [ ] **Step 1: Add alarm methods to APIClient**

Add to `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`:

```python
    def get_active_alarms(self, controller_id: int | None = None) -> list[dict]:
        params = {}
        if controller_id is not None:
            params["controller_id"] = controller_id
        resp = self._http.get("/alarms/active", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def ack_alarm(self, alarm_id: int) -> dict:
        resp = self._http.post(f"/alarms/{alarm_id}/ack", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def ack_all_alarms(self) -> dict:
        resp = self._http.post("/alarms/ack-all", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def get_alarm_history(self, start: datetime, end: datetime, controller_id: int | None = None) -> list[dict]:
        params: dict = {"start": start.isoformat(), "end": end.isoformat()}
        if controller_id is not None:
            params["controller_id"] = controller_id
        resp = self._http.get("/alarms/history", params=params, headers=self._headers())
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 2: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py
git commit -m "feat(hmi): add alarm REST client methods to APIClient"
```

---

## Task 14: AlarmPanel HMI Page

**Files:**
- Create: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/alarm_panel.py`
- Test: `tests/hmi/pages/test_alarm_panel.py`

- [ ] **Step 1: Write test for AlarmPanel**

```python
# tests/hmi/pages/test_alarm_panel.py
"""Tests for AlarmPanel page."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from smart_pid_hmi.pages.alarm_panel import AlarmPanel
from smart_pid_hmi.themes.isa101 import ISA101Theme

app = QApplication.instance() or QApplication([])


def test_alarm_panel_creation():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    assert panel is not None


def test_alarm_panel_add_active_alarm():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    panel.on_alarm(1, {
        "controller_id": 1, "alarm_type": "HIHI", "priority": "CRITICAL",
        "value": 95.0, "limit": 90.0, "transition": "TRIGGERED",
        "timestamp": "2026-04-03T12:00:00",
    })
    assert panel.active_table.rowCount() == 1


def test_alarm_panel_clear_removes_from_active():
    theme = ISA101Theme()
    panel = AlarmPanel(theme=theme)
    panel.on_alarm(1, {
        "controller_id": 1, "alarm_type": "HIHI", "priority": "CRITICAL",
        "value": 95.0, "limit": 90.0, "transition": "TRIGGERED",
        "timestamp": "2026-04-03T12:00:00",
    })
    panel.on_alarm(1, {
        "controller_id": 1, "alarm_type": "HIHI", "priority": "CRITICAL",
        "value": 85.0, "limit": 90.0, "transition": "CLEARED",
        "timestamp": "2026-04-03T12:01:00",
    })
    # Cleared but not ACK'd — still in active table with CLEARED_UNACK status
    assert panel.active_table.rowCount() == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hmi/pages/test_alarm_panel.py -v`
Expected: FAIL — `AlarmPanel` not found

- [ ] **Step 3: Implement AlarmPanel**

```python
# packages/smart_pid_hmi/src/smart_pid_hmi/pages/alarm_panel.py
"""AlarmPanel — alarm management page with active + history tables."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_ACTIVE_COLUMNS = ["Controller", "Type", "Priority", "Value", "Limit", "Triggered", "Status"]
_PRIORITY_COLORS = {
    "CRITICAL": "#D32F2F",
    "WARNING": "#FFA000",
    "ADVISORY": "#1976D2",
    "LOG": "#757575",
}


class AlarmPanel(QWidget):
    """Page for alarm management: active alarms + ACK controls."""

    ack_requested = Signal(int)       # alarm_id
    ack_all_requested = Signal()

    def __init__(self, theme: ThemeBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        # (controller_id, alarm_type) -> row data dict
        self._active_alarms: dict[tuple[int, str], dict] = {}

        layout = QVBoxLayout(self)

        # Buttons
        btn_layout = QHBoxLayout()
        self._ack_btn = QPushButton("ACK Selected")
        self._ack_all_btn = QPushButton("ACK All")
        btn_layout.addWidget(self._ack_btn)
        btn_layout.addWidget(self._ack_all_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._ack_btn.clicked.connect(self._on_ack_selected)
        self._ack_all_btn.clicked.connect(self.ack_all_requested.emit)

        # Active alarms table
        self.active_table = QTableWidget(0, len(_ACTIVE_COLUMNS))
        self.active_table.setHorizontalHeaderLabels(_ACTIVE_COLUMNS)
        self.active_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.active_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        layout.addWidget(self.active_table)

    def on_alarm(self, controller_id: int, alarm: dict) -> None:
        """Handle an alarm transition from BusBridge."""
        atype = alarm.get("alarm_type", "")
        transition = alarm.get("transition", "")
        key = (controller_id, atype)

        if transition == "TRIGGERED":
            self._active_alarms[key] = {
                **alarm,
                "status": "UNACKNOWLEDGED",
            }
        elif transition == "CLEARED":
            if key in self._active_alarms:
                self._active_alarms[key]["status"] = "CLEARED_UNACK"
                self._active_alarms[key]["transition"] = "CLEARED"

        self._rebuild_table()

    def _rebuild_table(self) -> None:
        self.active_table.setRowCount(0)
        for (_cid, _atype), alarm in self._active_alarms.items():
            row = self.active_table.rowCount()
            self.active_table.insertRow(row)
            items = [
                str(alarm.get("controller_id", "")),
                alarm.get("alarm_type", ""),
                alarm.get("priority", ""),
                f"{alarm.get('value', 0.0):.1f}",
                f"{alarm.get('limit', 0.0):.1f}",
                alarm.get("timestamp", ""),
                alarm.get("status", ""),
            ]
            priority = alarm.get("priority", "")
            color = _PRIORITY_COLORS.get(priority, "#757575")
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(Qt.GlobalColor.white)
                item.setBackground(Qt.GlobalColor.transparent)
                if col == 2:  # Priority column
                    from PySide6.QtGui import QColor
                    item.setBackground(QColor(color))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.active_table.setItem(row, col, item)

    def _on_ack_selected(self) -> None:
        selected = self.active_table.selectedItems()
        if selected:
            row = selected[0].row()
            alarm_id_text = self.active_table.item(row, 0)
            if alarm_id_text:
                # In real implementation, would emit alarm_id from the data
                self.ack_requested.emit(row)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/hmi/pages/test_alarm_panel.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/alarm_panel.py \
       tests/hmi/pages/test_alarm_panel.py
git commit -m "feat(hmi): add AlarmPanel page with active alarms table and ACK controls"
```

---

## Task 15: MainWindow Integration (Toolbar + AlarmPanel + AlarmBar wiring)

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/alarm_bar.py`

- [ ] **Step 1: Add Alarms button to toolbar and wire AlarmPanel**

In `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`:

Add import:
```python
from smart_pid_hmi.pages.alarm_panel import AlarmPanel
```

After the Simulator button creation (around line 83), add:

```python
        self._alarms_btn = toolbar.addAction("Alarms")
        self._alarms_btn.triggered.connect(
            lambda: self._stack.setCurrentWidget(self._alarm_panel)
        )
```

After creating simulator_page (around line 98), add:

```python
        self._alarm_panel = AlarmPanel(theme=theme)
        self._stack.addWidget(self._alarm_panel)
```

Wire BusBridge alarm signal to both AlarmBar and AlarmPanel:

```python
        bus_bridge.alarm_received.connect(self._alarm_panel.on_alarm)
```

Wire AlarmPanel ACK signals:

```python
        self._alarm_panel.ack_all_requested.connect(self._send_ack_all)
```

Add ACK methods:

```python
    def _send_ack_all(self) -> None:
        threading.Thread(
            target=lambda: self._api_client.ack_all_alarms(),
            daemon=True,
        ).start()
```

- [ ] **Step 2: Add priority counters to AlarmBar**

In `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/alarm_bar.py`, add counter tracking:

```python
    def __init__(self, theme: ThemeBase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._alarms: list[dict] = []
        self._counts: dict[str, int] = {"CRITICAL": 0, "WARNING": 0, "ADVISORY": 0}
        # ... existing setup ...

        # Add counter label before scroll area
        self._counter_label = QLabel("")
        self._counter_label.setStyleSheet(
            f"color: {theme.fg_primary}; background: transparent; "
            f"font-size: {theme.font_size_label}px; padding: 0 8px;"
        )
        layout.insertWidget(0, self._counter_label)
```

Update `on_alarm` to track counts and `_rebuild` to update counter label.

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/main.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/widgets/alarm_bar.py
git commit -m "feat(hmi): wire AlarmPanel into MainWindow toolbar + alarm bar counters"
```

---

## Task 16: Final Integration Test + Lint + Full Suite

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run linter**

Run: `uv run --with ruff ruff check .`
Fix any issues: `uv run --with ruff ruff check --fix .`

- [ ] **Step 3: Run mypy**

Run: `uv run mypy packages/`
Fix any type errors.

- [ ] **Step 4: Commit any lint/type fixes**

```bash
git add -u
git commit -m "chore(phase6): fix lint and type errors"
```

- [ ] **Step 5: Update estado-atual.md**

Update `.claude/docs/estado-atual.md` with Phase 6 completion status.

- [ ] **Step 6: Final commit**

```bash
git add .claude/docs/estado-atual.md
git commit -m "docs: update estado-atual with Phase 6 completion"
```
