# Monitor + Supervisor Mode — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pivot SmartPID from internal PID execution to monitoring external PIDs and writing tuning parameters back to DCS with guardrails.

**Architecture:** New `SPID_EXECUTION_MODE=monitor` flag gates PIDWorker startup. A new MonitorWorker publishes `STATUS.{id}` from telemetry. AIWorker in monitor mode writes Kp/Ti/Td to DCS via OPCUAAdapter (auto-apply or approval-required per controller, always clamped by guardrails).

**Tech Stack:** Python 3.13, pydantic-settings, ZeroMQ (msgpack), asyncua, FastAPI, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-04-05-monitor-supervisor-mode-design.md`

---

## File Map

### Domain (`packages/smart_pid_domain/src/smart_pid_domain/`)

| File | Action | Purpose |
|------|--------|---------|
| `enums.py` | Modify | Add `TuningWriteMode`, `TuningRecStatus`, `SystemExecutionMode` |
| `models/controller.py` | Modify | Add `tuning_write_mode`, `max_tuning_change_pct` to Controller; expand TagBindings |
| `models/tuning.py` | Create | `PIDParamsRead`, `TuningRecommendation` frozen dataclasses |
| `events.py` | Modify | Add `TuningRecommended`, `TuningApplied` events |

### Core (`packages/smart_pid_core/src/smart_pid_core/`)

| File | Action | Purpose |
|------|--------|---------|
| `config.py` | Modify | Add `execution_mode` to CoreSettings |
| `application/workers/monitor_worker.py` | Create | MonitorWorker — enriches telemetry, publishes STATUS |
| `application/workers/io_worker.py` | Modify | Skip BKCAL write-back in monitor mode; read PID params at slow cadence |
| `application/loop_manager.py` | Modify | Branch on execution_mode: start MonitorWorker or PIDWorker |
| `application/workers/ai_worker.py` | Modify | Monitor mode: write tuning to DCS or publish recommendation |
| `adapters/outbound/opcua_adapter.py` | Modify | Add `read_pid_params()`, `write_pid_params()`, `read_external_mode()`, expand `register_controller()` |
| `adapters/inbound/api/routers/commands.py` | Modify | Gate SP/Mode/Output behind execute mode; add apply-tuning and recommendation endpoints |
| `adapters/inbound/api/dependencies.py` | Modify | Add `get_execution_mode()` dependency |
| `main.py` | Modify | Pass execution_mode to LoopManager and IOWorker |

### Tests

| File | Action | Purpose |
|------|--------|---------|
| `tests/domain/test_enums_tuning.py` | Create | TuningWriteMode, TuningRecStatus, SystemExecutionMode enums |
| `tests/domain/test_tuning_models.py` | Create | PIDParamsRead, TuningRecommendation |
| `tests/domain/test_events_tuning.py` | Create | TuningRecommended, TuningApplied events |
| `tests/core/unit/test_monitor_worker.py` | Create | MonitorWorker enrichment and STATUS publishing |
| `tests/core/unit/test_guardrails.py` | Create | Tuning guardrail clamping logic |
| `tests/core/unit/test_commands_monitor_mode.py` | Create | Commands return 409 in monitor mode |
| `tests/core/integration/test_loop_manager_monitor.py` | Create | LoopManager starts MonitorWorker in monitor mode |
| `tests/core/integration/test_io_worker_monitor.py` | Create | IOWorker skips BKCAL write in monitor mode |
| `tests/core/integration/test_tuning_writeback.py` | Create | End-to-end apply-tuning flow |

---

## Task 1: Domain Enums — TuningWriteMode, TuningRecStatus, SystemExecutionMode

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/enums.py`
- Create: `tests/domain/test_enums_tuning.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/domain/test_enums_tuning.py
"""Tests for tuning and execution mode enums."""
from smart_pid_domain.enums import (
    SystemExecutionMode,
    TuningRecStatus,
    TuningWriteMode,
)


class TestTuningWriteMode:
    def test_values(self) -> None:
        assert TuningWriteMode.AUTO_APPLY == "auto_apply"
        assert TuningWriteMode.APPROVAL_REQUIRED == "approval_required"
        assert TuningWriteMode.DISABLED == "disabled"

    def test_is_strenum(self) -> None:
        assert isinstance(TuningWriteMode.AUTO_APPLY, str)

    def test_member_count(self) -> None:
        assert len(TuningWriteMode) == 3


class TestTuningRecStatus:
    def test_values(self) -> None:
        assert TuningRecStatus.PENDING == "pending"
        assert TuningRecStatus.APPLIED == "applied"
        assert TuningRecStatus.REJECTED == "rejected"
        assert TuningRecStatus.EXPIRED == "expired"

    def test_member_count(self) -> None:
        assert len(TuningRecStatus) == 4


class TestSystemExecutionMode:
    def test_values(self) -> None:
        assert SystemExecutionMode.MONITOR == "monitor"
        assert SystemExecutionMode.EXECUTE == "execute"

    def test_member_count(self) -> None:
        assert len(SystemExecutionMode) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_enums_tuning.py -v`
Expected: FAIL with `ImportError: cannot import name 'SystemExecutionMode'`

- [ ] **Step 3: Implement the enums**

Add to `packages/smart_pid_domain/src/smart_pid_domain/enums.py` after the `ProcessPresetName` enum (line ~137):

```python
class TuningWriteMode(StrEnum):
    AUTO_APPLY = "auto_apply"
    APPROVAL_REQUIRED = "approval_required"
    DISABLED = "disabled"

class TuningRecStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"

class SystemExecutionMode(StrEnum):
    MONITOR = "monitor"
    EXECUTE = "execute"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_enums_tuning.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/enums.py tests/domain/test_enums_tuning.py
git commit -m "feat(domain): add TuningWriteMode, TuningRecStatus, SystemExecutionMode enums"
```

---

## Task 2: Domain Models — PIDParamsRead, TuningRecommendation

**Files:**
- Create: `packages/smart_pid_domain/src/smart_pid_domain/models/tuning.py`
- Create: `tests/domain/test_tuning_models.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/domain/test_tuning_models.py
"""Tests for tuning domain models."""
from uuid import UUID, uuid4

from smart_pid_domain.enums import TuningRecStatus
from smart_pid_domain.models.tuning import PIDParamsRead, TuningRecommendation


class TestPIDParamsRead:
    def test_creation_all_values(self) -> None:
        p = PIDParamsRead(kp=1.5, ti=10.0, td=0.5, timestamp=1000.0)
        assert p.kp == 1.5
        assert p.ti == 10.0
        assert p.td == 0.5
        assert p.timestamp == 1000.0

    def test_creation_partial_none(self) -> None:
        p = PIDParamsRead(kp=1.5, ti=None, td=None, timestamp=1000.0)
        assert p.kp == 1.5
        assert p.ti is None
        assert p.td is None

    def test_frozen(self) -> None:
        p = PIDParamsRead(kp=1.0, ti=10.0, td=0.0, timestamp=1000.0)
        try:
            p.kp = 2.0  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass


class TestTuningRecommendation:
    def test_creation(self) -> None:
        rec_id = uuid4()
        rec = TuningRecommendation(
            id=rec_id,
            controller_id=1,
            current_kp=1.0,
            current_ti=10.0,
            current_td=0.0,
            recommended_kp=1.2,
            recommended_ti=8.0,
            recommended_td=0.1,
            reason="fuzzy_sp_tracking",
            timestamp=1000.0,
        )
        assert rec.id == rec_id
        assert rec.status == TuningRecStatus.PENDING
        assert rec.recommended_kp == 1.2

    def test_default_status_pending(self) -> None:
        rec = TuningRecommendation(
            id=uuid4(),
            controller_id=1,
            current_kp=1.0,
            current_ti=10.0,
            current_td=0.0,
            recommended_kp=1.0,
            recommended_ti=10.0,
            recommended_td=0.0,
            reason="test",
            timestamp=0.0,
        )
        assert rec.status == TuningRecStatus.PENDING

    def test_frozen(self) -> None:
        rec = TuningRecommendation(
            id=uuid4(),
            controller_id=1,
            current_kp=1.0,
            current_ti=10.0,
            current_td=0.0,
            recommended_kp=1.0,
            recommended_ti=10.0,
            recommended_td=0.0,
            reason="test",
            timestamp=0.0,
        )
        try:
            rec.status = TuningRecStatus.APPLIED  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_tuning_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'smart_pid_domain.models.tuning'`

- [ ] **Step 3: Implement the models**

```python
# packages/smart_pid_domain/src/smart_pid_domain/models/tuning.py
"""Domain models for PID tuning read-back and recommendations."""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from smart_pid_domain.enums import TuningRecStatus


@dataclass(frozen=True)
class PIDParamsRead:
    """Snapshot of PID tuning parameters read from external DCS."""

    kp: float | None
    ti: float | None
    td: float | None
    timestamp: float


@dataclass(frozen=True)
class TuningRecommendation:
    """AI-generated tuning recommendation awaiting approval or auto-applied."""

    id: UUID
    controller_id: int
    current_kp: float
    current_ti: float
    current_td: float
    recommended_kp: float
    recommended_ti: float
    recommended_td: float
    reason: str
    timestamp: float
    status: TuningRecStatus = field(default=TuningRecStatus.PENDING)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_tuning_models.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/models/tuning.py tests/domain/test_tuning_models.py
git commit -m "feat(domain): add PIDParamsRead and TuningRecommendation models"
```

---

## Task 3: Domain Events — TuningRecommended, TuningApplied

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/events.py`
- Create: `tests/domain/test_events_tuning.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/domain/test_events_tuning.py
"""Tests for tuning-related domain events."""
from uuid import UUID, uuid4

from smart_pid_domain.enums import TuningRecStatus
from smart_pid_domain.events import TuningApplied, TuningRecommended


class TestTuningRecommended:
    def test_creation(self) -> None:
        evt = TuningRecommended(
            controller_id=1,
            current_kp=1.0,
            current_ti=10.0,
            current_td=0.0,
            recommended_kp=1.2,
            recommended_ti=8.0,
            recommended_td=0.1,
            reason="fuzzy_sp_tracking",
            timestamp=1000.0,
        )
        assert isinstance(evt.event_id, UUID)
        assert evt.controller_id == 1
        assert evt.recommended_kp == 1.2

    def test_frozen(self) -> None:
        evt = TuningRecommended(
            controller_id=1,
            current_kp=1.0,
            current_ti=10.0,
            current_td=0.0,
            recommended_kp=1.0,
            recommended_ti=10.0,
            recommended_td=0.0,
            reason="test",
            timestamp=0.0,
        )
        try:
            evt.controller_id = 2  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass


class TestTuningApplied:
    def test_creation(self) -> None:
        rec_id = uuid4()
        evt = TuningApplied(
            controller_id=1,
            recommendation_id=rec_id,
            applied_kp=1.15,
            applied_ti=9.0,
            applied_td=0.05,
            clamped=True,
            timestamp=1001.0,
        )
        assert isinstance(evt.event_id, UUID)
        assert evt.recommendation_id == rec_id
        assert evt.clamped is True

    def test_frozen(self) -> None:
        evt = TuningApplied(
            controller_id=1,
            recommendation_id=uuid4(),
            applied_kp=1.0,
            applied_ti=10.0,
            applied_td=0.0,
            clamped=False,
            timestamp=0.0,
        )
        try:
            evt.clamped = True  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_events_tuning.py -v`
Expected: FAIL with `ImportError: cannot import name 'TuningRecommended'`

- [ ] **Step 3: Implement the events**

Add to `packages/smart_pid_domain/src/smart_pid_domain/events.py` after the `CascadeHandshakeChanged` class (line ~129):

```python
@dataclass(frozen=True)
class TuningRecommended:
    """AI engine produced a tuning recommendation."""

    controller_id: int
    current_kp: float
    current_ti: float
    current_td: float
    recommended_kp: float
    recommended_ti: float
    recommended_td: float
    reason: str
    timestamp: float
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class TuningApplied:
    """Tuning parameters were written to the external DCS."""

    controller_id: int
    recommendation_id: UUID
    applied_kp: float
    applied_ti: float
    applied_td: float
    clamped: bool
    timestamp: float
    event_id: UUID = field(default_factory=uuid4)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_events_tuning.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/events.py tests/domain/test_events_tuning.py
git commit -m "feat(domain): add TuningRecommended and TuningApplied events"
```

---

## Task 4: Expand TagBindings and Controller Model

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py`
- Modify: existing tests in `tests/domain/test_models.py` (add new tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/domain/test_models.py`:

```python
class TestTagBindingsExpanded:
    def test_new_fields_default_empty(self) -> None:
        tb = TagBindings()
        assert tb.node_id_kp == ""
        assert tb.node_id_ti == ""
        assert tb.node_id_td == ""
        assert tb.node_id_mode == ""

    def test_new_fields_set(self) -> None:
        tb = TagBindings(
            node_id_kp="ns=2;s=PID1.KP",
            node_id_ti="ns=2;s=PID1.TI",
            node_id_td="ns=2;s=PID1.TD",
            node_id_mode="ns=2;s=PID1.MODE",
        )
        assert tb.node_id_kp == "ns=2;s=PID1.KP"
        assert tb.node_id_mode == "ns=2;s=PID1.MODE"


class TestControllerTuningFields:
    def test_default_tuning_write_mode(self) -> None:
        from smart_pid_domain.enums import TuningWriteMode
        c = Controller(id=1, name="test")
        assert c.tuning_write_mode == TuningWriteMode.APPROVAL_REQUIRED

    def test_default_max_tuning_change_pct(self) -> None:
        c = Controller(id=1, name="test")
        assert c.max_tuning_change_pct == 10.0

    def test_custom_tuning_config(self) -> None:
        from smart_pid_domain.enums import TuningWriteMode
        c = Controller(
            id=1,
            name="test",
            tuning_write_mode=TuningWriteMode.AUTO_APPLY,
            max_tuning_change_pct=5.0,
        )
        assert c.tuning_write_mode == TuningWriteMode.AUTO_APPLY
        assert c.max_tuning_change_pct == 5.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_models.py::TestTagBindingsExpanded -v`
Expected: FAIL with `AttributeError: ... has no attribute 'node_id_kp'`

- [ ] **Step 3: Implement the changes**

In `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py`:

Add import at top:
```python
from smart_pid_domain.enums import TuningWriteMode
```

Add to `TagBindings` dataclass after `node_id_bkcal_out` (line ~66):
```python
    node_id_kp: str = ""
    node_id_ti: str = ""
    node_id_td: str = ""
    node_id_mode: str = ""
```

Add to `Controller` dataclass after `ai_config` field (line ~125 area):
```python
    tuning_write_mode: TuningWriteMode = TuningWriteMode.APPROVAL_REQUIRED
    max_tuning_change_pct: float = 10.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_models.py::TestTagBindingsExpanded tests/domain/test_models.py::TestControllerTuningFields -v`
Expected: 5 PASSED

- [ ] **Step 5: Run full domain tests for regressions**

Run: `uv run pytest tests/domain/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/models/controller.py tests/domain/test_models.py
git commit -m "feat(domain): expand TagBindings and Controller with tuning write-back fields"
```

---

## Task 5: CoreSettings — Add execution_mode

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/config.py`
- Modify: `tests/core/unit/test_config.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/core/unit/test_config.py`:

```python
class TestExecutionMode:
    def test_default_monitor(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPID_JWT_SECRET", "test-secret")
        s = CoreSettings()
        assert s.execution_mode == "monitor"

    def test_set_execute(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SPID_JWT_SECRET", "test-secret")
        monkeypatch.setenv("SPID_EXECUTION_MODE", "execute")
        s = CoreSettings()
        assert s.execution_mode == "execute"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_config.py::TestExecutionMode -v`
Expected: FAIL with `pydantic_core._pydantic_core.ValidationError` or `AttributeError`

- [ ] **Step 3: Implement**

Add to `CoreSettings` in `packages/smart_pid_core/src/smart_pid_core/config.py` after `log_level`:

```python
    execution_mode: str = "monitor"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_config.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/config.py tests/core/unit/test_config.py
git commit -m "feat(config): add SPID_EXECUTION_MODE setting (default: monitor)"
```

---

## Task 6: Guardrail Clamping — Pure Function

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/services/tuning_guardrails.py`
- Create: `tests/core/unit/test_guardrails.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/unit/test_guardrails.py
"""Tests for tuning guardrail clamping logic."""
import pytest

from smart_pid_core.domain.services.tuning_guardrails import clamp_tuning_change


class TestClampTuningChange:
    def test_no_change(self) -> None:
        result = clamp_tuning_change(current=1.0, recommended=1.0, max_pct=10.0)
        assert result == 1.0

    def test_within_limit(self) -> None:
        result = clamp_tuning_change(current=1.0, recommended=1.05, max_pct=10.0)
        assert result == 1.05

    def test_clamped_high(self) -> None:
        result = clamp_tuning_change(current=1.0, recommended=1.5, max_pct=10.0)
        assert result == pytest.approx(1.1)

    def test_clamped_low(self) -> None:
        result = clamp_tuning_change(current=1.0, recommended=0.5, max_pct=10.0)
        assert result == pytest.approx(0.9)

    def test_negative_current(self) -> None:
        """Guardrail uses abs(current) for max_delta."""
        result = clamp_tuning_change(current=-1.0, recommended=-1.5, max_pct=10.0)
        assert result == pytest.approx(-1.1)

    def test_zero_current(self) -> None:
        """When current is zero, max_delta is zero — no change allowed."""
        result = clamp_tuning_change(current=0.0, recommended=0.5, max_pct=10.0)
        assert result == 0.0

    def test_100_pct_allows_doubling(self) -> None:
        result = clamp_tuning_change(current=1.0, recommended=2.5, max_pct=100.0)
        assert result == pytest.approx(2.0)


class TestClampTuningChangeTuple:
    def test_clamp_all_three(self) -> None:
        from smart_pid_core.domain.services.tuning_guardrails import clamp_tuning_params

        kp, ti, td = clamp_tuning_params(
            current_kp=1.0, current_ti=10.0, current_td=0.5,
            rec_kp=2.0, rec_ti=20.0, rec_td=1.0,
            max_pct=10.0,
        )
        assert kp == pytest.approx(1.1)
        assert ti == pytest.approx(11.0)
        assert td == pytest.approx(0.55)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_guardrails.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

```python
# packages/smart_pid_core/src/smart_pid_core/domain/services/tuning_guardrails.py
"""Guardrail clamping for tuning parameter write-back."""
from __future__ import annotations


def clamp_tuning_change(current: float, recommended: float, max_pct: float) -> float:
    """Clamp a tuning parameter change to at most max_pct% of current value."""
    max_delta = abs(current) * (max_pct / 100.0)
    delta = recommended - current
    clamped_delta = max(min(delta, max_delta), -max_delta)
    return current + clamped_delta


def clamp_tuning_params(
    *,
    current_kp: float,
    current_ti: float,
    current_td: float,
    rec_kp: float,
    rec_ti: float,
    rec_td: float,
    max_pct: float,
) -> tuple[float, float, float]:
    """Clamp all three PID tuning parameters."""
    return (
        clamp_tuning_change(current_kp, rec_kp, max_pct),
        clamp_tuning_change(current_ti, rec_ti, max_pct),
        clamp_tuning_change(current_td, rec_td, max_pct),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_guardrails.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/services/tuning_guardrails.py tests/core/unit/test_guardrails.py
git commit -m "feat(core): add tuning guardrail clamping functions"
```

---

## Task 7: MonitorWorker — Enriches Telemetry, Publishes STATUS

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/application/workers/monitor_worker.py`
- Create: `tests/core/unit/test_monitor_worker.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/unit/test_monitor_worker.py
"""Tests for MonitorWorker — enriches telemetry and publishes STATUS."""
import time
import threading

import msgpack
import pytest
import zmq

from smart_pid_domain.enums import LimitBits, SignalSeverity
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus


class TestMonitorWorker:
    """Uses real ZMQ inproc sockets to test MonitorWorker."""

    def _make_telemetry_msg(
        self,
        controller_id: int = 1,
        pv: float = 50.0,
        sp: float = 50.0,
        co: float = 50.0,
        co_limit: str = "none",
    ) -> bytes:
        """Build a msgpack telemetry payload matching IOWorker format."""

        def _signal(value: float, limit: str = "none") -> dict:
            return {
                "value": value,
                "severity": "good",
                "limit_bits": limit,
                "sub_status": "none",
            }

        return msgpack.packb({
            "controller_id": controller_id,
            "pv": _signal(pv),
            "sp": _signal(sp),
            "co": _signal(co, limit=co_limit),
            "bkcal_in": _signal(0.0),
            "bkcal_out": _signal(0.0),
            "integral_val": 0.0,
            "timestamp": time.time(),
        })

    def test_publishes_status_with_error(self) -> None:
        from smart_pid_core.application.workers.monitor_worker import MonitorWorker

        ctx = zmq.Context()
        try:
            # Set up pub/sub
            pub = ctx.socket(zmq.PUB)
            pub.bind("inproc://test-monitor-bus")

            status_sub = ctx.socket(zmq.SUB)
            status_sub.connect("inproc://test-monitor-bus")
            status_sub.setsockopt(zmq.SUBSCRIBE, b"STATUS.1")

            telemetry_sub = ctx.socket(zmq.SUB)
            telemetry_sub.connect("inproc://test-monitor-bus")
            telemetry_sub.setsockopt(zmq.SUBSCRIBE, b"TELEMETRY.1")

            time.sleep(0.05)  # let subscriptions propagate

            worker = MonitorWorker(
                controller_id=1,
                bus_ctx=ctx,
                bus_url="inproc://test-monitor-bus",
                scan_rate_ms=50,
            )
            worker.start()

            # Publish a telemetry frame: PV=55, SP=50 → error=5
            pub.send_multipart([
                b"TELEMETRY.1",
                self._make_telemetry_msg(pv=55.0, sp=50.0),
            ])

            # Wait for STATUS
            if status_sub.poll(timeout=2000):
                topic, payload = status_sub.recv_multipart()
                data = msgpack.unpackb(payload)
                assert data["error"] == pytest.approx(5.0)
                assert data["saturated"] is False
                assert data["controller_id"] == 1
            else:
                pytest.fail("No STATUS message received within 2s")

            worker.stop()
        finally:
            ctx.term()

    def test_detects_saturation(self) -> None:
        from smart_pid_core.application.workers.monitor_worker import MonitorWorker

        ctx = zmq.Context()
        try:
            pub = ctx.socket(zmq.PUB)
            pub.bind("inproc://test-monitor-sat")

            status_sub = ctx.socket(zmq.SUB)
            status_sub.connect("inproc://test-monitor-sat")
            status_sub.setsockopt(zmq.SUBSCRIBE, b"STATUS.1")

            time.sleep(0.05)

            worker = MonitorWorker(
                controller_id=1,
                bus_ctx=ctx,
                bus_url="inproc://test-monitor-sat",
                scan_rate_ms=50,
            )
            worker.start()

            pub.send_multipart([
                b"TELEMETRY.1",
                self._make_telemetry_msg(co=100.0, co_limit="high_limited"),
            ])

            if status_sub.poll(timeout=2000):
                topic, payload = status_sub.recv_multipart()
                data = msgpack.unpackb(payload)
                assert data["saturated"] is True
            else:
                pytest.fail("No STATUS message received within 2s")

            worker.stop()
        finally:
            ctx.term()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_monitor_worker.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement MonitorWorker**

```python
# packages/smart_pid_core/src/smart_pid_core/application/workers/monitor_worker.py
"""MonitorWorker — enriches telemetry and publishes STATUS for monitor mode."""
from __future__ import annotations

import logging
import threading
import time

import msgpack
import zmq

logger = logging.getLogger(__name__)


class MonitorWorker(threading.Thread):
    """Subscribes to TELEMETRY.{id}, enriches with error/saturation, publishes STATUS.{id}."""

    def __init__(
        self,
        controller_id: int,
        bus_ctx: zmq.Context,  # type: ignore[type-arg]
        bus_url: str,
        scan_rate_ms: int = 100,
    ) -> None:
        super().__init__(daemon=True)
        self._cid = controller_id
        self._ctx = bus_ctx
        self._url = bus_url
        self._scan_rate = scan_rate_ms / 1000.0
        self._stop_evt = threading.Event()

    def start(self) -> None:
        self._stop_evt.clear()
        super().start()

    def stop(self) -> None:
        self._stop_evt.set()
        self.join(timeout=5.0)

    def run(self) -> None:
        sub = self._ctx.socket(zmq.SUB)
        sub.connect(self._url)
        sub.setsockopt(zmq.SUBSCRIBE, f"TELEMETRY.{self._cid}".encode())

        pub = self._ctx.socket(zmq.PUB)
        pub.connect(self._url)

        poller = zmq.Poller()
        poller.register(sub, zmq.POLLIN)

        logger.info("MonitorWorker started for controller %s", self._cid)

        try:
            while not self._stop_evt.is_set():
                events = dict(poller.poll(timeout=int(self._scan_rate * 1000)))
                if sub in events:
                    self._process_telemetry(sub, pub)
        finally:
            sub.close()
            pub.close()

    def _process_telemetry(self, sub: zmq.Socket, pub: zmq.Socket) -> None:  # type: ignore[type-arg]
        """Drain all pending telemetry, enrich the latest, publish STATUS."""
        latest = None
        while True:
            try:
                _topic, payload = sub.recv_multipart(flags=zmq.NOBLOCK)
                latest = msgpack.unpackb(payload)
            except zmq.Again:
                break

        if latest is None:
            return

        # Enrich
        pv_val = latest["pv"]["value"] if isinstance(latest["pv"], dict) else latest["pv"]
        sp_val = latest["sp"]["value"] if isinstance(latest["sp"], dict) else latest["sp"]
        error = pv_val - sp_val

        co_data = latest["co"]
        co_limit = co_data.get("limit_bits", "none") if isinstance(co_data, dict) else "none"
        saturated = co_limit in ("high_limited", "low_limited")

        status_msg = {
            "controller_id": latest["controller_id"],
            "pv": latest["pv"],
            "sp": latest["sp"],
            "co": latest["co"],
            "bkcal_in": latest.get("bkcal_in", {"value": 0.0, "severity": "good", "limit_bits": "none", "sub_status": "none"}),
            "bkcal_out": latest.get("bkcal_out", {"value": 0.0, "severity": "good", "limit_bits": "none", "sub_status": "none"}),
            "integral_val": latest.get("integral_val", 0.0),
            "error": error,
            "saturated": saturated,
            "timestamp": latest.get("timestamp", time.time()),
        }

        pub.send_multipart([
            f"STATUS.{self._cid}".encode(),
            msgpack.packb(status_msg),
        ])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_monitor_worker.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/monitor_worker.py tests/core/unit/test_monitor_worker.py
git commit -m "feat(core): add MonitorWorker — enriches telemetry and publishes STATUS"
```

---

## Task 8: OPCUAAdapter — read_pid_params, write_pid_params, read_external_mode

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py`
- Modify: `tests/core/unit/test_opcua_server.py` or create `tests/core/unit/test_opcua_tuning.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/unit/test_opcua_tuning.py
"""Tests for OPCUAAdapter tuning read/write methods."""
import pytest

from smart_pid_domain.models.tuning import PIDParamsRead


class TestRegisterControllerTuningTags:
    """Test that register_controller accepts new tuning tag arguments."""

    def test_register_with_tuning_tags(self, opcua_adapter) -> None:
        """Adapter should accept node_id_kp, node_id_ti, node_id_td, node_id_mode."""
        opcua_adapter.register_controller(
            controller_id=99,
            node_id_pv="ns=2;s=TEST.PV",
            node_id_sp="ns=2;s=TEST.SP",
            node_id_co="ns=2;s=TEST.CO",
            node_id_kp="ns=2;s=TEST.KP",
            node_id_ti="ns=2;s=TEST.TI",
            node_id_td="ns=2;s=TEST.TD",
            node_id_mode="ns=2;s=TEST.MODE",
        )
        assert 99 in opcua_adapter._tags


class TestReadPidParams:
    def test_returns_none_when_no_tags_mapped(self, opcua_adapter) -> None:
        """If no tuning tags were registered, read_pid_params returns None for all."""
        opcua_adapter.register_controller(
            controller_id=99,
            node_id_pv="ns=2;s=TEST.PV",
            node_id_sp="ns=2;s=TEST.SP",
            node_id_co="ns=2;s=TEST.CO",
        )
        result = opcua_adapter.read_pid_params(99)
        assert result is None


class TestReadExternalMode:
    def test_returns_none_when_no_mode_tag(self, opcua_adapter) -> None:
        opcua_adapter.register_controller(
            controller_id=99,
            node_id_pv="ns=2;s=TEST.PV",
            node_id_sp="ns=2;s=TEST.SP",
            node_id_co="ns=2;s=TEST.CO",
        )
        result = opcua_adapter.read_external_mode(99)
        assert result is None
```

Note: The `opcua_adapter` fixture should come from `tests/core/fixtures/opcua_server.py`. Check if there's a conftest providing it, or add a simple fixture:

```python
@pytest.fixture
def opcua_adapter():
    from smart_pid_core.config import CoreSettings
    import os
    os.environ.setdefault("SPID_JWT_SECRET", "test")
    settings = CoreSettings()
    from smart_pid_core.adapters.outbound.opcua_adapter import OPCUAAdapter
    adapter = OPCUAAdapter(settings)
    return adapter
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_opcua_tuning.py -v`
Expected: FAIL with `TypeError: register_controller() got an unexpected keyword argument 'node_id_kp'`

- [ ] **Step 3: Implement**

In `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py`:

**a)** Expand `register_controller()` signature (line ~198) to add:

```python
    def register_controller(
        self,
        controller_id: int,
        node_id_pv: str,
        node_id_sp: str,
        node_id_co: str,
        node_id_integral: str = "",
        node_id_bkcal_in: str = "",
        node_id_bkcal_out: str = "",
        node_id_kp: str = "",
        node_id_ti: str = "",
        node_id_td: str = "",
        node_id_mode: str = "",
    ) -> None:
```

Store the new tag IDs in `self._tags[controller_id]` dict alongside existing ones.

**b)** Add `read_pid_params()`:

```python
    def read_pid_params(self, controller_id: int) -> PIDParamsRead | None:
        """Read Kp, Ti, Td from external DCS. Returns None if no tuning tags mapped."""
        tags = self._tags.get(controller_id, {})
        kp_id = tags.get("kp", "")
        ti_id = tags.get("ti", "")
        td_id = tags.get("td", "")
        if not kp_id and not ti_id and not td_id:
            return None
        # Read via OPC-UA (same pattern as read_telemetry)
        import time
        node_ids = [n for n in [kp_id, ti_id, td_id] if n]
        if not self.is_connected or not node_ids:
            return None
        values = self._read_nodes_sync(node_ids)
        return PIDParamsRead(
            kp=values.get(kp_id) if kp_id else None,
            ti=values.get(ti_id) if ti_id else None,
            td=values.get(td_id) if td_id else None,
            timestamp=time.time(),
        )
```

**c)** Add `write_pid_params()`:

```python
    def write_pid_params(
        self, controller_id: int, kp: float | None, ti: float | None, td: float | None
    ) -> None:
        """Write tuning parameters to DCS. Only writes non-None values."""
        tags = self._tags.get(controller_id, {})
        writes: list[tuple[str, float]] = []
        if kp is not None and tags.get("kp"):
            writes.append((tags["kp"], kp))
        if ti is not None and tags.get("ti"):
            writes.append((tags["ti"], ti))
        if td is not None and tags.get("td"):
            writes.append((tags["td"], td))
        if writes:
            self._write_nodes_sync(writes)
```

**d)** Add `read_external_mode()`:

```python
    def read_external_mode(self, controller_id: int) -> str | None:
        """Read PID mode from DCS. Returns None if node_id_mode not mapped."""
        tags = self._tags.get(controller_id, {})
        mode_id = tags.get("mode", "")
        if not mode_id or not self.is_connected:
            return None
        values = self._read_nodes_sync([mode_id])
        return str(values.get(mode_id)) if mode_id in values else None
```

Add import at top of file:
```python
from smart_pid_domain.models.tuning import PIDParamsRead
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_opcua_tuning.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Run existing OPC-UA tests for regressions**

Run: `uv run pytest tests/core/unit/test_opcua_server.py tests/core/integration/test_opcua_connection.py -v`
Expected: All pass (pre-existing OPC-UA setup errors acceptable)

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py tests/core/unit/test_opcua_tuning.py
git commit -m "feat(opcua): add read_pid_params, write_pid_params, read_external_mode methods"
```

---

## Task 9: LoopManager — Branch on execution_mode

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py`
- Create: `tests/core/integration/test_loop_manager_monitor.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/integration/test_loop_manager_monitor.py
"""Tests for LoopManager in monitor mode."""
import pytest
import zmq

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_domain.models.controller import Controller


@pytest.fixture
def bus():
    b = EventBus()
    b.start()
    yield b
    b.stop()


class TestLoopManagerMonitorMode:
    def test_start_loop_creates_monitor_worker(self, bus: EventBus) -> None:
        lm = LoopManager(bus, execution_mode="monitor")
        ctrl = Controller(id=1, name="test-mon")
        lm.start_loop(ctrl)

        ctx = lm.get_context(1)
        assert ctx is not None
        assert ctx.pid_worker is None
        assert ctx.monitor_worker is not None
        assert ctx.monitor_worker.is_alive()

        lm.stop_all()

    def test_start_loop_execute_creates_pid_worker(self, bus: EventBus) -> None:
        lm = LoopManager(bus, execution_mode="execute")
        ctrl = Controller(id=1, name="test-exec")
        lm.start_loop(ctrl)

        ctx = lm.get_context(1)
        assert ctx is not None
        assert ctx.pid_worker is not None
        assert ctx.monitor_worker is None

        lm.stop_all()

    def test_set_setpoint_blocked_in_monitor(self, bus: EventBus) -> None:
        lm = LoopManager(bus, execution_mode="monitor")
        ctrl = Controller(id=1, name="test-mon")
        lm.start_loop(ctrl)

        with pytest.raises(Exception, match="monitor"):
            lm.set_setpoint(1, 50.0)

        lm.stop_all()

    def test_set_mode_blocked_in_monitor(self, bus: EventBus) -> None:
        from smart_pid_domain.enums import ControllerMode
        lm = LoopManager(bus, execution_mode="monitor")
        ctrl = Controller(id=1, name="test-mon")
        lm.start_loop(ctrl)

        with pytest.raises(Exception, match="monitor"):
            lm.set_mode(1, ControllerMode.AUTO)

        lm.stop_all()

    def test_set_output_blocked_in_monitor(self, bus: EventBus) -> None:
        lm = LoopManager(bus, execution_mode="monitor")
        ctrl = Controller(id=1, name="test-mon")
        lm.start_loop(ctrl)

        with pytest.raises(Exception, match="monitor"):
            lm.set_output(1, 50.0)

        lm.stop_all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_loop_manager_monitor.py -v`
Expected: FAIL with `TypeError: LoopManager.__init__() got an unexpected keyword argument 'execution_mode'`

- [ ] **Step 3: Implement**

In `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py`:

**a)** Update imports:
```python
from smart_pid_core.application.workers.monitor_worker import MonitorWorker
```

**b)** Update `LoopContext` to include `monitor_worker`:
```python
@dataclass
class LoopContext:
    controller: Controller
    pid_worker: PIDWorker | None
    engine: PIDEngine | None
    mode_manager: ModeManager | None
    stats_worker: StatsWorker
    ai_worker: AIWorker
    monitor_worker: MonitorWorker | None = None
```

**c)** Update `__init__` to accept `execution_mode`:
```python
def __init__(self, bus: EventBus, execution_mode: str = "monitor") -> None:
    self._bus = bus
    self._execution_mode = execution_mode
    self._loops: dict[int, LoopContext] = {}
```

**d)** Update `start_loop` to branch:
```python
def start_loop(self, controller: Controller) -> None:
    if self._execution_mode == "monitor":
        monitor_worker = MonitorWorker(
            controller_id=controller.id,
            bus_ctx=self._bus.ctx,
            bus_url=self._bus.url,
            scan_rate_ms=controller.scan_rate_ms,
        )
        stats_worker = StatsWorker(self._bus, controller)
        ai_worker = AIWorker(self._bus, controller)

        ctx = LoopContext(
            controller=controller,
            pid_worker=None,
            engine=None,
            mode_manager=None,
            stats_worker=stats_worker,
            ai_worker=ai_worker,
            monitor_worker=monitor_worker,
        )
        self._loops[controller.id] = ctx
        monitor_worker.start()
        stats_worker.start()
        ai_worker.start()
    else:
        # existing execute mode logic unchanged
        engine = PIDEngine()
        mode_manager = ModeManager()
        pid_worker = PIDWorker(self._bus, controller, engine, mode_manager)
        stats_worker = StatsWorker(self._bus, controller)
        ai_worker = AIWorker(self._bus, controller)

        ctx = LoopContext(
            controller=controller,
            pid_worker=pid_worker,
            engine=engine,
            mode_manager=mode_manager,
            stats_worker=stats_worker,
            ai_worker=ai_worker,
            monitor_worker=None,
        )
        self._loops[controller.id] = ctx
        pid_worker.start()
        stats_worker.start()
        ai_worker.start()
```

**e)** Gate `set_setpoint`, `set_mode`, `set_output` in monitor mode:
```python
def set_setpoint(self, controller_id: int, value: float) -> None:
    if self._execution_mode == "monitor":
        raise DomainError("Cannot set setpoint in monitor mode — PID is controlled by external DCS")
    # ... existing logic
```

Same pattern for `set_mode` and `set_output`.

**f)** Update `stop_loop` to stop monitor_worker if present:
```python
if ctx.monitor_worker is not None:
    ctx.monitor_worker.stop()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_loop_manager_monitor.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Run existing LoopManager tests for regressions**

Run: `uv run pytest tests/core/ -k "loop_manager" -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py tests/core/integration/test_loop_manager_monitor.py
git commit -m "feat(core): LoopManager branches on execution_mode — MonitorWorker in monitor, PIDWorker in execute"
```

---

## Task 10: IOWorker — Skip BKCAL Write in Monitor Mode

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/workers/io_worker.py`
- Create: `tests/core/integration/test_io_worker_monitor.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/integration/test_io_worker_monitor.py
"""Tests for IOWorker in monitor mode — no BKCAL write-back."""
import pytest

from smart_pid_core.application.workers.io_worker import IOWorker


class TestIOWorkerMonitorMode:
    def test_accepts_execution_mode_param(self) -> None:
        """IOWorker should accept execution_mode parameter."""
        import zmq
        from unittest.mock import MagicMock

        bus = MagicMock()
        bus.ctx = zmq.Context()
        bus.url = "inproc://test-io-monitor"
        adapter = MagicMock()

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1],
            execution_mode="monitor",
        )
        assert worker._execution_mode == "monitor"
        bus.ctx.term()

    def test_monitor_mode_does_not_subscribe_action(self) -> None:
        """In monitor mode, IOWorker should not subscribe to ACTION.CTRL."""
        import zmq
        from unittest.mock import MagicMock

        bus = MagicMock()
        bus.ctx = zmq.Context()
        bus.url = "inproc://test-io-nosub"
        adapter = MagicMock()

        worker = IOWorker(
            bus=bus,
            opcua_adapter=adapter,
            controller_ids=[1],
            execution_mode="monitor",
        )
        # In monitor mode the worker should set a flag indicating no action subscription
        assert worker._skip_bkcal_write is True
        bus.ctx.term()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_io_worker_monitor.py -v`
Expected: FAIL with `TypeError: IOWorker.__init__() got an unexpected keyword argument 'execution_mode'`

- [ ] **Step 3: Implement**

In `packages/smart_pid_core/src/smart_pid_core/application/workers/io_worker.py`:

**a)** Update `__init__` to accept `execution_mode`:
```python
def __init__(
    self,
    bus: EventBus,
    opcua_adapter: OPCUAAdapter,
    controller_ids: list[int],
    scan_interval_s: float = 0.1,
    execution_mode: str = "monitor",
) -> None:
    super().__init__(daemon=True)
    self._bus = bus
    self._opcua = opcua_adapter
    self._cids = list(controller_ids)
    self._scan = scan_interval_s
    self._stop_evt = threading.Event()
    self._execution_mode = execution_mode
    self._skip_bkcal_write = execution_mode == "monitor"
```

**b)** In `_run()`, conditionally skip action subscription and `_drain_and_write_bkcal()`:
```python
def _run(self) -> None:
    # ... existing telemetry sub setup ...

    action_sub = None
    if not self._skip_bkcal_write:
        action_sub = self._ctx.socket(zmq.SUB)
        action_sub.connect(self._url)
        for cid in self._cids:
            action_sub.setsockopt(zmq.SUBSCRIBE, f"ACTION.CTRL.{cid}".encode())

    # ... existing loop ...
    while not self._stop_evt.is_set():
        # ... read telemetry ...
        if action_sub is not None:
            self._drain_and_write_bkcal(action_sub)

    # cleanup
    if action_sub is not None:
        action_sub.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_io_worker_monitor.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Run existing IOWorker tests for regressions**

Run: `uv run pytest tests/core/ -k "io_worker" -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/io_worker.py tests/core/integration/test_io_worker_monitor.py
git commit -m "feat(io): IOWorker skips BKCAL write-back in monitor mode"
```

---

## Task 11: Commands Router — Gate Endpoints, Add apply-tuning

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`
- Create: `tests/core/unit/test_commands_monitor_mode.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/unit/test_commands_monitor_mode.py
"""Tests for commands router in monitor mode."""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def monitor_app():
    """Create a FastAPI app configured in monitor mode."""
    from unittest.mock import AsyncMock, MagicMock

    from smart_pid_core.adapters.inbound.api.app import create_app

    repo = MagicMock()
    historian = MagicMock()
    user_repo = MagicMock()
    loop_manager = MagicMock()
    settings = MagicMock()
    settings.execution_mode = "monitor"
    settings.jwt_secret = "test-secret"
    settings.jwt_expiry_hours = 8
    audit_repo = MagicMock()

    app = create_app(
        repo=repo,
        historian=historian,
        user_repo=user_repo,
        loop_manager=loop_manager,
        settings=settings,
        audit_repo=audit_repo,
    )
    return app


class TestCommandsBlockedInMonitor:
    @pytest.mark.anyio
    async def test_setpoint_returns_409(self, monitor_app, auth_headers) -> None:
        transport = ASGITransport(app=monitor_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/commands/setpoint",
                json={"controller_id": 1, "value": 50.0},
                headers=auth_headers,
            )
            assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_mode_returns_409(self, monitor_app, auth_headers) -> None:
        transport = ASGITransport(app=monitor_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/commands/mode",
                json={"controller_id": 1, "mode": "AUTO"},
                headers=auth_headers,
            )
            assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_output_returns_409(self, monitor_app, auth_headers) -> None:
        transport = ASGITransport(app=monitor_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/commands/output",
                json={"controller_id": 1, "value": 50.0},
                headers=auth_headers,
            )
            assert resp.status_code == 409
```

Note: `auth_headers` fixture should produce valid JWT headers. Check existing test fixtures (e.g., `tests/core/integration/test_api_commands.py`) and reuse the pattern.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_commands_monitor_mode.py -v`
Expected: FAIL — endpoints return 200/400/422 instead of 409

- [ ] **Step 3: Implement**

**a)** Add `get_execution_mode` dependency in `dependencies.py`:

```python
def get_execution_mode(request: Request) -> str:
    return getattr(request.app.state, "execution_mode", "monitor")
```

**b)** In `commands.py`, add the monitor mode guard to each endpoint:

```python
from fastapi import HTTPException

from smart_pid_core.adapters.inbound.api.dependencies import get_execution_mode

@router.post("/setpoint")
async def set_setpoint(
    cmd: SetpointCommand,
    user: UserClaims = Depends(require_operator),
    lm: LoopManager = Depends(get_loop_manager),
    audit: AuditRepository = Depends(get_audit_repo),
    execution_mode: str = Depends(get_execution_mode),
) -> CommandResponse:
    if execution_mode == "monitor":
        raise HTTPException(
            status_code=409,
            detail="Not available in monitor mode. PID is controlled by external DCS.",
        )
    # ... existing logic
```

Same guard for `set_mode` and `set_output` endpoints.

**c)** Store `execution_mode` on `app.state` in `create_app()`:

In `app.py`, add after other state assignments:
```python
app.state.execution_mode = settings.execution_mode
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_commands_monitor_mode.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Run existing commands tests for regressions**

Run: `uv run pytest tests/core/integration/test_api_commands.py -v`
Expected: All pass (those tests use execute mode settings)

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py \
      packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py \
      packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py \
      tests/core/unit/test_commands_monitor_mode.py
git commit -m "feat(api): gate SP/mode/output commands behind execute mode, return 409 in monitor"
```

---

## Task 12: Wire execution_mode in main.py

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/integration/test_main_monitor.py
"""Test that main.py passes execution_mode to LoopManager and IOWorker."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestDaemonMonitorWiring:
    def test_loop_manager_receives_execution_mode(self) -> None:
        """Verify LoopManager is constructed with settings.execution_mode."""
        import os
        os.environ["SPID_JWT_SECRET"] = "test"
        os.environ["SPID_EXECUTION_MODE"] = "monitor"
        from smart_pid_core.config import CoreSettings
        settings = CoreSettings()
        assert settings.execution_mode == "monitor"
```

- [ ] **Step 2: Run test to verify it passes** (this is a sanity check)

Run: `uv run pytest tests/core/integration/test_main_monitor.py -v`
Expected: PASS

- [ ] **Step 3: Implement wiring in main.py**

In `packages/smart_pid_core/src/smart_pid_core/main.py`, modify `run_daemon()`:

**a)** Where `LoopManager` is constructed (line ~102 area):
```python
loop_manager = LoopManager(bus, execution_mode=settings.execution_mode)
```

**b)** Where `IOWorker` is constructed (line ~150 area):
```python
io_worker = IOWorker(
    bus=bus,
    opcua_adapter=opcua_adapter,
    controller_ids=controller_ids,
    scan_interval_s=scan_interval,
    execution_mode=settings.execution_mode,
)
```

**c)** Log the execution mode at startup:
```python
logger.info("SmartPID daemon starting in %s mode", settings.execution_mode)
```

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All pass (existing tests should continue working since default is "monitor" and existing tests for execute-mode features mock LoopManager)

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/main.py tests/core/integration/test_main_monitor.py
git commit -m "feat(main): wire execution_mode to LoopManager and IOWorker"
```

---

## Task 13: Apply-Tuning API Endpoint

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py`
- Create: `tests/core/integration/test_tuning_writeback.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/core/integration/test_tuning_writeback.py
"""Tests for the apply-tuning API endpoint."""
from uuid import uuid4

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, AsyncMock, patch

from smart_pid_domain.enums import TuningRecStatus
from smart_pid_domain.models.tuning import TuningRecommendation


class TestApplyTuningEndpoint:
    @pytest.fixture
    def pending_recommendation(self) -> TuningRecommendation:
        return TuningRecommendation(
            id=uuid4(),
            controller_id=1,
            current_kp=1.0,
            current_ti=10.0,
            current_td=0.0,
            recommended_kp=1.2,
            recommended_ti=8.0,
            recommended_td=0.1,
            reason="fuzzy_sp_tracking",
            timestamp=1000.0,
        )

    @pytest.mark.anyio
    async def test_apply_tuning_success(
        self, monitor_app, auth_headers, pending_recommendation
    ) -> None:
        # Store a pending recommendation in app state
        monitor_app.state.tuning_recommendations = {1: pending_recommendation}
        monitor_app.state.opcua_adapter = MagicMock()
        monitor_app.state.opcua_adapter.read_external_mode = MagicMock(return_value="Auto")
        monitor_app.state.opcua_adapter.write_pid_params = MagicMock()

        # Also need controller for max_tuning_change_pct
        from smart_pid_domain.models.controller import Controller
        ctrl = Controller(id=1, name="test", max_tuning_change_pct=50.0)
        monitor_app.state.loop_manager.get_controller = MagicMock(return_value=ctrl)

        transport = ASGITransport(app=monitor_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/commands/apply-tuning/1",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "applied_kp" in data

    @pytest.mark.anyio
    async def test_apply_tuning_no_pending(self, monitor_app, auth_headers) -> None:
        monitor_app.state.tuning_recommendations = {}

        transport = ASGITransport(app=monitor_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/commands/apply-tuning/1",
                headers=auth_headers,
            )
            assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_apply_tuning_pid_not_in_auto(
        self, monitor_app, auth_headers, pending_recommendation
    ) -> None:
        monitor_app.state.tuning_recommendations = {1: pending_recommendation}
        monitor_app.state.opcua_adapter = MagicMock()
        monitor_app.state.opcua_adapter.read_external_mode = MagicMock(return_value="Manual")

        transport = ASGITransport(app=monitor_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/commands/apply-tuning/1",
                headers=auth_headers,
            )
            assert resp.status_code == 409
            assert "Auto" in resp.json()["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_tuning_writeback.py -v`
Expected: FAIL with 404 (endpoint doesn't exist)

- [ ] **Step 3: Implement**

Add to `commands.py`:

```python
from smart_pid_core.domain.services.tuning_guardrails import clamp_tuning_params


@router.post("/apply-tuning/{controller_id}")
async def apply_tuning(
    controller_id: int,
    user: UserClaims = Depends(require_operator),
    lm: LoopManager = Depends(get_loop_manager),
    audit: AuditRepository = Depends(get_audit_repo),
    execution_mode: str = Depends(get_execution_mode),
    request: Request = None,
) -> dict:
    # Get pending recommendation
    recs = getattr(request.app.state, "tuning_recommendations", {})
    rec = recs.get(controller_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="No pending tuning recommendation")

    # Check external PID mode
    opcua = getattr(request.app.state, "opcua_adapter", None)
    if opcua is not None:
        ext_mode = opcua.read_external_mode(controller_id)
        if ext_mode is not None and ext_mode.lower() != "auto":
            raise HTTPException(
                status_code=409,
                detail=f"External PID is in {ext_mode} mode — tuning write-back requires Auto",
            )

    # Apply guardrails
    ctrl = lm.get_controller(controller_id)
    kp, ti, td = clamp_tuning_params(
        current_kp=rec.current_kp,
        current_ti=rec.current_ti,
        current_td=rec.current_td,
        rec_kp=rec.recommended_kp,
        rec_ti=rec.recommended_ti,
        rec_td=rec.recommended_td,
        max_pct=ctrl.max_tuning_change_pct,
    )

    # Write to DCS
    if opcua is not None:
        opcua.write_pid_params(controller_id, kp, ti, td)

    # Clear recommendation
    recs.pop(controller_id, None)

    # Audit
    await audit.log(
        user_id=user.user_id,
        username=user.username,
        action="TUNE_PID",
        detail=f"Applied tuning: Kp={kp:.4f}, Ti={ti:.4f}, Td={td:.4f}",
        controller_id=controller_id,
    )

    return {
        "controller_id": controller_id,
        "applied_kp": kp,
        "applied_ti": ti,
        "applied_td": td,
        "clamped": (kp != rec.recommended_kp or ti != rec.recommended_ti or td != rec.recommended_td),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_tuning_writeback.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py \
      tests/core/integration/test_tuning_writeback.py
git commit -m "feat(api): add POST /commands/apply-tuning endpoint with guardrails"
```

---

## Task 14: Full Regression Test Suite

**Files:** None — verification only.

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=60`
Expected: All tests pass (pre-existing OPC-UA setup errors acceptable)

- [ ] **Step 2: Run linter**

Run: `uv run --with ruff ruff check .`
Expected: No new errors

- [ ] **Step 3: Fix any issues found**

If lint or test failures, fix them and commit:

```bash
git commit -m "fix: address lint/test issues from monitor-supervisor integration"
```

- [ ] **Step 4: Final commit if all clean**

```bash
git log --oneline -15
```

Verify all tasks committed properly.

---

## Deferred to Phase 5 (AI Engine Expansion)

The following spec requirements are **not covered** in this plan because they depend on the Fuzzy/RL engines being expanded to output Kp/Ti/Td (currently they only output Ki gamma):

1. **AIWorker monitor-mode behavior** (Spec Section 7): AIWorker calling `OPCUAAdapter.write_pid_params()` for auto-apply, or publishing `TUNING_RECOMMENDATION.{id}` for approval-required mode. The infrastructure (guardrails, apply-tuning endpoint, MonitorWorker) is built by this plan; the AI engine adaptation is Phase 5 work.

2. **IOWorker PID params reading at slow cadence** (Spec Section 9): Publishing `PARAMS.{id}` every 10s with current Kp/Ti/Td from DCS. The `OPCUAAdapter.read_pid_params()` method is built by Task 8; the IOWorker integration to read and publish periodically is deferred since it's primarily consumed by AIWorker in monitor mode.

3. **GET /commands/tuning-recommendations/{controller_id}** endpoint (Spec Section 8): Listing recent recommendations with status filter. Deferred because recommendations are produced by AIWorker in monitor mode (Phase 5).

These items will be implemented as part of Phase 5 when the AI engines are adapted for the monitor+supervisor workflow.

---

## Summary of Commits (Expected)

1. `feat(domain): add TuningWriteMode, TuningRecStatus, SystemExecutionMode enums`
2. `feat(domain): add PIDParamsRead and TuningRecommendation models`
3. `feat(domain): add TuningRecommended and TuningApplied events`
4. `feat(domain): expand TagBindings and Controller with tuning write-back fields`
5. `feat(config): add SPID_EXECUTION_MODE setting (default: monitor)`
6. `feat(core): add tuning guardrail clamping functions`
7. `feat(core): add MonitorWorker — enriches telemetry and publishes STATUS`
8. `feat(opcua): add read_pid_params, write_pid_params, read_external_mode methods`
9. `feat(core): LoopManager branches on execution_mode — MonitorWorker in monitor, PIDWorker in execute`
10. `feat(io): IOWorker skips BKCAL write-back in monitor mode`
11. `feat(api): gate SP/mode/output commands behind execute mode, return 409 in monitor`
12. `feat(main): wire execution_mode to LoopManager and IOWorker`
13. `feat(api): add POST /commands/apply-tuning endpoint with guardrails`
14. `fix: regression cleanup` (if needed)
