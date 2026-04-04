# FF Signals & BKCAL Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Foundation Fieldbus signal semantics (value+status+timestamp) to all process signals and implement BKCAL_IN/BKCAL_OUT for directional anti-windup and cascade handshake.

**Architecture:** Bottom-up approach — domain models first (FFSignal, new enums), then PID engine (directional anti-windup, IMAN tracking, BKCAL_OUT), then mode manager (cascade handshake), then workers/adapters. Each task produces a testable, committable unit.

**Tech Stack:** Python 3.13, frozen dataclasses, StrEnum, pytest, velocity-form PID

**Spec:** `docs/superpowers/specs/2026-04-04-ff-signals-bkcal-design.md`

---

## File Structure

### New Files
- `packages/smart_pid_domain/src/smart_pid_domain/models/signal.py` — FFSignalStatus + FFSignal value objects
- `tests/domain/test_signal.py` — Unit tests for FFSignal and FFSignalStatus
- `tests/core/unit/test_cascade_handshake.py` — Unit tests for cascade handshake evaluation

### Modified Files
- `packages/smart_pid_domain/src/smart_pid_domain/enums.py` — Add SignalSeverity, LimitBits, InitSubStatus; deprecate SignalStatus
- `packages/smart_pid_domain/src/smart_pid_domain/models/__init__.py` — Export FFSignal, FFSignalStatus
- `packages/smart_pid_domain/src/smart_pid_domain/models/telemetry.py` — Update TelemetryFrame, ControlAction to use FFSignal
- `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py` — Add BKCAL node IDs to TagBindings
- `packages/smart_pid_domain/src/smart_pid_domain/events.py` — Update ControlActionComputed, add CascadeHandshakeChanged
- `packages/smart_pid_core/src/smart_pid_core/domain/services/pid_engine.py` — FFSignal inputs, directional anti-windup, IMAN tracking, BKCAL_OUT
- `packages/smart_pid_core/src/smart_pid_core/domain/services/pid_mode_manager.py` — Cascade handshake, updated BlockStatus, new forced transitions
- `packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py` — Propagate FFSignal, cascade handshake loop, BKCAL_OUT publish
- `packages/smart_pid_core/src/smart_pid_core/application/workers/io_worker.py` — Serialize FFSignal to msgpack
- `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py` — Read DataValue with StatusCode decoding, write BKCAL_OUT
- `tests/core/unit/test_pid_engine.py` — Update existing tests, add directional anti-windup + IMAN tracking tests
- `tests/core/unit/test_pid_mode_manager.py` — Update existing tests, add cascade handshake tests
- `tests/domain/test_models.py` — Update TelemetryFrame/ControlAction tests
- `tests/domain/test_events.py` — Update ControlActionComputed tests, add CascadeHandshakeChanged

---

## Task 1: New Enums — SignalSeverity, LimitBits, InitSubStatus

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/enums.py:52-55`
- Test: `tests/domain/test_signal.py` (create)

- [ ] **Step 1: Write failing tests for new enums**

Create `tests/domain/test_signal.py`:

```python
"""Tests for FF signal enums and value objects."""
from __future__ import annotations

from smart_pid_domain.enums import InitSubStatus, LimitBits, SignalSeverity


class TestSignalSeverity:
    def test_values(self) -> None:
        assert SignalSeverity.GOOD == "GOOD"
        assert SignalSeverity.UNCERTAIN == "UNCERTAIN"
        assert SignalSeverity.BAD == "BAD"

    def test_is_str_enum(self) -> None:
        assert isinstance(SignalSeverity.GOOD, str)


class TestLimitBits:
    def test_values(self) -> None:
        assert LimitBits.NONE == "NONE"
        assert LimitBits.LOW_LIMITED == "LOW_LIMITED"
        assert LimitBits.HIGH_LIMITED == "HIGH_LIMITED"
        assert LimitBits.CONSTANT == "CONSTANT"


class TestInitSubStatus:
    def test_values(self) -> None:
        assert InitSubStatus.NONE == "NONE"
        assert InitSubStatus.NI == "NI"
        assert InitSubStatus.IR == "IR"
        assert InitSubStatus.IA == "IA"
        assert InitSubStatus.GOOD_CASCADE == "GOOD_CASCADE"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_signal.py -v`
Expected: FAIL with `ImportError: cannot import name 'SignalSeverity'`

- [ ] **Step 3: Implement new enums**

In `packages/smart_pid_domain/src/smart_pid_domain/enums.py`, replace the `SignalStatus` enum (lines 52-55) with:

```python
class SignalSeverity(StrEnum):
    """OPC-UA StatusCode severity (bits 31:30)."""
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"


# Backward compatibility alias — will be removed in a future version
SignalStatus = SignalSeverity


class LimitBits(StrEnum):
    """OPC-UA StatusCode limit bits (bits 9:8) for directional anti-windup."""
    NONE = "NONE"
    LOW_LIMITED = "LOW_LIMITED"
    HIGH_LIMITED = "HIGH_LIMITED"
    CONSTANT = "CONSTANT"


class InitSubStatus(StrEnum):
    """FF cascade handshake sub-status."""
    NONE = "NONE"
    NI = "NI"
    IR = "IR"
    IA = "IA"
    GOOD_CASCADE = "GOOD_CASCADE"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_signal.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Verify existing tests still pass**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All existing tests PASS (SignalStatus is aliased to SignalSeverity)

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/enums.py tests/domain/test_signal.py
git commit -m "feat(domain): add SignalSeverity, LimitBits, InitSubStatus enums for FF signals"
```

---

## Task 2: FFSignalStatus and FFSignal Value Objects

**Files:**
- Create: `packages/smart_pid_domain/src/smart_pid_domain/models/signal.py`
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/models/__init__.py`
- Test: `tests/domain/test_signal.py` (append)

- [ ] **Step 1: Write failing tests for FFSignalStatus and FFSignal**

Append to `tests/domain/test_signal.py`:

```python
from datetime import UTC, datetime

from smart_pid_domain.models.signal import FFSignal, FFSignalStatus


class TestFFSignalStatus:
    def test_default_is_good(self) -> None:
        status = FFSignalStatus()
        assert status.severity == SignalSeverity.GOOD
        assert status.limit_bits == LimitBits.NONE
        assert status.sub_status == InitSubStatus.NONE

    def test_is_good(self) -> None:
        assert FFSignalStatus().is_good is True
        assert FFSignalStatus(severity=SignalSeverity.BAD).is_good is False

    def test_is_bad(self) -> None:
        assert FFSignalStatus(severity=SignalSeverity.BAD).is_bad is True
        assert FFSignalStatus().is_bad is False

    def test_is_high_limited(self) -> None:
        status = FFSignalStatus(limit_bits=LimitBits.HIGH_LIMITED)
        assert status.is_high_limited is True
        assert status.is_low_limited is False

    def test_is_low_limited(self) -> None:
        status = FFSignalStatus(limit_bits=LimitBits.LOW_LIMITED)
        assert status.is_low_limited is True
        assert status.is_high_limited is False

    def test_is_constant(self) -> None:
        status = FFSignalStatus(limit_bits=LimitBits.CONSTANT)
        assert status.is_constant is True

    def test_sub_status_properties(self) -> None:
        assert FFSignalStatus(sub_status=InitSubStatus.NI).is_not_invited is True
        assert FFSignalStatus(sub_status=InitSubStatus.IR).is_init_request is True
        assert FFSignalStatus(sub_status=InitSubStatus.IA).is_init_acknowledge is True
        assert FFSignalStatus(sub_status=InitSubStatus.GOOD_CASCADE).is_good_cascade is True

    def test_frozen(self) -> None:
        import pytest
        status = FFSignalStatus()
        with pytest.raises(AttributeError):
            status.severity = SignalSeverity.BAD  # type: ignore[misc]


class TestFFSignal:
    def test_default_good_status(self) -> None:
        sig = FFSignal(value=42.0)
        assert sig.value == 42.0
        assert sig.status.is_good is True
        assert sig.timestamp is None

    def test_good_factory(self) -> None:
        ts = datetime.now(tz=UTC)
        sig = FFSignal.good(50.0, ts)
        assert sig.value == 50.0
        assert sig.status.is_good is True
        assert sig.timestamp == ts

    def test_bad_factory(self) -> None:
        sig = FFSignal.bad(0.0)
        assert sig.status.is_bad is True
        assert sig.value == 0.0

    def test_with_limits_factory(self) -> None:
        sig = FFSignal.with_limits(75.0, LimitBits.HIGH_LIMITED)
        assert sig.value == 75.0
        assert sig.status.is_high_limited is True
        assert sig.status.is_good is True

    def test_frozen(self) -> None:
        import pytest
        sig = FFSignal(value=1.0)
        with pytest.raises(AttributeError):
            sig.value = 2.0  # type: ignore[misc]

    def test_equality(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        a = FFSignal.good(10.0, ts)
        b = FFSignal.good(10.0, ts)
        assert a == b
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_signal.py::TestFFSignalStatus -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'smart_pid_domain.models.signal'`

- [ ] **Step 3: Implement FFSignalStatus and FFSignal**

Create `packages/smart_pid_domain/src/smart_pid_domain/models/signal.py`:

```python
"""Foundation Fieldbus signal value objects.

Every process signal (PV, SP, CO, BKCAL_IN, BKCAL_OUT) carries value, quality
status, and timestamp as a single unit — matching OPC-UA DataValue semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from smart_pid_domain.enums import InitSubStatus, LimitBits, SignalSeverity

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class FFSignalStatus:
    """Composite status matching OPC-UA StatusCode semantics."""

    severity: SignalSeverity = SignalSeverity.GOOD
    limit_bits: LimitBits = LimitBits.NONE
    sub_status: InitSubStatus = InitSubStatus.NONE

    @property
    def is_good(self) -> bool:
        return self.severity == SignalSeverity.GOOD

    @property
    def is_bad(self) -> bool:
        return self.severity == SignalSeverity.BAD

    @property
    def is_high_limited(self) -> bool:
        return self.limit_bits == LimitBits.HIGH_LIMITED

    @property
    def is_low_limited(self) -> bool:
        return self.limit_bits == LimitBits.LOW_LIMITED

    @property
    def is_constant(self) -> bool:
        return self.limit_bits == LimitBits.CONSTANT

    @property
    def is_not_invited(self) -> bool:
        return self.sub_status == InitSubStatus.NI

    @property
    def is_init_request(self) -> bool:
        return self.sub_status == InitSubStatus.IR

    @property
    def is_init_acknowledge(self) -> bool:
        return self.sub_status == InitSubStatus.IA

    @property
    def is_good_cascade(self) -> bool:
        return self.sub_status == InitSubStatus.GOOD_CASCADE


@dataclass(frozen=True)
class FFSignal:
    """A process signal with value, quality status, and timestamp.

    Mirrors the OPC-UA DataValue structure and Foundation Fieldbus signal
    semantics. Every signal in the PID engine (PV, SP, CO, BKCAL_IN,
    BKCAL_OUT) uses this type.
    """

    value: float
    status: FFSignalStatus = field(default_factory=FFSignalStatus)
    timestamp: datetime | None = None

    @staticmethod
    def good(value: float, ts: datetime | None = None) -> FFSignal:
        """Create a signal with GOOD status."""
        return FFSignal(value=value, status=FFSignalStatus(), timestamp=ts)

    @staticmethod
    def bad(value: float = 0.0, ts: datetime | None = None) -> FFSignal:
        """Create a signal with BAD status."""
        return FFSignal(
            value=value,
            status=FFSignalStatus(severity=SignalSeverity.BAD),
            timestamp=ts,
        )

    @staticmethod
    def with_limits(
        value: float, limit_bits: LimitBits, ts: datetime | None = None,
    ) -> FFSignal:
        """Create a GOOD signal with specific limit bits."""
        return FFSignal(
            value=value,
            status=FFSignalStatus(limit_bits=limit_bits),
            timestamp=ts,
        )
```

- [ ] **Step 4: Update domain models __init__.py**

In `packages/smart_pid_domain/src/smart_pid_domain/models/__init__.py`, add the imports:

```python
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus
```

And add to `__all__`:
```python
    "FFSignal",
    "FFSignalStatus",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_signal.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/models/signal.py \
      packages/smart_pid_domain/src/smart_pid_domain/models/__init__.py \
      tests/domain/test_signal.py
git commit -m "feat(domain): add FFSignal and FFSignalStatus value objects"
```

---

## Task 3: Update TelemetryFrame, ControlAction, and TagBindings

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/models/telemetry.py`
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py:58-65`
- Test: `tests/domain/test_models.py` (update)

- [ ] **Step 1: Write failing tests for updated models**

Read `tests/domain/test_models.py` first to understand existing tests, then add new tests. Append to the test file:

```python
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus
from smart_pid_domain.enums import LimitBits, SignalSeverity


class TestTelemetryFrameFFSignal:
    """TelemetryFrame fields are now FFSignal."""

    def test_create_with_ff_signals(self) -> None:
        from datetime import UTC, datetime
        ts = datetime.now(tz=UTC)
        frame = TelemetryFrame(
            controller_id=1,
            pv=FFSignal.good(50.0, ts),
            sp=FFSignal.good(50.0, ts),
            co=FFSignal.good(62.0, ts),
            bkcal_in=FFSignal.good(62.0, ts),
            integral_val=45.0,
            timestamp=ts,
        )
        assert frame.pv.value == 50.0
        assert frame.pv.status.is_good is True
        assert frame.bkcal_in.value == 62.0

    def test_bkcal_in_with_limit_bits(self) -> None:
        from datetime import UTC, datetime
        ts = datetime.now(tz=UTC)
        frame = TelemetryFrame(
            controller_id=1,
            pv=FFSignal.good(50.0),
            sp=FFSignal.good(50.0),
            co=FFSignal.with_limits(100.0, LimitBits.HIGH_LIMITED),
            bkcal_in=FFSignal.with_limits(100.0, LimitBits.HIGH_LIMITED),
            integral_val=45.0,
            timestamp=ts,
        )
        assert frame.bkcal_in.status.is_high_limited is True


class TestControlActionFFSignal:
    """ControlAction fields now use FFSignal."""

    def test_create_with_bkcal_out(self) -> None:
        from datetime import UTC, datetime
        ts = datetime.now(tz=UTC)
        action = ControlAction(
            controller_id=1,
            co=FFSignal.good(62.0, ts),
            bkcal_out=FFSignal.good(62.0, ts),
            integral_val=45.0,
            timestamp=ts,
        )
        assert action.co.value == 62.0
        assert action.bkcal_out.value == 62.0


class TestTagBindingsFFSignal:
    """TagBindings has BKCAL node ID fields."""

    def test_bkcal_node_ids(self) -> None:
        from smart_pid_domain.models.controller import TagBindings
        tb = TagBindings(
            node_id_pv="ns=2;s=PV",
            node_id_bkcal_in="ns=2;s=BKCAL_IN",
            node_id_bkcal_out="ns=2;s=BKCAL_OUT",
        )
        assert tb.node_id_bkcal_in == "ns=2;s=BKCAL_IN"
        assert tb.node_id_bkcal_out == "ns=2;s=BKCAL_OUT"

    def test_bkcal_defaults_empty(self) -> None:
        from smart_pid_domain.models.controller import TagBindings
        tb = TagBindings()
        assert tb.node_id_bkcal_in == ""
        assert tb.node_id_bkcal_out == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_models.py::TestTelemetryFrameFFSignal -v`
Expected: FAIL — TelemetryFrame doesn't accept FFSignal or bkcal_in yet

- [ ] **Step 3: Update TelemetryFrame and ControlAction**

Replace the full content of `packages/smart_pid_domain/src/smart_pid_domain/models/telemetry.py`:

```python
"""Telemetry and control action models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from smart_pid_domain.models.signal import FFSignal

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(frozen=True)
class TelemetryFrame:
    """Immutable snapshot of a controller's process values.

    All process signals carry value + quality status + timestamp (FF semantics).
    """

    controller_id: int
    pv: FFSignal
    sp: FFSignal
    co: FFSignal
    bkcal_in: FFSignal
    integral_val: float
    timestamp: datetime


@dataclass(frozen=True)
class ControlAction:
    """Output from PID computation to be written to the process."""

    controller_id: int
    co: FFSignal
    bkcal_out: FFSignal
    integral_val: float
    timestamp: datetime
```

- [ ] **Step 4: Update TagBindings**

In `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py`, replace the `TagBindings` class (lines 58-65):

```python
@dataclass
class TagBindings:
    """OPC-UA NodeID mappings for a controller."""

    node_id_pv: str = ""
    node_id_sp: str = ""
    node_id_co: str = ""
    node_id_integral: str = ""
    node_id_bkcal_in: str = ""
    node_id_bkcal_out: str = ""
```

- [ ] **Step 5: Run new tests to verify they pass**

Run: `uv run pytest tests/domain/test_models.py::TestTelemetryFrameFFSignal tests/domain/test_models.py::TestControlActionFFSignal tests/domain/test_models.py::TestTagBindingsFFSignal -v`
Expected: PASS

- [ ] **Step 6: Fix existing tests that break due to model changes**

Existing tests that create `TelemetryFrame` or `ControlAction` with old signatures need updating. The pattern is:
- `TelemetryFrame(controller_id=1, pv=50.0, sp=50.0, co=62.0, integral_val=45.0, timestamp=ts, status=SignalStatus.GOOD)` becomes
- `TelemetryFrame(controller_id=1, pv=FFSignal.good(50.0), sp=FFSignal.good(50.0), co=FFSignal.good(62.0), bkcal_in=FFSignal.good(0.0), integral_val=45.0, timestamp=ts)`

Run `uv run pytest tests/ -v --timeout=30` to find all broken tests. Fix each one by updating to use `FFSignal`. Files likely affected:
- `tests/domain/test_models.py` — existing TelemetryFrame tests
- `tests/domain/test_events.py` — TelemetryReceived tests
- `tests/core/integration/test_historian.py` — historian batch insert tests
- `tests/core/unit/test_export_worker.py` — export tests
- `tests/core/integration/test_api_history.py` — history API tests

For each broken test, import `FFSignal` and wrap float values with `FFSignal.good(value)`.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/models/telemetry.py \
      packages/smart_pid_domain/src/smart_pid_domain/models/controller.py \
      tests/
git commit -m "feat(domain): update TelemetryFrame, ControlAction, TagBindings for FF signals"
```

---

## Task 4: PID Engine — Directional Anti-Windup via BKCAL_IN

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/domain/services/pid_engine.py`
- Test: `tests/core/unit/test_pid_engine.py`

- [ ] **Step 1: Write failing tests for directional anti-windup**

Append to `tests/core/unit/test_pid_engine.py`:

```python
from smart_pid_domain.enums import LimitBits
from smart_pid_domain.models.signal import FFSignal


class TestDirectionalAntiWindup:
    """Anti-windup based on BKCAL_IN limit bits from downstream block."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_high_limited_blocks_positive_integration(self) -> None:
        """When downstream is HIGH_LIMITED, positive integral increment is blocked."""
        state = PIDState(cv=60.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0)
        bkcal_in = FFSignal.with_limits(60.0, LimitBits.HIGH_LIMITED)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Error = 10 (positive), integral would be +1.0, but HIGH_LIMITED blocks it
        # Only proportional acts: error unchanged so p_term = 0
        assert result.delta_cv == pytest.approx(0.0, abs=1e-6)

    def test_high_limited_allows_negative_integration(self) -> None:
        """HIGH_LIMITED only blocks positive increment; negative is allowed."""
        state = PIDState(cv=60.0, error_prev=-5.0, pv_prev=55.0, pv_prev2=55.0)
        bkcal_in = FFSignal.with_limits(60.0, LimitBits.HIGH_LIMITED)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(55.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Error = -5, integral = -0.5 (negative) -> allowed despite HIGH_LIMITED
        assert result.delta_cv < 0.0

    def test_low_limited_blocks_negative_integration(self) -> None:
        """When downstream is LOW_LIMITED, negative integral increment is blocked."""
        state = PIDState(cv=40.0, error_prev=-10.0, pv_prev=60.0, pv_prev2=60.0)
        bkcal_in = FFSignal.with_limits(40.0, LimitBits.LOW_LIMITED)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(60.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Error = -10, integral would be -1.0, but LOW_LIMITED blocks it
        # Proportional: error unchanged so p_term = 0
        assert result.delta_cv == pytest.approx(0.0, abs=1e-6)

    def test_constant_blocks_all_integration(self) -> None:
        """CONSTANT limit blocks all integration regardless of direction."""
        state = PIDState(cv=50.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0)
        bkcal_in = FFSignal.with_limits(50.0, LimitBits.CONSTANT)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        assert result.delta_cv == pytest.approx(0.0, abs=1e-6)

    def test_none_limit_allows_normal_integration(self) -> None:
        """NONE limit bits — integration is free (normal behavior)."""
        state = PIDState(cv=50.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0)
        bkcal_in = FFSignal.good(50.0)
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Normal integral: G * dt/Ti * e = 1.0 * 1.0/10.0 * 10 = 1.0
        assert result.delta_cv == pytest.approx(1.0, abs=1e-6)

    def test_downstream_and_local_arw_most_restrictive_wins(self) -> None:
        """Both local ARW and downstream limit active — most restrictive wins."""
        # Local ARW: saturated high, error positive -> blocks
        # Downstream: NONE -> allows
        # Result: blocked (local wins)
        state = PIDState(
            cv=100.0, error_prev=10.0, pv_prev=40.0, pv_prev2=40.0, is_saturated=True,
        )
        bkcal_in = FFSignal.good(100.0)  # No downstream limit
        result = self.engine.compute(
            params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
            state=state,
            pv=FFSignal.good(40.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
            dt=1.0,
            out_limits=(0.0, 100.0),
        )
        # Local ARW blocks positive integration when saturated high
        assert result.cv == pytest.approx(100.0, abs=1e-6)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_pid_engine.py::TestDirectionalAntiWindup -v`
Expected: FAIL — `compute()` doesn't accept FFSignal or bkcal_in parameter

- [ ] **Step 3: Update PID engine signature and add directional anti-windup**

Replace the full content of `packages/smart_pid_core/src/smart_pid_core/domain/services/pid_engine.py`:

```python
"""PID controller engine using velocity (incremental) form.

Equation (derivative on PV):
    delta_cv = Gain * [(e_n - e_n-1) + (dt/Reset)*e_n - Rate*(PV_n - 2*PV_n-1 + PV_n-2)/dt]
    cv_new = cv_current + delta_cv

Derivative filter: alpha (default Rate/8).
Anti-windup: local (output saturation) + directional (downstream limit bits via BKCAL_IN).
Bumpless transfer: reinitializes state to match current output on mode change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from smart_pid_domain.enums import LimitBits
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus

if TYPE_CHECKING:
    from smart_pid_domain.enums import SignalSeverity
    from smart_pid_domain.models.controller import PIDParams


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
    bkcal_out: FFSignal
    new_state: PIDState


class PIDEngine:
    """Stateless PID engine. All state is passed in and returned explicitly."""

    def compute(
        self,
        params: PIDParams,
        state: PIDState,
        pv: FFSignal,
        sp: FFSignal,
        bkcal_in: FFSignal,
        dt: float,
        out_limits: tuple[float, float],
        direct_acting: bool = False,
        arw_limits: tuple[float, float] | None = None,
    ) -> PIDResult:
        """Execute one PID scan. Returns new CV, BKCAL_OUT, and updated state."""
        lo, hi = out_limits
        arw_lo, arw_hi = arw_limits if arw_limits is not None else (lo, hi)

        pv_val = pv.value
        sp_val = sp.value

        # Error calculation
        error = pv_val - sp_val if direct_acting else sp_val - pv_val

        # --- Proportional term (acts on error change) ---
        p_term = params.gain * (error - state.error_prev)

        # --- Integral term ---
        i_term = 0.0
        if params.reset > 0 and dt > 0:
            # Check deadband
            in_deadband = abs(error) < params.deadband if params.deadband > 0 else False

            # Local anti-windup: suppress integral if saturated AND error drives further
            local_windup_block = (
                state.is_saturated
                and (
                    (state.cv >= arw_hi and error > 0)
                    or (state.cv <= arw_lo and error < 0)
                )
            )

            if not in_deadband and not local_windup_block:
                i_term = params.gain * (dt / params.reset) * error

                # Directional anti-windup from downstream (BKCAL_IN limit bits)
                limit = bkcal_in.status.limit_bits
                if limit == LimitBits.CONSTANT:
                    i_term = 0.0
                elif limit == LimitBits.HIGH_LIMITED and i_term > 0:
                    i_term = 0.0
                elif limit == LimitBits.LOW_LIMITED and i_term < 0:
                    i_term = 0.0

                # 16x faster reset recovery: if previously saturated and integral
                # now drives output away from saturation, accelerate recovery.
                if state.is_saturated and i_term != 0.0:
                    reducing_hi = state.cv >= arw_hi and i_term < 0
                    reducing_lo = state.cv <= arw_lo and i_term > 0
                    if reducing_hi or reducing_lo:
                        i_term *= 16.0

        # --- Derivative term (acts on PV, not error) ---
        d_term = 0.0
        if params.rate > 0 and dt > 0:
            d2_pv = pv_val - 2.0 * state.pv_prev + state.pv_prev2
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
            pv_prev=pv_val,
            pv_prev2=state.pv_prev,
            sp_working=sp_val,
            derivative_filtered=d_term,
            is_saturated=is_saturated,
        )

        # --- Generate BKCAL_OUT ---
        bkcal_out = self._make_bkcal_out(cv_new, lo, hi, is_saturated)

        return PIDResult(
            cv=cv_new,
            delta_cv=delta_cv,
            error=error,
            bkcal_out=bkcal_out,
            new_state=new_state,
        )

    def compute_iman_tracking(
        self,
        state: PIDState,
        pv: FFSignal,
        sp: FFSignal,
        bkcal_in: FFSignal,
        direct_acting: bool = False,
    ) -> PIDResult:
        """IMAN tracking: force CV to match BKCAL_IN value exactly.

        Used during cascade initialization handshake (IR phase).
        The integral accumulator is forced directly — no PID calculation.
        PV history is updated to prevent derivative kick on return to active mode.
        """
        pv_val = pv.value
        sp_val = sp.value
        error = pv_val - sp_val if direct_acting else sp_val - pv_val
        tracking_value = bkcal_in.value

        new_state = PIDState(
            cv=tracking_value,
            error_prev=error,
            pv_prev=pv_val,
            pv_prev2=state.pv_prev,
            sp_working=sp_val,
            derivative_filtered=0.0,
            is_saturated=False,
        )

        from smart_pid_domain.enums import InitSubStatus, SignalSeverity

        bkcal_out = FFSignal(
            value=tracking_value,
            status=FFSignalStatus(
                severity=SignalSeverity.GOOD,
                sub_status=InitSubStatus.IA,
            ),
            timestamp=bkcal_in.timestamp,
        )

        return PIDResult(
            cv=tracking_value,
            delta_cv=0.0,
            error=error,
            bkcal_out=bkcal_out,
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

    def _make_bkcal_out(
        self, cv: float, lo: float, hi: float, is_saturated: bool,
    ) -> FFSignal:
        """Build BKCAL_OUT signal reflecting current output and saturation state."""
        if not is_saturated:
            return FFSignal.good(cv)
        if cv >= hi:
            return FFSignal.with_limits(cv, LimitBits.HIGH_LIMITED)
        return FFSignal.with_limits(cv, LimitBits.LOW_LIMITED)
```

- [ ] **Step 4: Update existing PID engine tests to use FFSignal**

In `tests/core/unit/test_pid_engine.py`, update every call to `self.engine.compute()` to wrap float PV/SP with `FFSignal.good()` and add `bkcal_in=FFSignal.good(0.0)`.

Add imports at the top of the file:

```python
from smart_pid_domain.models.signal import FFSignal
```

For every existing `compute()` call, the pattern is:
- `pv=50.0` → `pv=FFSignal.good(50.0)`
- `sp=60.0` → `sp=FFSignal.good(60.0)`
- Add `bkcal_in=FFSignal.good(0.0)` parameter

Example — `test_zero_error_produces_zero_delta`:
```python
def test_zero_error_produces_zero_delta(self) -> None:
    state = PIDState(cv=50.0, pv_prev=50.0, pv_prev2=50.0)
    result = self.engine.compute(
        params=self.params,
        state=state,
        pv=FFSignal.good(50.0),
        sp=FFSignal.good(50.0),
        bkcal_in=FFSignal.good(0.0),
        dt=1.0,
        out_limits=(0.0, 100.0),
    )
    assert result.delta_cv == pytest.approx(0.0, abs=1e-10)
    assert result.cv == pytest.approx(50.0, abs=1e-10)
```

Apply this same pattern to ALL existing tests in: `TestPIDCompute`, `TestAntiWindup`, `TestDeadband`.

- [ ] **Step 5: Run tests to verify everything passes**

Run: `uv run pytest tests/core/unit/test_pid_engine.py -v`
Expected: All existing tests PASS + all new `TestDirectionalAntiWindup` tests PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/services/pid_engine.py \
      tests/core/unit/test_pid_engine.py
git commit -m "feat(pid): directional anti-windup via BKCAL_IN limit bits + BKCAL_OUT generation"
```

---

## Task 5: PID Engine — IMAN Tracking (Integral Forcing)

**Files:**
- Test: `tests/core/unit/test_pid_engine.py` (append)

The implementation was already added in Task 4 (`compute_iman_tracking`). This task tests it.

- [ ] **Step 1: Write tests for IMAN tracking**

Append to `tests/core/unit/test_pid_engine.py`:

```python
from smart_pid_domain.enums import InitSubStatus


class TestIMANTracking:
    """IMAN mode: force CV to match BKCAL_IN value for cascade handshake."""

    def setup_method(self) -> None:
        self.engine = PIDEngine()

    def test_cv_matches_bkcal_in_value(self) -> None:
        """Output must exactly match BKCAL_IN value during tracking."""
        state = PIDState(cv=50.0, pv_prev=45.0, pv_prev2=45.0)
        bkcal_in = FFSignal(
            value=72.5,
            status=FFSignalStatus(sub_status=InitSubStatus.IR),
        )
        result = self.engine.compute_iman_tracking(
            state=state,
            pv=FFSignal.good(45.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
        )
        assert result.cv == pytest.approx(72.5, abs=1e-10)
        assert result.delta_cv == 0.0

    def test_bkcal_out_has_ia_substatus(self) -> None:
        """BKCAL_OUT must carry IA sub-status to acknowledge initialization."""
        state = PIDState(cv=50.0, pv_prev=45.0, pv_prev2=45.0)
        bkcal_in = FFSignal(
            value=72.5,
            status=FFSignalStatus(sub_status=InitSubStatus.IR),
        )
        result = self.engine.compute_iman_tracking(
            state=state,
            pv=FFSignal.good(45.0),
            sp=FFSignal.good(50.0),
            bkcal_in=bkcal_in,
        )
        assert result.bkcal_out.value == pytest.approx(72.5, abs=1e-10)
        assert result.bkcal_out.status.sub_status == InitSubStatus.IA

    def test_pv_history_updated(self) -> None:
        """PV history must be updated to prevent derivative kick on return."""
        state = PIDState(cv=50.0, pv_prev=40.0, pv_prev2=38.0)
        result = self.engine.compute_iman_tracking(
            state=state,
            pv=FFSignal.good(45.0),
            sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(72.5),
        )
        assert result.new_state.pv_prev == pytest.approx(45.0)
        assert result.new_state.pv_prev2 == pytest.approx(40.0)
        assert result.new_state.derivative_filtered == 0.0

    def test_state_cv_set_to_tracking_value(self) -> None:
        """State CV must be set to BKCAL_IN value for seamless transition."""
        state = PIDState(cv=30.0)
        result = self.engine.compute_iman_tracking(
            state=state,
            pv=FFSignal.good(45.0),
            sp=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(80.0),
        )
        assert result.new_state.cv == pytest.approx(80.0)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_pid_engine.py::TestIMANTracking -v`
Expected: All 4 tests PASS (implementation already in place from Task 4)

- [ ] **Step 3: Commit**

```bash
git add tests/core/unit/test_pid_engine.py
git commit -m "test(pid): add IMAN tracking tests for cascade handshake integral forcing"
```

---

## Task 6: Mode Manager — Cascade Handshake

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/domain/services/pid_mode_manager.py`
- Test: `tests/core/unit/test_cascade_handshake.py` (create)

- [ ] **Step 1: Write failing tests for cascade handshake**

Create `tests/core/unit/test_cascade_handshake.py`:

```python
"""Unit tests for FF cascade handshake in mode manager."""
from __future__ import annotations

from smart_pid_core.domain.services.pid_mode_manager import (
    BlockStatus,
    CascadeAction,
    ModeManager,
)
from smart_pid_domain.enums import (
    ControllerMode,
    InitSubStatus,
    LimitBits,
    SignalSeverity,
)
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus


class TestCascadeHandshake:
    """Test evaluate_cascade_handshake decision table."""

    def setup_method(self) -> None:
        self.mgr = ModeManager()

    def test_bad_bkcal_in_cas_forces_iman(self) -> None:
        """Slave sends BAD status while in CAS -> force IMAN."""
        bkcal_in = FFSignal.bad(50.0)
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.CAS,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode == ControllerMode.IMAN
        assert action.emit_sub_status == InitSubStatus.NI

    def test_ni_bkcal_in_cas_forces_iman(self) -> None:
        """Slave sends NI while in CAS -> force IMAN."""
        bkcal_in = FFSignal(
            value=50.0,
            status=FFSignalStatus(sub_status=InitSubStatus.NI),
        )
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.CAS,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode == ControllerMode.IMAN
        assert action.emit_sub_status == InitSubStatus.NI

    def test_ir_in_iman_stays_iman_and_tracks(self) -> None:
        """Slave sends IR while in IMAN -> stay IMAN, track value."""
        bkcal_in = FFSignal(
            value=72.5,
            status=FFSignalStatus(sub_status=InitSubStatus.IR),
        )
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.IMAN,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode is None  # Stay in current mode
        assert action.tracking_target == 72.5
        assert action.emit_sub_status == InitSubStatus.IA

    def test_good_cascade_in_iman_forces_cas(self) -> None:
        """Slave sends GOOD_CASCADE while in IMAN -> force CAS."""
        bkcal_in = FFSignal(
            value=72.5,
            status=FFSignalStatus(sub_status=InitSubStatus.GOOD_CASCADE),
        )
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.IMAN,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode == ControllerMode.CAS
        assert action.requires_bumpless is True
        assert action.emit_sub_status == InitSubStatus.NONE

    def test_good_none_in_auto_no_action(self) -> None:
        """Normal operation in AUTO with GOOD/NONE -> no action."""
        bkcal_in = FFSignal.good(50.0)
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.AUTO,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode is None
        assert action.tracking_target is None
        assert action.emit_sub_status == InitSubStatus.NONE

    def test_bad_bkcal_in_already_iman_stays(self) -> None:
        """Already in IMAN with BAD -> stay in IMAN, emit NI."""
        bkcal_in = FFSignal.bad(0.0)
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.IMAN,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode is None
        assert action.emit_sub_status == InitSubStatus.NI

    def test_bad_bkcal_in_rcas_forces_iman(self) -> None:
        """BAD status in RCAS also forces IMAN."""
        bkcal_in = FFSignal.bad(50.0)
        action = self.mgr.evaluate_cascade_handshake(
            current_mode=ControllerMode.RCAS,
            bkcal_in=bkcal_in,
        )
        assert action.force_mode == ControllerMode.IMAN


class TestForcedTransitionsWithFF:
    """Updated forced transitions with BKCAL_IN in BlockStatus."""

    def setup_method(self) -> None:
        self.mgr = ModeManager()

    def test_bad_pv_forces_man(self) -> None:
        """Bad PV status forces MAN — unchanged behavior."""
        status = BlockStatus(
            pv=FFSignal.bad(0.0),
            bkcal_in=FFSignal.good(0.0),
        )
        forced = self.mgr.evaluate_forced_transitions(
            current=ControllerMode.AUTO,
            block_status=status,
        )
        assert forced == ControllerMode.MAN

    def test_tracking_active_forces_lo(self) -> None:
        """Tracking active forces LO — unchanged behavior."""
        status = BlockStatus(
            pv=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(0.0),
            tracking_active=True,
        )
        forced = self.mgr.evaluate_forced_transitions(
            current=ControllerMode.AUTO,
            block_status=status,
        )
        assert forced == ControllerMode.LO

    def test_bad_bkcal_in_forces_iman(self) -> None:
        """Bad BKCAL_IN forces IMAN from CAS."""
        status = BlockStatus(
            pv=FFSignal.good(50.0),
            bkcal_in=FFSignal.bad(0.0),
        )
        forced = self.mgr.evaluate_forced_transitions(
            current=ControllerMode.CAS,
            block_status=status,
        )
        assert forced == ControllerMode.IMAN

    def test_ni_bkcal_in_forces_iman(self) -> None:
        """NI sub-status on BKCAL_IN forces IMAN from CAS."""
        status = BlockStatus(
            pv=FFSignal.good(50.0),
            bkcal_in=FFSignal(
                value=0.0,
                status=FFSignalStatus(sub_status=InitSubStatus.NI),
            ),
        )
        forced = self.mgr.evaluate_forced_transitions(
            current=ControllerMode.CAS,
            block_status=status,
        )
        assert forced == ControllerMode.IMAN

    def test_bad_pv_higher_priority_than_bad_bkcal(self) -> None:
        """Bad PV (forces MAN) has higher priority than bad BKCAL_IN (forces IMAN)."""
        status = BlockStatus(
            pv=FFSignal.bad(0.0),
            bkcal_in=FFSignal.bad(0.0),
        )
        forced = self.mgr.evaluate_forced_transitions(
            current=ControllerMode.CAS,
            block_status=status,
        )
        assert forced == ControllerMode.MAN

    def test_good_signals_no_force(self) -> None:
        """All signals GOOD — no forced transition."""
        status = BlockStatus(
            pv=FFSignal.good(50.0),
            bkcal_in=FFSignal.good(50.0),
        )
        forced = self.mgr.evaluate_forced_transitions(
            current=ControllerMode.AUTO,
            block_status=status,
        )
        assert forced is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_cascade_handshake.py -v`
Expected: FAIL — `CascadeAction` doesn't exist, `BlockStatus` doesn't accept FFSignal

- [ ] **Step 3: Update mode manager implementation**

Replace the full content of `packages/smart_pid_core/src/smart_pid_core/domain/services/pid_mode_manager.py`:

```python
"""PID mode state machine with Foundation Fieldbus cascade handshake.

Manages transitions between 8 operating modes:
OOS, IMan, LO, Man, Auto, Cas, RCas, ROut.

Rules from bloco_pid.md + FF spec:
- Tracking active -> forces LO
- Bad PV -> forces MAN
- Bad/NI BKCAL_IN -> forces IMAN (cascade break)
- SHED timeout -> forces configured shed mode
- Transitions validate against permitted modes
- Man->Auto and Auto->Cas require bumpless transfer
- Cascade handshake: NI -> IR -> IA -> GOOD_CASCADE
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from smart_pid_domain.enums import ControllerMode, InitSubStatus
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus

# Modes that require bumpless transfer when entering
_BUMPLESS_REQUIRED_TARGETS = {ControllerMode.AUTO, ControllerMode.CAS, ControllerMode.RCAS}

# Modes where cascade handshake break applies
_CASCADE_MODES = {ControllerMode.CAS, ControllerMode.RCAS}


@dataclass
class BlockStatus:
    """Current status conditions that may force mode changes."""

    pv: FFSignal = field(default_factory=lambda: FFSignal.good(0.0))
    bkcal_in: FFSignal = field(default_factory=lambda: FFSignal.good(0.0))
    tracking_active: bool = False
    shed_timeout_expired: bool = False
    simulate_active: bool = False


@dataclass(frozen=True)
class CascadeAction:
    """Result of cascade handshake evaluation."""

    force_mode: ControllerMode | None = None
    requires_bumpless: bool = False
    tracking_target: float | None = None
    emit_sub_status: InitSubStatus = InitSubStatus.NONE


@dataclass
class ModeTransition:
    """Result of a mode transition request."""

    accepted: bool
    new_mode: ControllerMode
    requires_bumpless: bool = False
    rejection_reason: str = ""


class ModeManager:
    """Stateless mode transition evaluator with FF cascade handshake."""

    def request_mode(
        self,
        current: ControllerMode,
        target: ControllerMode,
        permitted: set[ControllerMode],
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
        current: ControllerMode,
        block_status: BlockStatus,
        shed_mode: ControllerMode = ControllerMode.MAN,
    ) -> ControllerMode | None:
        """Check for conditions that force an automatic mode change.

        Priority order:
        1. Tracking active -> LO
        2. Bad PV -> MAN
        3. Bad/NI BKCAL_IN in cascade mode -> IMAN
        4. Shed timeout -> configured shed mode

        Returns None if no forced transition is needed.
        """
        # Tracking has highest priority
        if block_status.tracking_active:
            return ControllerMode.LO

        # Bad PV forces manual
        if block_status.pv.status.is_bad:
            return ControllerMode.MAN

        # Bad or NI BKCAL_IN forces IMAN when in cascade modes
        if current in _CASCADE_MODES:
            bkcal_status = block_status.bkcal_in.status
            if bkcal_status.is_bad or bkcal_status.is_not_invited:
                return ControllerMode.IMAN

        # Shed timeout
        if block_status.shed_timeout_expired:
            return shed_mode

        return None

    def evaluate_cascade_handshake(
        self,
        current_mode: ControllerMode,
        bkcal_in: FFSignal,
    ) -> CascadeAction:
        """Evaluate FF cascade handshake based on BKCAL_IN status.

        Returns CascadeAction indicating what the PID worker should do.
        """
        sub = bkcal_in.status.sub_status
        is_bad = bkcal_in.status.is_bad

        # BAD or NI while in cascade -> break to IMAN
        if is_bad or sub == InitSubStatus.NI:
            if current_mode in _CASCADE_MODES:
                return CascadeAction(
                    force_mode=ControllerMode.IMAN,
                    emit_sub_status=InitSubStatus.NI,
                )
            # Already in IMAN or other mode — just emit NI
            return CascadeAction(emit_sub_status=InitSubStatus.NI)

        # IR while in IMAN -> track BKCAL_IN value
        if sub == InitSubStatus.IR and current_mode == ControllerMode.IMAN:
            return CascadeAction(
                tracking_target=bkcal_in.value,
                emit_sub_status=InitSubStatus.IA,
            )

        # GOOD_CASCADE while in IMAN -> transition to CAS
        if sub == InitSubStatus.GOOD_CASCADE and current_mode == ControllerMode.IMAN:
            return CascadeAction(
                force_mode=ControllerMode.CAS,
                requires_bumpless=True,
                emit_sub_status=InitSubStatus.NONE,
            )

        # Normal operation — no cascade action needed
        return CascadeAction()
```

- [ ] **Step 4: Update existing mode manager tests**

In `tests/core/unit/test_pid_mode_manager.py`, update `BlockStatus` creation to use FFSignal:

Add import at top:
```python
from smart_pid_domain.models.signal import FFSignal
```

Replace `BlockStatus()` calls:
- `BlockStatus()` → `BlockStatus()` (no change needed — defaults are now `FFSignal.good(0.0)`)
- `BlockStatus(pv_status=SignalStatus.BAD)` → `BlockStatus(pv=FFSignal.bad(0.0))`
- `BlockStatus(pv_status=SignalStatus.GOOD)` → `BlockStatus(pv=FFSignal.good(0.0))`
- `BlockStatus(tracking_active=True)` → `BlockStatus(tracking_active=True)`
- `BlockStatus(shed_timeout_expired=True)` → `BlockStatus(shed_timeout_expired=True)`

Remove import of `SignalStatus` from the test file.

- [ ] **Step 5: Run all mode manager tests**

Run: `uv run pytest tests/core/unit/test_pid_mode_manager.py tests/core/unit/test_cascade_handshake.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/services/pid_mode_manager.py \
      tests/core/unit/test_pid_mode_manager.py \
      tests/core/unit/test_cascade_handshake.py
git commit -m "feat(mode): cascade handshake evaluation and updated forced transitions for FF"
```

---

## Task 7: Update Events — ControlActionComputed + CascadeHandshakeChanged

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/events.py`
- Test: `tests/domain/test_events.py`

- [ ] **Step 1: Write failing tests for updated events**

Append to `tests/domain/test_events.py`:

```python
from smart_pid_domain.enums import InitSubStatus
from smart_pid_domain.events import CascadeHandshakeChanged


class TestCascadeHandshakeChanged:
    def test_create(self) -> None:
        from datetime import UTC, datetime
        evt = CascadeHandshakeChanged(
            controller_id=1,
            old_sub_status=InitSubStatus.NI,
            new_sub_status=InitSubStatus.IR,
            trigger="ir_received",
            timestamp=datetime.now(tz=UTC),
        )
        assert evt.controller_id == 1
        assert evt.old_sub_status == InitSubStatus.NI
        assert evt.new_sub_status == InitSubStatus.IR
        assert evt.trigger == "ir_received"

    def test_frozen(self) -> None:
        import pytest
        from datetime import UTC, datetime
        evt = CascadeHandshakeChanged(
            controller_id=1,
            old_sub_status=InitSubStatus.NONE,
            new_sub_status=InitSubStatus.NI,
            trigger="bkcal_in_bad",
            timestamp=datetime.now(tz=UTC),
        )
        with pytest.raises(AttributeError):
            evt.controller_id = 2  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_events.py::TestCascadeHandshakeChanged -v`
Expected: FAIL — `CascadeHandshakeChanged` doesn't exist

- [ ] **Step 3: Add CascadeHandshakeChanged event**

In `packages/smart_pid_domain/src/smart_pid_domain/events.py`, add after `AlarmAcknowledged`:

```python
@dataclass(frozen=True)
class CascadeHandshakeChanged:
    """Published by PID Worker on cascade handshake state transitions."""

    controller_id: int
    old_sub_status: InitSubStatus
    new_sub_status: InitSubStatus
    trigger: str
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)
```

Also add `InitSubStatus` to the TYPE_CHECKING imports block at the top of the file:

```python
if TYPE_CHECKING:
    from datetime import datetime

    from smart_pid_domain.enums import (
        AIEngine,
        AlarmPriority,
        AlarmType,
        ConnectionState,
        ControlObjective,
        InitSubStatus,
    )
    from smart_pid_domain.models.telemetry import TelemetryFrame
```

- [ ] **Step 4: Fix existing event tests if broken**

The `ControlActionComputed` event keeps its existing fields for now (co as float). The internal structure will be updated when the PIDWorker is modified. Check `tests/domain/test_events.py` for any existing tests that need `TelemetryFrame` or import updates.

Run: `uv run pytest tests/domain/test_events.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/events.py tests/domain/test_events.py
git commit -m "feat(events): add CascadeHandshakeChanged event for FF handshake audit"
```

---

## Task 8: PIDWorker — Integrate FFSignal and Cascade Handshake

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py`
- Test: `tests/core/integration/test_pid_worker.py`

- [ ] **Step 1: Read current PIDWorker integration tests**

Read `tests/core/integration/test_pid_worker.py` to understand the current test setup and patterns before modifying.

- [ ] **Step 2: Update PIDWorker implementation**

Replace the full content of `packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py`:

```python
"""PID Worker — high-priority daemon thread executing PID at the controller's scan rate."""
from __future__ import annotations

import dataclasses
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import msgpack
import zmq

from smart_pid_core.domain.services.pid_engine import PIDState
from smart_pid_core.domain.services.pid_mode_manager import BlockStatus
from smart_pid_domain.enums import ControllerMode, InitSubStatus
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_core.domain.services.pid_engine import PIDEngine
    from smart_pid_core.domain.services.pid_mode_manager import ModeManager
    from smart_pid_domain.enums import LimitBits, SignalSeverity
    from smart_pid_domain.models.controller import Controller


def _deserialize_ff_signal(data: dict | float | int) -> FFSignal:
    """Deserialize an FFSignal from msgpack data.

    Backward compatible: plain float/int is wrapped as FFSignal.good(value).
    """
    if isinstance(data, (float, int)):
        return FFSignal.good(float(data))
    from smart_pid_domain.enums import LimitBits, SignalSeverity
    return FFSignal(
        value=float(data.get("value", 0.0)),
        status=FFSignalStatus(
            severity=SignalSeverity(data.get("severity", "GOOD")),
            limit_bits=LimitBits(data.get("limit_bits", "NONE")),
            sub_status=InitSubStatus(data.get("sub_status", "NONE")),
        ),
        timestamp=None,  # Timestamp from msgpack is string, handled at IOWorker level
    )


def _serialize_ff_signal(signal: FFSignal) -> dict:
    """Serialize an FFSignal to a msgpack-compatible dict."""
    return {
        "value": signal.value,
        "severity": signal.status.severity.value,
        "limit_bits": signal.status.limit_bits.value,
        "sub_status": signal.status.sub_status.value,
    }


class PIDWorker:
    def __init__(
        self, bus: EventBus, controller: Controller, engine: PIDEngine, mode_manager: ModeManager
    ) -> None:
        self._bus = bus
        self._controller = controller
        self._engine = engine
        self._mode_manager = mode_manager
        self._state = PIDState()
        self._mode = ControllerMode.MAN
        self._block_status = BlockStatus()
        self._last_pv: FFSignal = FFSignal.good(0.0)
        self._last_sp: FFSignal = FFSignal.good(0.0)
        self._last_co: FFSignal = FFSignal.good(0.0)
        self._last_bkcal_in: FFSignal = FFSignal.good(0.0)
        self._last_bkcal_out: FFSignal = FFSignal.good(0.0)
        self._has_telemetry = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def controller_id(self) -> int:
        return self._controller.id

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"pid-worker-{self.controller_id}"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def current_mode(self) -> ControllerMode:
        return self._mode

    def set_mode(self, mode: ControllerMode) -> None:
        with self._lock:
            self._mode = mode

    def set_sp(self, value: float) -> None:
        with self._lock:
            self._last_sp = FFSignal.good(value)

    def set_output(self, value: float) -> None:
        with self._lock:
            self._last_co = FFSignal.good(value)

    def _run(self) -> None:
        telem_sub = self._bus.create_subscriber(f"TELEMETRY.{self.controller_id}".encode())
        ai_sub = self._bus.create_subscriber(f"ACTION.AI.{self.controller_id}".encode())
        pub = self._bus.create_publisher()
        scan_s = self._controller.scan_rate_ms / 1000.0
        time.sleep(0.02)

        while not self._stop_event.is_set():
            try:
                tick_start = time.monotonic()
                self._drain_telemetry(telem_sub)
                self._drain_ai_actions(ai_sub)

                # Evaluate cascade handshake
                cascade_action = self._mode_manager.evaluate_cascade_handshake(
                    current_mode=self._mode,
                    bkcal_in=self._last_bkcal_in,
                )
                if cascade_action.force_mode is not None:
                    self._mode = cascade_action.force_mode
                    if cascade_action.requires_bumpless:
                        self._state = self._engine.bumpless_transfer(
                            state=self._state,
                            current_pv=self._last_pv.value,
                            current_co=self._last_bkcal_in.value,
                            params=self._controller.pid_params,
                        )

                if self._has_telemetry:
                    if self._mode == ControllerMode.IMAN and cascade_action.tracking_target is not None:
                        # IMAN tracking: force CV to match BKCAL_IN
                        result = self._engine.compute_iman_tracking(
                            state=self._state,
                            pv=self._last_pv,
                            sp=self._last_sp,
                            bkcal_in=self._last_bkcal_in,
                            direct_acting=self._controller.control_opts.direct_acting,
                        )
                        self._state = result.new_state
                        self._last_co = result.bkcal_out  # CO = tracking value
                        self._last_bkcal_out = result.bkcal_out
                    elif self._mode in {
                        ControllerMode.AUTO, ControllerMode.CAS, ControllerMode.RCAS,
                    }:
                        params = self._controller.pid_params
                        out_limits = (self._controller.out_lo_lim, self._controller.out_hi_lim)
                        arw_limits = (self._controller.arw_lo_lim, self._controller.arw_hi_lim)
                        direct_acting = self._controller.control_opts.direct_acting
                        result = self._engine.compute(
                            params=params, state=self._state,
                            pv=self._last_pv, sp=self._last_sp,
                            bkcal_in=self._last_bkcal_in,
                            dt=scan_s, out_limits=out_limits,
                            direct_acting=direct_acting, arw_limits=arw_limits,
                        )
                        self._state = result.new_state
                        self._last_co = FFSignal.good(result.cv)
                        self._last_bkcal_out = result.bkcal_out

                    # Publish control action
                    action_data = {
                        "controller_id": self.controller_id,
                        "co": _serialize_ff_signal(self._last_co),
                        "bkcal_out": _serialize_ff_signal(self._last_bkcal_out),
                        "integral_val": self._state.cv,
                        "delta_cv": getattr(result, "delta_cv", 0.0) if "result" in dir() else 0.0,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                    topic = f"ACTION.CTRL.{self.controller_id}".encode()
                    pub.send(topic, msgpack.packb(action_data))

                if self._has_telemetry:
                    telem_data = {
                        "controller_id": self.controller_id,
                        "pv": _serialize_ff_signal(self._last_pv),
                        "sp": _serialize_ff_signal(self._last_sp),
                        "co": _serialize_ff_signal(self._last_co),
                        "bkcal_in": _serialize_ff_signal(self._last_bkcal_in),
                        "bkcal_out": _serialize_ff_signal(self._last_bkcal_out),
                        "integral_val": self._state.cv,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                    pub.send(
                        f"STATUS.{self.controller_id}".encode(), msgpack.packb(telem_data),
                    )

                elapsed = time.monotonic() - tick_start
                sleep_time = scan_s - elapsed
                if sleep_time > 0:
                    self._stop_event.wait(timeout=sleep_time)
            except zmq.ZMQError:
                break

    def _drain_telemetry(self, sub) -> None:
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                self._last_pv = _deserialize_ff_signal(data["pv"])
                self._last_sp = _deserialize_ff_signal(data["sp"])
                if "bkcal_in" in data:
                    self._last_bkcal_in = _deserialize_ff_signal(data["bkcal_in"])
                if not self._has_telemetry:
                    self._last_co = _deserialize_ff_signal(data.get("co", 0.0))
                self._has_telemetry = True
            except (KeyError, ValueError, msgpack.UnpackException):
                pass

    def _drain_ai_actions(self, sub) -> None:
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                new_ki = data.get("new_ki")
                if new_ki is not None:
                    with self._lock:
                        self._controller.pid_params = dataclasses.replace(
                            self._controller.pid_params, reset=float(new_ki)
                        )
            except (KeyError, ValueError, msgpack.UnpackException):
                pass
```

- [ ] **Step 3: Fix the delta_cv reference in action_data**

Note: The `action_data` block has a fragile `result` reference. Fix it by restructuring:

In the `_run` method, declare `delta_cv = 0.0` before the if/elif block, and set `delta_cv = result.delta_cv` inside each branch. Then use `delta_cv` in action_data:

```python
                    action_data = {
                        "controller_id": self.controller_id,
                        "co": _serialize_ff_signal(self._last_co),
                        "bkcal_out": _serialize_ff_signal(self._last_bkcal_out),
                        "integral_val": self._state.cv,
                        "delta_cv": delta_cv,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
```

- [ ] **Step 4: Update PIDWorker integration tests**

Read `tests/core/integration/test_pid_worker.py` and update telemetry payloads to use the new FFSignal serialization format. The pattern:
- `{"pv": 50.0, "sp": 50.0, "co": 62.0, ...}` stays the same for backward compatibility — `_deserialize_ff_signal` handles plain floats.
- Add `"bkcal_in": {"value": 0.0, "severity": "GOOD", "limit_bits": "NONE", "sub_status": "NONE"}` to telemetry payloads in tests that need it.

- [ ] **Step 5: Run integration tests**

Run: `uv run pytest tests/core/integration/test_pid_worker.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py \
      tests/core/integration/test_pid_worker.py
git commit -m "feat(worker): PIDWorker integrates FFSignal, cascade handshake, BKCAL_OUT"
```

---

## Task 9: IOWorker — Serialize FFSignal to Bus

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/workers/io_worker.py`

- [ ] **Step 1: Update IOWorker to publish FFSignal data**

In `packages/smart_pid_core/src/smart_pid_core/application/workers/io_worker.py`, update the `_run()` method to serialize FFSignal fields from TelemetryFrame.

Replace the payload construction inside the `for cid` loop (lines 76-86):

```python
                        frame = self._opcua.read_telemetry(cid)
                        topic = f"TELEMETRY.{cid}".encode()
                        payload = msgpack.packb({
                            "controller_id": frame.controller_id,
                            "pv": {
                                "value": frame.pv.value,
                                "severity": frame.pv.status.severity.value,
                                "limit_bits": frame.pv.status.limit_bits.value,
                                "sub_status": frame.pv.status.sub_status.value,
                            },
                            "sp": {
                                "value": frame.sp.value,
                                "severity": frame.sp.status.severity.value,
                                "limit_bits": frame.sp.status.limit_bits.value,
                                "sub_status": frame.sp.status.sub_status.value,
                            },
                            "co": {
                                "value": frame.co.value,
                                "severity": frame.co.status.severity.value,
                                "limit_bits": frame.co.status.limit_bits.value,
                                "sub_status": frame.co.status.sub_status.value,
                            },
                            "bkcal_in": {
                                "value": frame.bkcal_in.value,
                                "severity": frame.bkcal_in.status.severity.value,
                                "limit_bits": frame.bkcal_in.status.limit_bits.value,
                                "sub_status": frame.bkcal_in.status.sub_status.value,
                            },
                            "integral_val": frame.integral_val,
                            "timestamp": frame.timestamp.isoformat(),
                        })
                        pub.send(topic, payload)
```

- [ ] **Step 2: Run existing tests**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/io_worker.py
git commit -m "feat(io): IOWorker serializes FFSignal fields to event bus"
```

---

## Task 10: OPCUAAdapter — Read DataValue with StatusCode Decoding

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py`

- [ ] **Step 1: Add StatusCode decoding helpers**

Add these methods to `OPCUAAdapter` class after the `wait_connected` method:

```python
    @staticmethod
    def _decode_status(status_code: int) -> FFSignalStatus:
        """Decode OPC-UA StatusCode into FFSignalStatus."""
        from smart_pid_domain.enums import LimitBits, SignalSeverity
        from smart_pid_domain.models.signal import FFSignalStatus

        severity_bits = (status_code & 0xC0000000) >> 30
        severity_map = {0: SignalSeverity.GOOD, 1: SignalSeverity.UNCERTAIN}
        severity = severity_map.get(severity_bits, SignalSeverity.BAD)

        limit_val = (status_code & 0x00000300) >> 8
        limit_map = {
            0: LimitBits.NONE, 1: LimitBits.LOW_LIMITED,
            2: LimitBits.HIGH_LIMITED, 3: LimitBits.CONSTANT,
        }
        limit_bits = limit_map.get(limit_val, LimitBits.NONE)

        return FFSignalStatus(severity=severity, limit_bits=limit_bits)

    @staticmethod
    def _encode_status(status: FFSignalStatus) -> int:
        """Encode FFSignalStatus into OPC-UA StatusCode integer."""
        from smart_pid_domain.enums import LimitBits, SignalSeverity

        severity_map = {
            SignalSeverity.GOOD: 0, SignalSeverity.UNCERTAIN: 1, SignalSeverity.BAD: 2,
        }
        limit_map = {
            LimitBits.NONE: 0, LimitBits.LOW_LIMITED: 1,
            LimitBits.HIGH_LIMITED: 2, LimitBits.CONSTANT: 3,
        }
        return (severity_map.get(status.severity, 2) << 30) | (
            limit_map.get(status.limit_bits, 0) << 8
        )
```

- [ ] **Step 2: Update register_controller to accept BKCAL node IDs**

Replace `register_controller` method:

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
    ) -> None:
        """Register a controller's OPC-UA node mappings."""
        with self._lock:
            self._controllers[controller_id] = {
                "pv": node_id_pv,
                "sp": node_id_sp,
                "co": node_id_co,
                "integral": node_id_integral,
                "bkcal_in": node_id_bkcal_in,
                "bkcal_out": node_id_bkcal_out,
            }
```

- [ ] **Step 3: Update _async_read_telemetry to read DataValue**

Replace `_async_read_telemetry`:

```python
    async def _async_read_telemetry(
        self, client, controller_id: int, nodes: dict[str, str],
    ) -> TelemetryFrame:
        """Async batch read of OPC-UA nodes with full DataValue (value + status + timestamp)."""
        from smart_pid_domain.models.signal import FFSignal

        node_ids_to_read = []
        keys = []
        for key in ("pv", "sp", "co", "bkcal_in"):
            nid = nodes.get(key, "")
            if nid:
                node_ids_to_read.append(client.get_node(nid))
                keys.append(key)

        integral_nid = nodes.get("integral", "")
        if integral_nid:
            node_ids_to_read.append(client.get_node(integral_nid))
            keys.append("integral")

        # Read full DataValue (value + StatusCode + SourceTimestamp)
        data_values = await client.read_data_value(node_ids_to_read)
        result: dict[str, FFSignal | float] = {}
        for key, dv in zip(keys, data_values, strict=True):
            if key == "integral":
                result[key] = float(dv.Value.Value) if dv.Value is not None else 0.0
            else:
                value = float(dv.Value.Value) if dv.Value is not None else 0.0
                status = self._decode_status(dv.StatusCode.value) if dv.StatusCode else FFSignalStatus()
                ts = dv.SourceTimestamp
                result[key] = FFSignal(value=value, status=status, timestamp=ts)

        now = datetime.now(UTC)
        return TelemetryFrame(
            controller_id=controller_id,
            pv=result.get("pv", FFSignal.good(0.0)),
            sp=result.get("sp", FFSignal.good(0.0)),
            co=result.get("co", FFSignal.good(0.0)),
            bkcal_in=result.get("bkcal_in", FFSignal.good(0.0)),
            integral_val=float(result.get("integral", 0.0)),
            timestamp=now,
        )
```

- [ ] **Step 4: Add write_bkcal_out method**

Add after `write_parameter`:

```python
    def write_bkcal_out(self, controller_id: int, signal: FFSignal) -> None:
        """Write BKCAL_OUT value and status to the controller's BKCAL_OUT node."""
        with self._lock:
            if controller_id not in self._controllers:
                raise KeyError(f"Controller {controller_id} not registered")
            node_id = self._controllers[controller_id].get("bkcal_out", "")
            client = self._client

        if not node_id:
            return  # No BKCAL_OUT node configured — skip silently
        if client is None or self.state != ConnectionState.ONLINE:
            raise ConnectionError("OPC-UA not connected")

        future = asyncio.run_coroutine_threadsafe(
            self._async_write_bkcal_out(client, node_id, signal),
            self._loop,
        )
        future.result(timeout=self._timeout_s)

    async def _async_write_bkcal_out(
        self, client, node_id: str, signal: FFSignal,
    ) -> None:
        """Write BKCAL_OUT with encoded StatusCode."""
        from asyncua import ua

        node = client.get_node(node_id)
        status_code = ua.StatusCode(self._encode_status(signal.status))
        dv = ua.DataValue(
            Value=ua.Variant(signal.value, ua.VariantType.Float),
            StatusCode=status_code,
            SourceTimestamp=signal.timestamp or datetime.now(UTC),
        )
        await node.write_data_value(dv)
```

- [ ] **Step 5: Add FFSignal import at top of file**

Add to the imports at the top of `opcua_adapter.py`:

```python
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus
```

- [ ] **Step 6: Run existing tests**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py
git commit -m "feat(opcua): read DataValue with StatusCode decoding, write BKCAL_OUT"
```

---

## Task 11: Update LoopManager, DBWorker, and Historian

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py:103-118`
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/workers/db_worker.py:78-91`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/historian.py:27-76`

- [ ] **Step 1: Update LoopManager imports**

In `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py`, the `set_mode` method has a local import of `BlockStatus` at line 108. Move it to the top-level imports and remove the local import:

Add to top-level imports:
```python
from smart_pid_core.domain.services.pid_mode_manager import BlockStatus, ModeManager
```

Remove line 108: `from smart_pid_core.domain.services.pid_mode_manager import BlockStatus`

Note: `BlockStatus()` now defaults to `FFSignal.good(0.0)` for pv and bkcal_in, so the `set_mode` method body needs no changes.

- [ ] **Step 2: Update DBWorker _process_message**

In `packages/smart_pid_core/src/smart_pid_core/application/workers/db_worker.py`, replace `_process_message` (lines 78-91). The method constructs `TelemetryFrame` from msgpack data — it now needs to deserialize FFSignal dicts:

```python
    def _process_message(self, msg: tuple[bytes, bytes]) -> None:
        _topic, payload = msg
        try:
            data = msgpack.unpackb(payload)

            def _to_signal(raw: dict | float | int) -> FFSignal:
                if isinstance(raw, (float, int)):
                    return FFSignal.good(float(raw))
                from smart_pid_domain.enums import LimitBits, SignalSeverity
                return FFSignal(
                    value=float(raw.get("value", 0.0)),
                    status=FFSignalStatus(
                        severity=SignalSeverity(raw.get("severity", "GOOD")),
                        limit_bits=LimitBits(raw.get("limit_bits", "NONE")),
                        sub_status=InitSubStatus(raw.get("sub_status", "NONE")),
                    ),
                )

            frame = TelemetryFrame(
                controller_id=data["controller_id"],
                pv=_to_signal(data["pv"]),
                sp=_to_signal(data["sp"]),
                co=_to_signal(data["co"]),
                bkcal_in=_to_signal(data.get("bkcal_in", 0.0)),
                integral_val=data["integral_val"],
                timestamp=datetime.fromisoformat(data["timestamp"]).replace(tzinfo=UTC),
            )
            self._buffer.append(frame)
        except (KeyError, ValueError, msgpack.UnpackException):
            pass
```

Update imports at top of db_worker.py:
```python
from smart_pid_domain.enums import InitSubStatus
from smart_pid_domain.models.signal import FFSignal, FFSignalStatus
from smart_pid_domain.models.telemetry import TelemetryFrame
```

Remove the old `SignalStatus` import.

- [ ] **Step 3: Update Historian write_batch**

In `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/historian.py`, update `write_batch` to extract `.value` from FFSignal fields (lines 27-43):

```python
    async def write_batch(self, frames: list[TelemetryFrame]) -> None:
        """Batch-insert telemetry frames. No-op for empty list."""
        if not frames:
            return
        rows = [
            (
                f.controller_id,
                f.timestamp.isoformat(),
                f.pv.value,
                f.sp.value,
                f.co.value,
                f.integral_val,
            )
            for f in frames
        ]
        await self._db.executemany(
            "INSERT INTO Log_Processo (controlador_id, timestamp, pv, sp, co, integral_val) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        await self._db.commit()
```

- [ ] **Step 4: Update Historian query**

Update `query` method (lines 51-77) to construct TelemetryFrame with FFSignal:

```python
    async def query(
        self,
        controller_id: int,
        start: datetime,
        end: datetime,
    ) -> list[TelemetryFrame]:
        """Return frames for a controller within [start, end] inclusive."""
        async with self._db.execute(
            "SELECT controlador_id, timestamp, pv, sp, co, integral_val "
            "FROM Log_Processo "
            "WHERE controlador_id = ? AND timestamp >= ? AND timestamp <= ? "
            "ORDER BY timestamp",
            (controller_id, start.isoformat(), end.isoformat()),
        ) as cur:
            rows = await cur.fetchall()

        from smart_pid_domain.models.signal import FFSignal

        results: list[TelemetryFrame] = []
        for row in rows:
            ts = datetime.fromisoformat(row[1])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            results.append(
                TelemetryFrame(
                    controller_id=row[0],
                    pv=FFSignal.good(row[2]),
                    sp=FFSignal.good(row[3]),
                    co=FFSignal.good(row[4]),
                    bkcal_in=FFSignal.good(0.0),
                    integral_val=row[5],
                    timestamp=ts,
                )
            )
        return results
```

Remove the `SignalStatus` import from the top of historian.py.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py \
      packages/smart_pid_core/src/smart_pid_core/application/workers/db_worker.py \
      packages/smart_pid_core/src/smart_pid_core/adapters/outbound/historian.py
git commit -m "fix: update LoopManager, DBWorker, Historian for FFSignal model changes"
```

---

## Task 12: Full Regression + Lint

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=60`
Expected: All tests PASS

- [ ] **Step 2: Run linter**

Run: `uv run --with ruff ruff check .`
Expected: No errors. If any, fix with `uv run --with ruff ruff check --fix .`

- [ ] **Step 3: Fix any remaining issues**

If tests fail or lint reports issues, fix them and run again until clean.

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -u
git commit -m "fix: address lint and test regressions from FF signals integration"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | New enums (SignalSeverity, LimitBits, InitSubStatus) | 3 |
| 2 | FFSignalStatus + FFSignal value objects | 14 |
| 3 | TelemetryFrame, ControlAction, TagBindings update | 5 + existing fixes |
| 4 | PID Engine — directional anti-windup | 6 |
| 5 | PID Engine — IMAN tracking | 4 |
| 6 | Mode Manager — cascade handshake | 13 |
| 7 | Events — CascadeHandshakeChanged | 2 |
| 8 | PIDWorker — FFSignal + cascade loop | existing updates |
| 9 | IOWorker — FFSignal serialization | existing |
| 10 | OPCUAAdapter — DataValue + BKCAL_OUT | existing |
| 11 | LoopManager + remaining consumers | existing |
| 12 | Full regression + lint | all |
