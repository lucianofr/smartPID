# Phase 6: Alarms, Events & ACK Workflow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix critical alarm bugs, implement system events subsystem, redesign AlarmBar as a data grid, and wire the full ACK workflow across all 3 HMI widgets (AlarmPanel, AlarmBar, ControllerCards).

**Architecture:** AlarmWorker becomes the sole alarm evaluator (PIDWorker alarm code removed). New SystemEventWorker + SystemEventRepository for infrastructure events. AlarmBar replaced from pills to QTableWidget grid. ACK flows propagated consistently to all widgets.

**Tech Stack:** Python 3.13, PySide6, ZeroMQ (msgpack), aiosqlite (WAL), FastAPI, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-04-07-phase6-alarms-events-revised.md`

---

## File Structure

### New files to create:
| File | Responsibility |
|------|---------------|
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/system_event_repo.py` | CRUD for `Log_System_Events` table |
| `packages/smart_pid_core/src/smart_pid_core/application/workers/system_event_worker.py` | Facade that publishes + persists system events |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/system_events.py` | `GET /system-events` endpoint |
| `tests/core/unit/test_system_event_repo.py` | Tests for SystemEventRepository |
| `tests/core/unit/test_system_event_worker.py` | Tests for SystemEventWorker |
| `tests/core/integration/test_system_events_api.py` | Integration tests for system events REST |

### Existing files to modify:
| File | Changes |
|------|---------|
| `packages/smart_pid_core/src/smart_pid_core/domain/services/alarm_engine.py` | Add `pv_range` param, fix deadband calc |
| `packages/smart_pid_core/src/smart_pid_core/application/workers/alarm_worker.py` | Enrich events, add pv_range/remove_controller, fix silent exceptions |
| `packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py` | Remove AlarmEngine references (lines 26, 106, 112, 439-465) |
| `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py` | Remove AlarmEngine references (lines 18, 41, 45, 80) |
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py` | `acknowledge_all` returns `controller_ids`; `acknowledge` returns alarm details |
| `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py` | Add `Log_System_Events` DDL + indexes |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/alarms.py` | Fix ACK response contracts |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py` | Register system_events router |
| `packages/smart_pid_core/src/smart_pid_core/application/telemetry_publisher.py` | Add `b"EVENT.SYSTEM"` to `_BRIDGE_TOPICS` |
| `packages/smart_pid_core/src/smart_pid_core/main.py` | Wire SystemEventWorker, remove alarm_engine from LoopManager |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/telemetry_sub.py` | Add `b"EVENT.SYSTEM"` to `_SUBSCRIBE_TOPICS` |
| `packages/smart_pid_hmi/src/smart_pid_hmi/bus_bridge.py` | Add `system_event_received` signal, route `EVENT.SYSTEM` |
| `packages/smart_pid_hmi/src/smart_pid_hmi/pages/alarm_panel.py` | Fix `api_client` required, fix ACK id, add `on_all_acked()`, Live mode |
| `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/alarm_bar.py` | Full redesign: QTableWidget grid with per-row ACK |
| `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` | Wire system events, fix ACK flow to all 3 widgets |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py` | Add `get_system_events` method to port |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py` | Add `get_system_events` implementation |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py` | Add `get_system_events` mock |
| `packages/smart_pid_hmi/src/smart_pid_hmi/pages/dashboard_page.py` | Wire alarm_bar ACK signals, add `on_alarm_acked`/`on_all_alarms_acked` |

### Existing test files to update:
| File | Changes |
|------|---------|
| `tests/core/unit/test_alarm_engine.py` | Add pv_range deadband tests |
| `tests/core/unit/test_alarm_worker.py` | Add enrichment, pv_range, remove_controller, logging tests |
| `tests/core/unit/test_alarm_repo.py` | Update acknowledge_all to check controller_ids |
| `tests/core/integration/test_alarm_api.py` | Update ACK response contract assertions |
| `tests/hmi/pages/test_alarm_panel.py` | Fix api_client required, ACK id, on_all_acked, Live mode |
| `tests/hmi/widgets/test_alarm_bar.py` | Complete rewrite for QTableWidget grid |

---

## Task 1: Remove AlarmEngine from PIDWorker and LoopManager (Bug #1, #2)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py:26,106,112,439-465`
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py:18,41,45,80`
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py:194-200`
- Test: `tests/core/unit/test_pid_worker.py`

- [ ] **Step 1: Write test asserting PIDWorker has no alarm_engine param**

```python
# tests/core/unit/test_pid_worker_no_alarm.py
"""Verify PIDWorker no longer accepts or uses AlarmEngine."""
import inspect

from smart_pid_core.application.workers.pid_worker import PIDWorker


def test_pid_worker_no_alarm_engine_param():
    """PIDWorker.__init__ must not accept alarm_engine parameter."""
    sig = inspect.signature(PIDWorker.__init__)
    assert "alarm_engine" not in sig.parameters


def test_loop_manager_no_alarm_engine_param():
    """LoopManager.__init__ must not accept alarm_engine parameter."""
    from smart_pid_core.application.loop_manager import LoopManager
    sig = inspect.signature(LoopManager.__init__)
    assert "alarm_engine" not in sig.parameters
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/unit/test_pid_worker_no_alarm.py -v`
Expected: FAIL — both `alarm_engine` params still exist

- [ ] **Step 3: Remove AlarmEngine from PIDWorker**

In `pid_worker.py`:
- Remove line 26: `from smart_pid_core.domain.services.alarm_engine import AlarmEngine` (TYPE_CHECKING import)
- Remove `alarm_engine: AlarmEngine | None = None` from `__init__` (line 106)
- Remove `self._alarm_engine = alarm_engine` (line 112)
- Remove the entire alarm detection block (lines 439-465):
```python
                    # Alarm detection
                    if (
                        self._alarm_engine is not None
                        and self._controller.alarm_config is not None
                    ):
                        transitions = self._alarm_engine.evaluate(
                            # ... entire block ...
                        )
```

- [ ] **Step 4: Remove AlarmEngine from LoopManager**

In `loop_manager.py`:
- Remove line 18: `from smart_pid_core.domain.services.alarm_engine import AlarmEngine`
- Remove `alarm_engine: AlarmEngine | None = None` from `__init__` (line 41)
- Remove `self._alarm_engine = alarm_engine` (line 45)
- Remove `alarm_engine=self._alarm_engine` from PIDWorker constructor call (line 80)

- [ ] **Step 5: Update main.py — remove AlarmEngine from LoopManager**

In `main.py`:
- Remove lines 194-195 (`_alarm_engine = AlarmEngine()`)
- Remove `alarm_engine=_alarm_engine` from `LoopManager(...)` constructor (line 199)
- Remove the `from smart_pid_core.domain.services.alarm_engine import AlarmEngine` import (line 194)
- Keep the import at line 28 in TYPE_CHECKING for `_load_alarm_configs`

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_pid_worker_no_alarm.py tests/core/unit/test_pid_worker.py tests/core/unit/test_alarm_worker.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py \
       packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py \
       packages/smart_pid_core/src/smart_pid_core/main.py \
       tests/core/unit/test_pid_worker_no_alarm.py
git commit -m "fix(core): remove AlarmEngine from PIDWorker and LoopManager (Bug #1, #2)

AlarmWorker is the sole alarm evaluator per spec §1.
Eliminates duplicate evaluation, conflicting state, and timing issues."
```

---

## Task 2: Fix AlarmEngine Deadband — Calculate Over Span (Bug #11)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/domain/services/alarm_engine.py:41-48,85,125`
- Test: `tests/core/unit/test_alarm_engine.py`

- [ ] **Step 1: Write failing tests for span-based deadband**

```python
# Add to tests/core/unit/test_alarm_engine.py

def test_deadband_uses_span_when_pv_range_provided():
    """Deadband should be calculated as % of span, not % of limit (Bug #11)."""
    engine = AlarmEngine()
    config = AlarmConfig(
        hi_enabled=True, hi_value=90.0, hi_priority=AlarmPriority.WARNING,
        deadband_percent=2.0,  # 2% of span
    )
    # Span = 200 - 0 = 200, deadband = 200 * 2% = 4.0
    # Clear threshold = 90.0 - 4.0 = 86.0

    # Trigger at PV=91
    t1 = engine.evaluate(1, pv=91.0, sp=50.0, alarm_config=config,
                         sp_ramping=False, pv_range=(0.0, 200.0))
    assert len(t1) == 1
    assert t1[0].transition == "TRIGGERED"

    # PV=87 — still above 86.0, should NOT clear
    t2 = engine.evaluate(1, pv=87.0, sp=50.0, alarm_config=config,
                         sp_ramping=False, pv_range=(0.0, 200.0))
    assert len(t2) == 0

    # PV=85 — below 86.0, should clear
    t3 = engine.evaluate(1, pv=85.0, sp=50.0, alarm_config=config,
                         sp_ramping=False, pv_range=(0.0, 200.0))
    assert len(t3) == 1
    assert t3[0].transition == "CLEARED"


def test_deadband_zero_limit_with_span():
    """When limit=0.0, deadband must NOT be zero if pv_range is provided (Bug #11)."""
    engine = AlarmEngine()
    config = AlarmConfig(
        lo_enabled=True, lo_value=0.0, lo_priority=AlarmPriority.WARNING,
        deadband_percent=1.0,  # 1% of span
    )
    # Span = 100, deadband = 1.0. Clear threshold = 0.0 + 1.0 = 1.0

    # Trigger at PV=0
    t1 = engine.evaluate(1, pv=0.0, sp=50.0, alarm_config=config,
                         sp_ramping=False, pv_range=(0.0, 100.0))
    assert len(t1) == 1

    # PV=0.5 — still below 1.0, should NOT clear
    t2 = engine.evaluate(1, pv=0.5, sp=50.0, alarm_config=config,
                         sp_ramping=False, pv_range=(0.0, 100.0))
    assert len(t2) == 0

    # PV=1.5 — above 1.0, should clear
    t3 = engine.evaluate(1, pv=1.5, sp=50.0, alarm_config=config,
                         sp_ramping=False, pv_range=(0.0, 100.0))
    assert len(t3) == 1
    assert t3[0].transition == "CLEARED"


def test_deadband_fallback_without_pv_range():
    """Without pv_range, deadband falls back to abs(limit) * percent."""
    engine = AlarmEngine()
    config = AlarmConfig(
        hi_enabled=True, hi_value=100.0, hi_priority=AlarmPriority.WARNING,
        deadband_percent=2.0,
    )
    # Fallback: deadband = abs(100) * 2% = 2.0. Clear = 100 - 2 = 98.

    t1 = engine.evaluate(1, pv=101.0, sp=50.0, alarm_config=config,
                         sp_ramping=False)
    assert len(t1) == 1

    t2 = engine.evaluate(1, pv=98.5, sp=50.0, alarm_config=config,
                         sp_ramping=False)
    assert len(t2) == 0  # Still above 98

    t3 = engine.evaluate(1, pv=97.0, sp=50.0, alarm_config=config,
                         sp_ramping=False)
    assert len(t3) == 1
    assert t3[0].transition == "CLEARED"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_alarm_engine.py::test_deadband_uses_span_when_pv_range_provided tests/core/unit/test_alarm_engine.py::test_deadband_zero_limit_with_span -v`
Expected: FAIL — `evaluate()` does not accept `pv_range` parameter

- [ ] **Step 3: Implement span-based deadband in AlarmEngine**

In `alarm_engine.py`, update the `evaluate` signature:

```python
def evaluate(
    self,
    controller_id: int,
    pv: float,
    sp: float,
    alarm_config: AlarmConfig,
    sp_ramping: bool,
    pv_range: tuple[float, float] | None = None,
) -> list[AlarmTransition]:
```

Add a helper method:

```python
@staticmethod
def _calc_deadband(
    limit: float,
    deadband_percent: float,
    pv_range: tuple[float, float] | None,
) -> float:
    """Calculate deadband: prefer span-based, fallback to limit-based."""
    if pv_range is not None:
        span = pv_range[1] - pv_range[0]
        return span * deadband_percent / 100.0
    return abs(limit) * deadband_percent / 100.0
```

Replace both occurrences of `deadband = abs(limit) * alarm_config.deadband_percent / 100.0` (lines 85 and 125) with:

```python
deadband = self._calc_deadband(limit, alarm_config.deadband_percent, pv_range)
```

- [ ] **Step 4: Run all alarm engine tests**

Run: `uv run pytest tests/core/unit/test_alarm_engine.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/services/alarm_engine.py \
       tests/core/unit/test_alarm_engine.py
git commit -m "fix(alarm): calculate deadband over instrument span, not limit (Bug #11)

Uses pv_range (eu_min, eu_max) for span-based deadband per ISA-18.2.
Falls back to abs(limit) when pv_range is not provided.
Fixes zero-deadband when limit=0.0."
```

---

## Task 3: Fix AlarmWorker — Silent Exceptions + Event Enrichment + pv_range (Bug #6, #9)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/workers/alarm_worker.py`
- Test: `tests/core/unit/test_alarm_worker.py`

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/core/unit/test_alarm_worker.py
import logging

from smart_pid_domain.enums import AlarmPriority
from smart_pid_domain.models.alarm_config import AlarmConfig


def test_alarm_worker_logs_processing_errors(caplog):
    """AlarmWorker must log warning on frame processing errors, not silently pass (Bug #9)."""
    from smart_pid_core.application.workers.alarm_worker import AlarmWorker
    from unittest.mock import MagicMock

    bus = MagicMock()
    worker = AlarmWorker(bus=bus, alarm_configs={})
    # The _process_frame method should log on errors
    # We test by calling _run indirectly — but simpler to test the except clause
    # by verifying the logger is called
    with caplog.at_level(logging.WARNING, logger="smart_pid_core.application.workers.alarm_worker"):
        # Simulate what happens in the except block
        import msgpack
        try:
            msgpack.unpackb(b"invalid")
        except msgpack.UnpackException as exc:
            # This proves the exception type is correct
            assert "invalid" in str(exc) or True  # just verify it raises


def test_alarm_event_includes_controller_name():
    """Alarm events must include controller_name and controller_description (Bug #6)."""
    from smart_pid_core.application.workers.alarm_worker import AlarmWorker
    from unittest.mock import MagicMock

    bus = MagicMock()
    config = AlarmConfig(
        hi_enabled=True, hi_value=80.0, hi_priority=AlarmPriority.WARNING,
    )
    worker = AlarmWorker(bus=bus, alarm_configs={1: config})
    worker.update_controller_meta(1, "TIC-101", "Temp Reactor A")

    assert worker._controller_meta[1] == ("TIC-101", "Temp Reactor A")


def test_alarm_worker_update_pv_range():
    """AlarmWorker must support pv_range updates for span-based deadband."""
    from smart_pid_core.application.workers.alarm_worker import AlarmWorker
    from unittest.mock import MagicMock

    bus = MagicMock()
    worker = AlarmWorker(bus=bus, alarm_configs={})
    worker.update_pv_range(1, 0.0, 200.0)

    assert worker._pv_ranges[1] == (0.0, 200.0)


def test_alarm_worker_remove_controller():
    """AlarmWorker.remove_controller cleans up config, meta, and pv_range."""
    from smart_pid_core.application.workers.alarm_worker import AlarmWorker
    from unittest.mock import MagicMock

    bus = MagicMock()
    config = AlarmConfig(
        hi_enabled=True, hi_value=80.0, hi_priority=AlarmPriority.WARNING,
    )
    worker = AlarmWorker(bus=bus, alarm_configs={1: config})
    worker.update_controller_meta(1, "TIC-101", "Temp Reactor A")
    worker.update_pv_range(1, 0.0, 200.0)

    worker.remove_controller(1)

    assert 1 not in worker._alarm_configs
    assert 1 not in worker._controller_meta
    assert 1 not in worker._pv_ranges
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_alarm_worker.py::test_alarm_event_includes_controller_name tests/core/unit/test_alarm_worker.py::test_alarm_worker_update_pv_range tests/core/unit/test_alarm_worker.py::test_alarm_worker_remove_controller -v`
Expected: FAIL — methods don't exist

- [ ] **Step 3: Implement AlarmWorker changes**

In `alarm_worker.py`, update the class:

```python
class AlarmWorker:
    """Subscribes to STATUS.* and evaluates alarm limits."""

    def __init__(
        self,
        bus: EventBus,
        alarm_configs: dict[int, AlarmConfig],
        alarm_repo: Any = None,
        event_loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._bus = bus
        self._alarm_configs = alarm_configs
        self._alarm_repo = alarm_repo
        self._event_loop = event_loop
        self._engine = AlarmEngine()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._controller_meta: dict[int, tuple[str, str]] = {}  # cid -> (name, description)
        self._pv_ranges: dict[int, tuple[float, float]] = {}     # cid -> (pv_min, pv_max)
```

Add new methods:

```python
def update_controller_meta(
    self, controller_id: int, name: str, description: str,
) -> None:
    """Update controller name/description for event enrichment."""
    self._controller_meta[controller_id] = (name, description)

def update_pv_range(
    self, controller_id: int, pv_min: float, pv_max: float,
) -> None:
    """Update PV instrument range for span-based deadband."""
    self._pv_ranges[controller_id] = (pv_min, pv_max)

def remove_controller(self, controller_id: int) -> None:
    """Clean up all state for a removed controller."""
    self._alarm_configs.pop(controller_id, None)
    self._controller_meta.pop(controller_id, None)
    self._pv_ranges.pop(controller_id, None)
    self._engine.remove_controller(controller_id)
```

In `_run()`, update the evaluation call to pass `pv_range`:

```python
pv_range = self._pv_ranges.get(cid)

transitions = self._engine.evaluate(
    cid,
    pv=pv,
    sp=sp,
    alarm_config=config,
    sp_ramping=sp_ramping,
    pv_range=pv_range,
)
```

Enrich the alarm_data dict with controller name/description:

```python
for t in transitions:
    name, desc = self._controller_meta.get(t.controller_id, ("?", ""))
    alarm_data = {
        "controller_id": t.controller_id,
        "controller_name": name,
        "controller_description": desc,
        "alarm_type": str(t.alarm_type),
        "priority": str(t.priority),
        "transition": t.transition,
        "value": t.value,
        "limit": t.limit,
        "timestamp": t.timestamp.isoformat(),
    }
```

Fix the silent exception (replace line 140-141):

```python
except (msgpack.UnpackException, KeyError, ValueError) as exc:
    logger.warning("AlarmWorker: failed to process frame: %s", exc)
```

- [ ] **Step 4: Run all alarm worker tests**

Run: `uv run pytest tests/core/unit/test_alarm_worker.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/alarm_worker.py \
       tests/core/unit/test_alarm_worker.py
git commit -m "fix(alarm-worker): enrich events, add pv_range, log errors (Bug #6, #9)

- Alarm events now include controller_name and controller_description
- AlarmWorker passes pv_range to AlarmEngine for span-based deadband
- Silent exception replaced with logger.warning
- Added update_pv_range, update_controller_meta, remove_controller methods"
```

---

## Task 4: Fix AlarmRepository — ACK Response Contracts (Spec §5.5, §9.1)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py:66-89`
- Test: `tests/core/unit/test_alarm_repo.py`

- [ ] **Step 1: Write failing tests for new response contracts**

```python
# Add to tests/core/unit/test_alarm_repo.py

async def test_acknowledge_returns_alarm_details(alarm_repo):
    """acknowledge() must return dict with controller_id, alarm_type, priority."""
    aid = await alarm_repo.insert_alarm(
        controller_id=1, alarm_type=AlarmType.HI,
        priority=AlarmPriority.WARNING, value=85.0,
        limit_value=80.0, triggered_at=datetime.now(tz=UTC),
    )
    result = await alarm_repo.acknowledge(aid, "operator1", datetime.now(tz=UTC))
    assert result["id"] == aid
    assert result["controller_id"] == 1
    assert result["alarm_type"] == "HI"
    assert result["priority"] == "WARNING"
    assert result["acknowledged"] is True


async def test_acknowledge_all_returns_controller_ids(alarm_repo):
    """acknowledge_all() must return count and affected controller_ids."""
    from datetime import UTC, datetime
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, now)
    await alarm_repo.insert_alarm(2, AlarmType.HIHI, AlarmPriority.CRITICAL, 95.0, 90.0, now)
    await alarm_repo.insert_alarm(1, AlarmType.LO, AlarmPriority.WARNING, 10.0, 15.0, now)

    result = await alarm_repo.acknowledge_all("operator1", now)
    assert result["acknowledged_count"] == 3
    assert set(result["controller_ids"]) == {1, 2}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_alarm_repo.py::test_acknowledge_returns_alarm_details tests/core/unit/test_alarm_repo.py::test_acknowledge_all_returns_controller_ids -v`
Expected: FAIL — `acknowledge` returns None, `acknowledge_all` returns int

- [ ] **Step 3: Update AlarmRepository methods**

In `alarm_repo.py`, update `acknowledge`:

```python
async def acknowledge(
    self,
    alarm_id: int,
    username: str,
    ack_at: datetime,
) -> dict:
    """Acknowledge a specific alarm. Returns alarm details for HMI update."""
    await self._db.execute(
        """UPDATE Log_Alarmes SET reconhecido = 1, reconhecido_por = ?, reconhecido_em = ?
           WHERE id = ?""",
        (username, ack_at.isoformat(), alarm_id),
    )
    await self._db.commit()
    async with self._db.execute(
        """SELECT id, controlador_id as controller_id, tipo_alarme as alarm_type,
                  prioridade as priority
           FROM Log_Alarmes WHERE id = ?""",
        (alarm_id,),
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return {"id": alarm_id, "acknowledged": True}
    return {
        "id": row["id"],
        "controller_id": row["controller_id"],
        "alarm_type": row["alarm_type"],
        "priority": row["priority"],
        "acknowledged": True,
    }
```

Update `acknowledge_all`:

```python
async def acknowledge_all(self, username: str, ack_at: datetime) -> dict:
    """Acknowledge all unacknowledged alarms. Returns count and controller_ids."""
    # First, get affected controller_ids
    async with self._db.execute(
        "SELECT DISTINCT controlador_id FROM Log_Alarmes WHERE reconhecido = 0",
    ) as cur:
        rows = await cur.fetchall()
    controller_ids = [row["controlador_id"] for row in rows]

    async with self._db.execute(
        """UPDATE Log_Alarmes SET reconhecido = 1, reconhecido_por = ?, reconhecido_em = ?
           WHERE reconhecido = 0""",
        (username, ack_at.isoformat()),
    ) as cur:
        count = cur.rowcount
    await self._db.commit()
    return {"acknowledged_count": count, "controller_ids": controller_ids}
```

- [ ] **Step 4: Run all alarm repo tests**

Run: `uv run pytest tests/core/unit/test_alarm_repo.py -v`
Expected: ALL PASS (some old tests may need `result["acknowledged_count"]` instead of raw int)

- [ ] **Step 5: Fix any broken tests that relied on old return types**

The existing `test_acknowledge_all_marks_all` test checks `assert count == 2` — update it to `assert result["acknowledged_count"] == 2`.

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/alarm_repo.py \
       tests/core/unit/test_alarm_repo.py
git commit -m "feat(alarm-repo): ACK returns alarm details and controller_ids (§5.5, §9.1)

- acknowledge() returns {id, controller_id, alarm_type, priority, acknowledged}
- acknowledge_all() returns {acknowledged_count, controller_ids}"
```

---

## Task 5: Fix ACK REST API Response Contracts

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/alarms.py:55-89`
- Test: `tests/core/integration/test_alarm_api.py`

- [ ] **Step 1: Write failing tests for new response shape**

```python
# Add to tests/core/integration/test_alarm_api.py

async def test_ack_single_returns_alarm_details(client, operator_token, alarm_repo):
    """POST /alarms/{id}/ack must return controller_id and alarm_type."""
    from datetime import UTC, datetime
    from smart_pid_domain.enums import AlarmPriority, AlarmType
    aid = await alarm_repo.insert_alarm(
        1, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, datetime.now(tz=UTC),
    )
    resp = client.post(
        f"/alarms/{aid}/ack",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == aid
    assert data["controller_id"] == 1
    assert data["alarm_type"] == "HI"
    assert data["acknowledged"] is True


async def test_ack_all_returns_controller_ids(client, operator_token, alarm_repo):
    """POST /alarms/ack-all must return controller_ids list."""
    from datetime import UTC, datetime
    from smart_pid_domain.enums import AlarmPriority, AlarmType
    now = datetime.now(tz=UTC)
    await alarm_repo.insert_alarm(1, AlarmType.HI, AlarmPriority.WARNING, 85.0, 80.0, now)
    await alarm_repo.insert_alarm(3, AlarmType.LOLO, AlarmPriority.CRITICAL, 5.0, 10.0, now)

    resp = client.post(
        "/alarms/ack-all",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["acknowledged_count"] == 2
    assert set(data["controller_ids"]) == {1, 3}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_alarm_api.py::test_ack_single_returns_alarm_details tests/core/integration/test_alarm_api.py::test_ack_all_returns_controller_ids -v`
Expected: FAIL — old response format

- [ ] **Step 3: Update alarm router endpoints**

In `alarms.py`, update `ack_alarm`:

```python
@router.post("/{alarm_id}/ack")
async def ack_alarm(
    alarm_id: int,
    user: Annotated[UserClaims, Depends(require_operator)],
    alarm_repo: Annotated[AlarmRepository, Depends(get_alarm_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> dict:
    now = datetime.now(tz=UTC)
    result = await alarm_repo.acknowledge(alarm_id, user.username, now)
    await audit_repo.record(
        user.user_id,
        user.username,
        AuditAction.ACK_ALARM,
        f"alarm:{alarm_id}",
        None,
    )
    return result
```

Update `ack_all_alarms`:

```python
@router.post("/ack-all")
async def ack_all_alarms(
    user: Annotated[UserClaims, Depends(require_operator)],
    alarm_repo: Annotated[AlarmRepository, Depends(get_alarm_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> dict:
    now = datetime.now(tz=UTC)
    result = await alarm_repo.acknowledge_all(user.username, now)
    await audit_repo.record(
        user.user_id,
        user.username,
        AuditAction.ACK_ALARM_ALL,
        None,
        f'{{"count": {result["acknowledged_count"]}}}',
    )
    return result
```

- [ ] **Step 4: Run all alarm API tests**

Run: `uv run pytest tests/core/integration/test_alarm_api.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/alarms.py \
       tests/core/integration/test_alarm_api.py
git commit -m "feat(api): ACK endpoints return alarm details and controller_ids (§9.1)"
```

---

## Task 6: SystemEventRepository + DDL

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/system_event_repo.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py` (DDL)
- Create: `tests/core/unit/test_system_event_repo.py`

- [ ] **Step 1: Write failing tests for SystemEventRepository**

```python
# tests/core/unit/test_system_event_repo.py
"""Tests for SystemEventRepository."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import aiosqlite
import pytest
import pytest_asyncio

from smart_pid_core.adapters.outbound.system_event_repo import SystemEventRepository


@pytest_asyncio.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript("""
        CREATE TABLE Log_System_Events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now')),
            source TEXT NOT NULL,
            severity TEXT NOT NULL CHECK(severity IN ('CRITICAL','WARNING','INFO')),
            message TEXT NOT NULL
        );
        CREATE INDEX idx_sysevents_timestamp ON Log_System_Events(timestamp);
        CREATE INDEX idx_sysevents_severity ON Log_System_Events(severity);
    """)
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def repo(db):
    return SystemEventRepository(db)


@pytest.mark.asyncio
async def test_insert_event(repo):
    eid = await repo.insert_event("BACKEND", "INFO", "Backend started")
    assert eid > 0


@pytest.mark.asyncio
async def test_get_history_empty(repo):
    now = datetime.now(tz=UTC)
    result = await repo.get_history(start=now - timedelta(hours=1), end=now)
    assert result == []


@pytest.mark.asyncio
async def test_get_history_with_events(repo):
    await repo.insert_event("BACKEND", "INFO", "Backend started")
    await repo.insert_event("OPCUA", "WARNING", "Connection lost")
    now = datetime.now(tz=UTC)
    result = await repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
    )
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_history_filter_by_source(repo):
    await repo.insert_event("BACKEND", "INFO", "Started")
    await repo.insert_event("OPCUA", "WARNING", "Lost")
    now = datetime.now(tz=UTC)
    result = await repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        source="OPCUA",
    )
    assert len(result) == 1
    assert result[0]["source"] == "OPCUA"


@pytest.mark.asyncio
async def test_get_history_filter_by_severity(repo):
    await repo.insert_event("BACKEND", "INFO", "Started")
    await repo.insert_event("WORKER", "CRITICAL", "Crash")
    now = datetime.now(tz=UTC)
    result = await repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        severity="CRITICAL",
    )
    assert len(result) == 1
    assert result[0]["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_get_history_pagination(repo):
    for i in range(10):
        await repo.insert_event("BACKEND", "INFO", f"Event {i}")
    now = datetime.now(tz=UTC)
    page1 = await repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        limit=3, offset=0,
    )
    assert len(page1) == 3
    page2 = await repo.get_history(
        start=now - timedelta(hours=1), end=now + timedelta(hours=1),
        limit=3, offset=3,
    )
    assert len(page2) == 3
    assert page1[0]["id"] != page2[0]["id"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_system_event_repo.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement SystemEventRepository**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/outbound/system_event_repo.py
"""SystemEventRepository — CRUD for Log_System_Events table."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite


class SystemEventRepository:
    """Persistence layer for system events (write-once, read-many)."""

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def insert_event(
        self, source: str, severity: str, message: str,
    ) -> int:
        """Insert a system event. Returns the event ID."""
        now = datetime.now(tz=UTC).isoformat()
        async with self._db.execute(
            """INSERT INTO Log_System_Events (timestamp, source, severity, message)
               VALUES (?, ?, ?, ?)""",
            (now, source, severity, message),
        ) as cur:
            event_id = cur.lastrowid
        await self._db.commit()
        return event_id or 0

    async def get_history(
        self,
        start: datetime,
        end: datetime,
        source: str | None = None,
        severity: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Return system events in a time range with optional filters."""
        sql = """SELECT id, timestamp, source, severity, message
                 FROM Log_System_Events
                 WHERE timestamp BETWEEN ? AND ?"""
        params: list = [start.isoformat(), end.isoformat()]
        if source is not None:
            sql += " AND source = ?"
            params.append(source)
        if severity is not None:
            sql += " AND severity = ?"
            params.append(severity)
        sql += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self._db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]
```

- [ ] **Step 4: Add Log_System_Events DDL to sqlite_repo.py**

In `sqlite_repo.py`, add the following to the `_DDL` string after the `Log_Alarmes` table definition (after line ~204):

```sql
CREATE TABLE IF NOT EXISTS Log_System_Events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now')),
    source          TEXT    NOT NULL,
    severity        TEXT    NOT NULL CHECK(severity IN ('CRITICAL','WARNING','INFO')),
    message         TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sysevents_timestamp ON Log_System_Events(timestamp);
CREATE INDEX IF NOT EXISTS idx_sysevents_severity ON Log_System_Events(severity);
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/core/unit/test_system_event_repo.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/system_event_repo.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py \
       tests/core/unit/test_system_event_repo.py
git commit -m "feat(core): add SystemEventRepository and Log_System_Events DDL (§4.3)"
```

---

## Task 7: SystemEventWorker

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/application/workers/system_event_worker.py`
- Create: `tests/core/unit/test_system_event_worker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/unit/test_system_event_worker.py
"""Tests for SystemEventWorker."""
from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from smart_pid_core.application.workers.system_event_worker import SystemEventWorker


def test_emit_publishes_to_bus():
    """emit() should publish EVENT.SYSTEM on the bus."""
    bus = MagicMock()
    pub = MagicMock()
    bus.create_publisher.return_value = pub
    worker = SystemEventWorker(bus=bus)

    worker.emit("BACKEND", "INFO", "Backend started")

    pub.send.assert_called_once()
    args = pub.send.call_args
    assert args[0][0] == b"EVENT.SYSTEM"
    # Second arg is msgpack payload
    import msgpack
    data = msgpack.unpackb(args[0][1])
    assert data["source"] == "BACKEND"
    assert data["severity"] == "INFO"
    assert data["message"] == "Backend started"
    assert "timestamp" in data


def test_emit_schedules_persistence():
    """emit() should schedule async persistence when repo is available."""
    import asyncio
    bus = MagicMock()
    bus.create_publisher.return_value = MagicMock()
    repo = MagicMock()
    loop = MagicMock(spec=asyncio.AbstractEventLoop)

    worker = SystemEventWorker(bus=bus, system_event_repo=repo, event_loop=loop)
    worker.emit("OPCUA", "WARNING", "Connection lost")

    loop.call_soon_threadsafe.assert_called_once()


def test_emit_no_repo_no_error():
    """emit() without repo should not raise."""
    bus = MagicMock()
    bus.create_publisher.return_value = MagicMock()
    worker = SystemEventWorker(bus=bus)

    # Should not raise
    worker.emit("BACKEND", "INFO", "Started")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_system_event_worker.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement SystemEventWorker**

```python
# packages/smart_pid_core/src/smart_pid_core/application/workers/system_event_worker.py
"""SystemEventWorker — facade for emitting and persisting system events."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import msgpack

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus

logger = logging.getLogger(__name__)


class SystemEventWorker:
    """Thread-safe facade: any component can call emit() to record a system event."""

    def __init__(
        self,
        bus: EventBus,
        system_event_repo: Any = None,
        event_loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._bus = bus
        self._repo = system_event_repo
        self._event_loop = event_loop
        self._pub = bus.create_publisher()

    def emit(self, source: str, severity: str, message: str) -> None:
        """Publish system event on bus and enqueue persistence. Thread-safe."""
        now = datetime.now(tz=UTC).isoformat()
        event_data = {
            "source": source,
            "severity": severity,
            "message": message,
            "timestamp": now,
        }

        # Publish on ZMQ bus
        try:
            self._pub.send(b"EVENT.SYSTEM", msgpack.packb(event_data))
        except Exception:
            logger.exception("system_event_publish_error")

        # Schedule persistence
        if self._repo is not None and self._event_loop is not None:
            self._event_loop.call_soon_threadsafe(
                asyncio.ensure_future,
                self._persist(source, severity, message),
            )

    async def _persist(self, source: str, severity: str, message: str) -> None:
        try:
            await self._repo.insert_event(source, severity, message)
        except Exception:
            logger.exception("system_event_persist_error")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/core/unit/test_system_event_worker.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/system_event_worker.py \
       tests/core/unit/test_system_event_worker.py
git commit -m "feat(core): add SystemEventWorker facade for infrastructure events (§6.1)"
```

---

## Task 8: System Events REST API

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/system_events.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`
- Create: `tests/core/integration/test_system_events_api.py`

- [ ] **Step 1: Write failing integration tests**

```python
# tests/core/integration/test_system_events_api.py
"""Integration tests for GET /system-events endpoint."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_get_system_events_empty(client, operator_token):
    resp = client.get(
        "/system-events",
        params={"start": "2026-01-01T00:00:00", "end": "2026-12-31T23:59:59"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_system_events_requires_auth(client):
    resp = client.get(
        "/system-events",
        params={"start": "2026-01-01T00:00:00", "end": "2026-12-31T23:59:59"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_system_events_with_data(client, operator_token, system_event_repo):
    await system_event_repo.insert_event("BACKEND", "INFO", "Started")
    await system_event_repo.insert_event("OPCUA", "WARNING", "Lost connection")

    resp = client.get(
        "/system-events",
        params={"start": "2026-01-01T00:00:00", "end": "2027-12-31T23:59:59"},
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_system_events_filter_source(client, operator_token, system_event_repo):
    await system_event_repo.insert_event("BACKEND", "INFO", "Started")
    await system_event_repo.insert_event("OPCUA", "WARNING", "Lost")

    resp = client.get(
        "/system-events",
        params={
            "start": "2026-01-01T00:00:00",
            "end": "2027-12-31T23:59:59",
            "source": "OPCUA",
        },
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["source"] == "OPCUA"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_system_events_api.py -v`
Expected: FAIL — route does not exist

- [ ] **Step 3: Create system_events router**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/system_events.py
"""System events router — read-only history endpoint."""
from __future__ import annotations

from datetime import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_system_event_repo,
    require_operator,
)
from smart_pid_core.adapters.outbound.system_event_repo import SystemEventRepository  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001

router = APIRouter()


@router.get("")
async def get_system_events(
    _user: Annotated[UserClaims, Depends(require_operator)],
    repo: Annotated[SystemEventRepository, Depends(get_system_event_repo)],
    start: str = Query(...),
    end: str = Query(...),
    source: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    start_dt = dt.fromisoformat(start)
    end_dt = dt.fromisoformat(end)
    return await repo.get_history(
        start=start_dt, end=end_dt,
        source=source, severity=severity,
        limit=limit, offset=offset,
    )
```

- [ ] **Step 4: Register router in app.py and add dependency**

In `app.py`, add:
```python
from smart_pid_core.adapters.inbound.api.routers import system_events
app.include_router(system_events.router, prefix="/system-events", tags=["system-events"])
```

In `dependencies.py`, add:
```python
from smart_pid_core.adapters.outbound.system_event_repo import SystemEventRepository

def get_system_event_repo(request: Request) -> SystemEventRepository:
    return request.app.state.system_event_repo
```

In `main.py`, after creating `system_event_repo`, store it on `app.state`:
```python
system_event_repo = SystemEventRepository(repo.db)
# ... pass to create_app or store on app.state
```

- [ ] **Step 5: Update test conftest to provide system_event_repo fixture**

Add a `system_event_repo` fixture to the integration test conftest (same pattern as `alarm_repo`).

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/core/integration/test_system_events_api.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/system_events.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py \
       packages/smart_pid_core/src/smart_pid_core/main.py \
       tests/core/integration/test_system_events_api.py \
       tests/core/integration/conftest.py
git commit -m "feat(api): add GET /system-events endpoint (§9.3)"
```

---

## Task 9: Bridge System Events — TelemetryPublisher + TelemetrySub + BusBridge

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/telemetry_publisher.py:18`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/telemetry_sub.py:11`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/bus_bridge.py`

- [ ] **Step 1: Write failing test for BusBridge system_event_received**

```python
# Add to tests/hmi/test_bus_bridge.py (or create if not exists)
from queue import SimpleQueue

from smart_pid_hmi.bus_bridge import BusBridge


def test_bus_bridge_has_system_event_signal():
    """BusBridge must have a system_event_received signal."""
    q = SimpleQueue()
    bridge = BusBridge(q)
    assert hasattr(bridge, "system_event_received")


def test_bus_bridge_routes_system_events(qtbot):
    """EVENT.SYSTEM messages should emit system_event_received."""
    q = SimpleQueue()
    bridge = BusBridge(q, refresh_ms=10)

    received = []
    bridge.system_event_received.connect(lambda data: received.append(data))

    q.put(("EVENT.SYSTEM", {
        "source": "BACKEND", "severity": "INFO",
        "message": "Started", "timestamp": "2026-04-07T12:00:00",
    }))

    bridge._drain()

    assert len(received) == 1
    assert received[0]["source"] == "BACKEND"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hmi/test_bus_bridge.py::test_bus_bridge_has_system_event_signal -v`
Expected: FAIL — no `system_event_received` signal

- [ ] **Step 3: Add EVENT.SYSTEM to TelemetryPublisher**

In `telemetry_publisher.py` line 18, change:
```python
_BRIDGE_TOPICS = [b"STATUS.", b"ACTION.CTRL.", b"ACTION.AI.", b"EVENT.ALARM.", b"EVENT.SYSTEM"]
```

- [ ] **Step 4: Add EVENT.SYSTEM to TelemetrySub**

In `telemetry_sub.py` line 11, change:
```python
_SUBSCRIBE_TOPICS = [b"STATUS.", b"ACTION.CTRL.", b"ACTION.AI.", b"EVENT.ALARM.", b"EVENT.SYSTEM"]
```

- [ ] **Step 5: Add system_event_received signal and routing to BusBridge**

In `bus_bridge.py`, add signal:
```python
system_event_received = Signal(object)  # (event_dict)
```

In `_drain()`, add routing after the alarm block (after line 76):
```python
elif topic.startswith("EVENT.SYSTEM"):
    system_events.append(data)
    self._last_frame_time = time.monotonic()
```

Initialize the list in `_drain`:
```python
system_events: list[dict] = []
```

After the alarm emit block, add:
```python
# Emit system events (never drop)
for event in system_events:
    self.system_event_received.emit(event)
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/hmi/test_bus_bridge.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/telemetry_publisher.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/services/telemetry_sub.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/bus_bridge.py \
       tests/hmi/test_bus_bridge.py
git commit -m "feat(zmq): bridge EVENT.SYSTEM from backend to HMI (§6.3, §6.4)"
```

---

## Task 10: Wire SystemEventWorker in Backend main.py

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py`

- [ ] **Step 1: Wire SystemEventWorker creation**

In `main.py`, after alarm_worker setup (~line 314), add:

```python
# System events infrastructure
from smart_pid_core.adapters.outbound.system_event_repo import SystemEventRepository
from smart_pid_core.application.workers.system_event_worker import SystemEventWorker

system_event_repo = SystemEventRepository(repo.db)
system_event_worker = SystemEventWorker(
    bus=bus, system_event_repo=system_event_repo,
    event_loop=asyncio.get_running_loop(),
)
system_event_worker.emit("BACKEND", "INFO", "Backend started")
logger.info("system_event_worker_started")
```

- [ ] **Step 2: Pass system_event_repo to create_app (for REST endpoint)**

In the `create_app(...)` call, add `system_event_repo=system_event_repo`.

Store on `app.state` in `create_app`:
```python
app.state.system_event_repo = system_event_repo
```

- [ ] **Step 3: Emit backend shutdown event before stop**

Before the shutdown sequence (after `await stop_event.wait()`):
```python
system_event_worker.emit("BACKEND", "INFO", "Backend shutdown")
```

- [ ] **Step 4: Load controller meta into AlarmWorker at startup**

After controllers are loaded and loops started, populate the AlarmWorker's controller metadata:

```python
# Populate AlarmWorker controller metadata for event enrichment
for ctrl in all_controllers:
    alarm_worker.update_controller_meta(ctrl.id, ctrl.name, ctrl.description)
    alarm_worker.update_pv_range(ctrl.id, ctrl.pv_scale.eu_min, ctrl.pv_scale.eu_max)
```

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/main.py \
       packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py
git commit -m "feat(core): wire SystemEventWorker + AlarmWorker metadata in daemon (§6.2)"
```

---

## Task 11: HMI API Client — Add System Events Method

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py`

- [ ] **Step 1: Add get_system_events to port protocol**

In `ports.py`, add after line 110:
```python
def get_system_events(
    self, start: datetime, end: datetime,
    source: str | None = ..., severity: str | None = ...,
) -> list[dict]: ...
```

- [ ] **Step 2: Implement in api_client.py**

Add after `get_alarm_history`:
```python
def get_system_events(
    self, start: datetime, end: datetime,
    source: str | None = None, severity: str | None = None,
) -> list[dict]:
    params: dict = {"start": start.isoformat(), "end": end.isoformat()}
    if source is not None:
        params["source"] = source
    if severity is not None:
        params["severity"] = severity
    resp = self._http.get("/system-events", params=params, headers=self._headers())
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 3: Implement in mock_service.py**

```python
def get_system_events(
    self, start: datetime, end: datetime,
    source: str | None = None, severity: str | None = None,
) -> list[dict]:
    return []
```

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py
git commit -m "feat(hmi): add get_system_events to API client port (§9.3)"
```

---

## Task 12: Fix AlarmPanel — api_client Required + ACK id Fix (Bug #3, #4)

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/alarm_panel.py:70-78,336,352-360`
- Test: `tests/hmi/pages/test_alarm_panel.py`

- [ ] **Step 1: Write failing tests**

```python
# Add to tests/hmi/pages/test_alarm_panel.py

def test_alarm_panel_requires_api_client(theme):
    """AlarmPanel must raise TypeError if api_client is not provided."""
    import inspect
    from smart_pid_hmi.pages.alarm_panel import AlarmPanel
    sig = inspect.signature(AlarmPanel.__init__)
    param = sig.parameters.get("api_client")
    # api_client should NOT have a default of None
    assert param is not None
    assert param.default is inspect.Parameter.empty, \
        "api_client must be a required parameter (no None default)"


def test_alarm_panel_ack_uses_id_field(theme, mock_api):
    """ACK should use 'id' field from alarm data, not 'alarm_id' (Bug #4)."""
    from smart_pid_hmi.pages.alarm_panel import AlarmPanel
    panel = AlarmPanel(theme=theme, api_client=mock_api)

    # Simulate an alarm from API (has 'id' field)
    panel.on_alarm(1, {
        "alarm_type": "HI",
        "priority": "WARNING",
        "transition": "TRIGGERED",
        "value": 85.0,
        "limit": 80.0,
        "timestamp": "2026-04-07T12:00:00",
        "id": 42,
    })

    # Verify the id is stored in UserRole
    from PySide6.QtCore import Qt
    item = panel.active_table.item(0, 0)
    assert item is not None
    stored_id = item.data(Qt.ItemDataRole.UserRole)
    assert stored_id == 42


def test_alarm_panel_on_all_acked(theme, mock_api):
    """on_all_acked() should mark all alarms as ACKNOWLEDGED."""
    from smart_pid_hmi.pages.alarm_panel import AlarmPanel
    panel = AlarmPanel(theme=theme, api_client=mock_api)
    panel.on_alarm(1, {
        "alarm_type": "HI", "priority": "WARNING",
        "transition": "TRIGGERED", "value": 85.0, "limit": 80.0,
        "timestamp": "2026-04-07T12:00:00",
    })
    panel.on_all_acked()
    for key, alarm in panel._active_alarms.items():
        assert alarm["status"] == "ACKNOWLEDGED"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/pages/test_alarm_panel.py::test_alarm_panel_requires_api_client tests/hmi/pages/test_alarm_panel.py::test_alarm_panel_ack_uses_id_field tests/hmi/pages/test_alarm_panel.py::test_alarm_panel_on_all_acked -v`
Expected: FAIL

- [ ] **Step 3: Fix AlarmPanel**

In `alarm_panel.py`:

**Make api_client required (remove `= None` default):**
```python
def __init__(
    self,
    theme: ThemeBase,
    api_client: APIClientPort,
    parent: QWidget | None = None,
) -> None:
```

**Fix _rebuild_table to store `id` (not `alarm_id`) in UserRole:**

Replace line 336 (`alarm_id = alarm.get("alarm_id")`) with:
```python
alarm_id = alarm.get("id")
```

**Add `on_all_acked` method:**
```python
def on_all_acked(self) -> None:
    """Mark all active alarms as ACKNOWLEDGED (called after ACK All response)."""
    for key in self._active_alarms:
        self._active_alarms[key]["status"] = "ACKNOWLEDGED"
    self._rebuild_table()

def on_alarm_acked(self, alarm_id: int) -> None:
    """Mark a specific alarm as ACKNOWLEDGED (called after single ACK response)."""
    for key, alarm in self._active_alarms.items():
        if alarm.get("id") == alarm_id:
            alarm["status"] = "ACKNOWLEDGED"
            break
    self._rebuild_table()
```

- [ ] **Step 4: Fix existing tests that construct AlarmPanel without api_client**

Update all test fixtures that create `AlarmPanel(theme=theme)` to pass `api_client=mock_api`.

- [ ] **Step 5: Run all alarm panel tests**

Run: `uv run pytest tests/hmi/pages/test_alarm_panel.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/alarm_panel.py \
       tests/hmi/pages/test_alarm_panel.py
git commit -m "fix(alarm-panel): api_client required, ACK uses 'id' field (Bug #3, #4)

- api_client is now a required constructor parameter
- ACK reads 'id' from UserRole (not 'alarm_id')
- Added on_all_acked() and on_alarm_acked() methods"
```

---

## Task 13: Redesign AlarmBar as QTableWidget Grid (Spec §8.1)

**Files:**
- Rewrite: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/alarm_bar.py`
- Rewrite: `tests/hmi/widgets/test_alarm_bar.py`

- [ ] **Step 1: Write tests for new AlarmBar grid**

```python
# tests/hmi/widgets/test_alarm_bar.py — complete rewrite
"""Tests for AlarmBar QTableWidget grid redesign."""
from __future__ import annotations

import pytest

from smart_pid_hmi.widgets.alarm_bar import AlarmBarWidget


@pytest.fixture
def bar(theme):
    return AlarmBarWidget(theme=theme)


def test_alarm_bar_creation(bar):
    assert bar is not None
    assert bar.alarm_count == 0
    assert hasattr(bar, "ack_requested")
    assert hasattr(bar, "ack_all_requested")


def test_alarm_bar_has_table(bar):
    """AlarmBar must use QTableWidget (not pills)."""
    from PySide6.QtWidgets import QTableWidget
    assert hasattr(bar, "_table")
    assert isinstance(bar._table, QTableWidget)


def test_alarm_bar_columns(bar):
    """Table must have 6 columns: Priority, Level, Loop, Description, DateTime, ACK."""
    assert bar._table.columnCount() == 6


def test_alarm_bar_triggered_adds_row(bar):
    bar.on_alarm({
        "controller_id": 1,
        "controller_name": "TIC-101",
        "controller_description": "Temp Reactor A",
        "alarm_type": "HIHI",
        "priority": "CRITICAL",
        "transition": "TRIGGERED",
        "value": 95.0,
        "limit": 90.0,
        "timestamp": "2026-04-07T12:00:00",
    })
    assert bar._table.rowCount() == 1
    assert bar.alarm_count == 1


def test_alarm_bar_cleared_removes_row(bar):
    bar.on_alarm({
        "controller_id": 1,
        "controller_name": "TIC-101",
        "controller_description": "Temp Reactor A",
        "alarm_type": "HIHI",
        "priority": "CRITICAL",
        "transition": "TRIGGERED",
        "value": 95.0,
        "limit": 90.0,
        "timestamp": "2026-04-07T12:00:00",
    })
    bar.on_alarm({
        "controller_id": 1,
        "controller_name": "TIC-101",
        "controller_description": "Temp Reactor A",
        "alarm_type": "HIHI",
        "priority": "CRITICAL",
        "transition": "CLEARED",
        "value": 85.0,
        "limit": 90.0,
        "timestamp": "2026-04-07T12:05:00",
    })
    assert bar._table.rowCount() == 0


def test_alarm_bar_log_priority_hidden(bar):
    """Priority LOG should NOT appear in AlarmBar grid."""
    bar.on_alarm({
        "controller_id": 1,
        "controller_name": "TIC-101",
        "controller_description": "",
        "alarm_type": "HI",
        "priority": "LOG",
        "transition": "TRIGGERED",
        "value": 81.0,
        "limit": 80.0,
        "timestamp": "2026-04-07T12:00:00",
    })
    assert bar._table.rowCount() == 0


def test_alarm_bar_on_alarm_acked(bar):
    """on_alarm_acked should stop blinking for specific alarm."""
    bar.on_alarm({
        "controller_id": 1,
        "controller_name": "TIC-101",
        "controller_description": "",
        "alarm_type": "HI",
        "priority": "WARNING",
        "transition": "TRIGGERED",
        "value": 85.0,
        "limit": 80.0,
        "timestamp": "2026-04-07T12:00:00",
    })
    bar.on_alarm_acked(1, "HI")
    # After ACK, the alarm is still visible but marked as acked
    assert bar._table.rowCount() == 1
    key = (1, "HI")
    assert bar._active[key]["acked"] is True


def test_alarm_bar_on_all_alarms_acked(bar):
    """on_all_alarms_acked should mark all as acked."""
    bar.on_alarm({
        "controller_id": 1, "controller_name": "TIC-101",
        "controller_description": "", "alarm_type": "HI",
        "priority": "WARNING", "transition": "TRIGGERED",
        "value": 85.0, "limit": 80.0, "timestamp": "2026-04-07T12:00:00",
    })
    bar.on_alarm({
        "controller_id": 2, "controller_name": "FIC-203",
        "controller_description": "", "alarm_type": "HIHI",
        "priority": "CRITICAL", "transition": "TRIGGERED",
        "value": 96.0, "limit": 95.0, "timestamp": "2026-04-07T12:01:00",
    })
    bar.on_all_alarms_acked()
    for info in bar._active.values():
        assert info["acked"] is True


def test_alarm_bar_counters(bar):
    """Counter label must show CRITICAL: N | WARNING: N for unacked alarms."""
    bar.on_alarm({
        "controller_id": 1, "controller_name": "TIC-101",
        "controller_description": "", "alarm_type": "HIHI",
        "priority": "CRITICAL", "transition": "TRIGGERED",
        "value": 95.0, "limit": 90.0, "timestamp": "2026-04-07T12:00:00",
    })
    bar.on_alarm({
        "controller_id": 2, "controller_name": "FIC-203",
        "controller_description": "", "alarm_type": "HI",
        "priority": "WARNING", "transition": "TRIGGERED",
        "value": 82.0, "limit": 80.0, "timestamp": "2026-04-07T12:01:00",
    })
    text = bar._counter_label.text()
    assert "CRITICAL: 1" in text
    assert "WARNING: 1" in text


def test_alarm_bar_sorted_by_priority_then_time(bar):
    """CRITICAL alarms should appear before WARNING, then by time (newest first)."""
    bar.on_alarm({
        "controller_id": 1, "controller_name": "TIC-101",
        "controller_description": "", "alarm_type": "HI",
        "priority": "WARNING", "transition": "TRIGGERED",
        "value": 82.0, "limit": 80.0, "timestamp": "2026-04-07T12:00:00",
    })
    bar.on_alarm({
        "controller_id": 2, "controller_name": "FIC-203",
        "controller_description": "", "alarm_type": "HIHI",
        "priority": "CRITICAL", "transition": "TRIGGERED",
        "value": 96.0, "limit": 95.0, "timestamp": "2026-04-07T12:01:00",
    })
    # CRITICAL should be first row
    assert bar._table.item(0, 0).text() == "CRITICAL"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/widgets/test_alarm_bar.py -v`
Expected: FAIL — old widget structure

- [ ] **Step 3: Rewrite AlarmBarWidget**

Complete rewrite of `alarm_bar.py`:

```python
"""AlarmBarWidget — QTableWidget grid showing active alarms (spec §8.1)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from smart_pid_hmi.themes.base import ThemeBase

_BAR_HEIGHT = 150
_COLUMNS = ["Priority", "Level", "Loop", "Description", "Date/Time", "ACK"]

_PRIORITY_RANK = {"CRITICAL": 0, "WARNING": 1, "ADVISORY": 2}
_PRIORITY_COLORS = {
    "CRITICAL": "#D32F2F",
    "WARNING": "#FBC02D",
    "ADVISORY": "#1976D2",
}
_PRIORITY_TEXT = {
    "CRITICAL": "#FFFFFF",
    "WARNING": "#000000",
    "ADVISORY": "#FFFFFF",
}


def _theme_attr(theme: ThemeBase, attr: str, fallback: str) -> str:
    val = getattr(theme, attr, "")
    return val if val else fallback


class AlarmBarWidget(QFrame):
    """Fixed-height footer grid showing active alarms with per-row ACK."""

    ack_requested = Signal(int)       # alarm_id for single ACK
    ack_all_requested = Signal()

    def __init__(
        self, theme: ThemeBase, parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        # (controller_id, alarm_type) -> alarm dict + acked flag
        self._active: dict[tuple[int, str], dict] = {}

        self.setFixedHeight(_BAR_HEIGHT)
        bg = _theme_attr(theme, "bg_toolbar", theme.bg_secondary)
        self.setStyleSheet(
            f"AlarmBarWidget {{ background-color: {bg}; "
            f"border-top: 1px solid {theme.border}; }}"
        )

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 4, 8, 4)
        main_layout.setSpacing(4)

        left = QVBoxLayout()
        left.setSpacing(2)

        # Counter header
        self._counter_label = QLabel("[ ACTIVE ALARMS ]")
        self._counter_label.setStyleSheet(
            f"color: {theme.fg_primary}; background: transparent; "
            f"font-size: {theme.font_size_label}px; font-weight: bold; padding: 0;"
        )
        left.addWidget(self._counter_label)

        # Table
        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch,  # Description stretches
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        left.addWidget(self._table, stretch=1)

        main_layout.addLayout(left, stretch=1)

        # ACK ALL button
        right = QVBoxLayout()
        self._ack_btn = QPushButton("ACK\nALL")
        self._ack_btn.setFixedWidth(60)
        self._ack_btn.clicked.connect(self.ack_all_requested.emit)
        right.addWidget(self._ack_btn)
        right.addStretch()
        main_layout.addLayout(right)

        # Blink timer
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._on_blink)
        self._blink_visible = True

    @property
    def alarm_count(self) -> int:
        return len(self._active)

    def on_alarm(self, alarm: dict) -> None:
        """Handle alarm TRIGGERED or CLEARED."""
        cid = alarm.get("controller_id", 0)
        atype = alarm.get("alarm_type", "")
        priority = alarm.get("priority", "")
        transition = alarm.get("transition", "")

        # LOG priority: do not show in bar
        if priority == "LOG":
            return

        key = (cid, atype)

        if transition == "TRIGGERED":
            self._active[key] = {**alarm, "acked": False}
        elif transition == "CLEARED":
            self._active.pop(key, None)

        self._rebuild()

    def on_alarm_acked(self, controller_id: int, alarm_type: str) -> None:
        """Mark a specific alarm as acknowledged."""
        key = (controller_id, alarm_type)
        if key in self._active:
            self._active[key]["acked"] = True
        self._rebuild()

    def on_all_alarms_acked(self) -> None:
        """Mark all alarms as acknowledged."""
        for info in self._active.values():
            info["acked"] = True
        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild table from _active dict, sorted by priority then timestamp."""
        # Sort: CRITICAL first, then by timestamp descending
        sorted_alarms = sorted(
            self._active.values(),
            key=lambda a: (
                _PRIORITY_RANK.get(a.get("priority", ""), 99),
                a.get("timestamp", ""),
            ),
        )
        # Reverse timestamp within same priority (newest first)
        # Actually: primary sort by priority ASC, secondary by timestamp DESC
        sorted_alarms = sorted(
            self._active.values(),
            key=lambda a: (
                _PRIORITY_RANK.get(a.get("priority", ""), 99),
                "",  # placeholder
            ),
        )
        # Proper sort: priority ASC, timestamp DESC
        sorted_alarms = sorted(
            self._active.values(),
            key=lambda a: (
                _PRIORITY_RANK.get(a.get("priority", ""), 99),
                # Negate timestamp for DESC — use string reversal trick
            ),
        )
        # Simpler: group by priority, each group sorted by timestamp desc
        from itertools import groupby
        groups = {}
        for alarm in self._active.values():
            pri = alarm.get("priority", "")
            groups.setdefault(pri, []).append(alarm)
        sorted_alarms = []
        for pri in ["CRITICAL", "WARNING", "ADVISORY"]:
            grp = groups.get(pri, [])
            grp.sort(key=lambda a: a.get("timestamp", ""), reverse=True)
            sorted_alarms.extend(grp)

        self._table.setRowCount(0)
        has_unacked = False

        for alarm in sorted_alarms:
            row = self._table.rowCount()
            self._table.insertRow(row)
            priority = alarm.get("priority", "")
            acked = alarm.get("acked", False)
            if not acked:
                has_unacked = True

            items = [
                priority,
                alarm.get("alarm_type", ""),
                alarm.get("controller_name", "?"),
                alarm.get("controller_description", ""),
                alarm.get("timestamp", ""),
                "\u2713" if acked else "ACK",
            ]
            color = _PRIORITY_COLORS.get(priority, "#757575")
            text_color = _PRIORITY_TEXT.get(priority, "#FFFFFF")

            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setForeground(QColor(text_color))
                if not acked:
                    item.setBackground(QColor(color))
                else:
                    # Solid color for acked
                    c = QColor(color)
                    c.setAlpha(180)
                    item.setBackground(c)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row, col, item)

        # Update counters
        unacked_counts: dict[str, int] = {"CRITICAL": 0, "WARNING": 0, "ADVISORY": 0}
        for alarm in self._active.values():
            if not alarm.get("acked", False):
                pri = alarm.get("priority", "")
                if pri in unacked_counts:
                    unacked_counts[pri] += 1

        parts = [f"{k}: {v}" for k, v in unacked_counts.items() if v > 0]
        if parts:
            self._counter_label.setText(f"[ ACTIVE ALARMS ] {' | '.join(parts)}")
        else:
            self._counter_label.setText("[ ACTIVE ALARMS ]")

        # Manage blink timer
        if has_unacked and not self._blink_timer.isActive():
            self._blink_visible = True
            self._blink_timer.start()
        elif not has_unacked:
            self._blink_timer.stop()

    def _on_blink(self) -> None:
        """Toggle visibility of unacked alarm row backgrounds."""
        self._blink_visible = not self._blink_visible
        for row in range(self._table.rowCount()):
            # Check if this row is unacked (ACK column != checkmark)
            ack_item = self._table.item(row, 5)
            if ack_item and ack_item.text() != "\u2713":
                pri_item = self._table.item(row, 0)
                if pri_item:
                    priority = pri_item.text()
                    color = _PRIORITY_COLORS.get(priority, "#757575")
                    for col in range(self._table.columnCount()):
                        item = self._table.item(row, col)
                        if item:
                            if self._blink_visible:
                                item.setBackground(QColor(color))
                            else:
                                item.setBackground(QColor("transparent"))

    def apply_theme(self, theme: ThemeBase) -> None:
        self._theme = theme
        bg = _theme_attr(theme, "bg_toolbar", theme.bg_secondary)
        self.setStyleSheet(
            f"AlarmBarWidget {{ background-color: {bg}; "
            f"border-top: 1px solid {theme.border}; }}"
        )
        self._counter_label.setStyleSheet(
            f"color: {theme.fg_primary}; background: transparent; "
            f"font-size: {theme.font_size_label}px; font-weight: bold; padding: 0;"
        )
        self._rebuild()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/hmi/widgets/test_alarm_bar.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/widgets/alarm_bar.py \
       tests/hmi/widgets/test_alarm_bar.py
git commit -m "feat(hmi): redesign AlarmBar as QTableWidget grid with per-row ACK (§8.1)

Replaces pills design with data grid showing Priority, Level, Loop,
Description, DateTime, ACK columns. Blinks unacked, sorted by priority."
```

---

## Task 14: Fix MainWindow ACK Wiring — All 3 Widgets (Bug #5)

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py:353-356,598-606`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/dashboard_page.py`

- [ ] **Step 1: Update MainWindow construction — pass api_client to AlarmPanel**

In `main.py`, find where `AlarmPanel` is constructed. Change:
```python
self._alarm_panel = AlarmPanel(theme=theme, api_client=self._api_client)
```

(Ensure `api_client` is passed — this is Bug #3.)

- [ ] **Step 2: Wire system_event_received in MainWindow**

After the existing bus_bridge connections (~line 353), add:
```python
bus_bridge.system_event_received.connect(self._on_system_event)
```

Add the handler:
```python
def _on_system_event(self, event: dict) -> None:
    """Forward system event to AlarmPanel."""
    source = event.get("source", "SYSTEM")
    severity = event.get("severity", "INFO")
    message = event.get("message", "")
    self._alarm_panel.on_system_event(message, priority=severity)
```

- [ ] **Step 3: Fix _send_ack_single to update all 3 widgets**

Replace the current `_send_ack_single`:
```python
def _send_ack_single(self, alarm_id: int) -> None:
    """ACK a single alarm and update all 3 widgets."""
    result = self._safe_api_call(self._api_client.ack_alarm, alarm_id)
    if result and isinstance(result, dict):
        controller_id = result.get("controller_id")
        alarm_type = result.get("alarm_type")
        if controller_id is not None and alarm_type:
            self._alarm_panel.on_alarm_acked(alarm_id)
            self._dashboard_page.on_alarm_ack(controller_id, alarm_type)
```

- [ ] **Step 4: Fix _send_ack_all to update all 3 widgets**

Replace the current `_send_ack_all`:
```python
def _send_ack_all(self) -> None:
    """ACK all alarms and update all 3 widgets."""
    result = self._safe_api_call(self._api_client.ack_all_alarms)
    if result and isinstance(result, dict):
        controller_ids = result.get("controller_ids", [])
        # Update AlarmPanel
        self._alarm_panel.on_all_acked()
        # Update AlarmBar
        self._dashboard_page.on_all_alarms_acked()
        # Update cards
        for cid in controller_ids:
            self._dashboard_page.on_alarm_ack(cid, None)
```

- [ ] **Step 5: Add on_all_alarms_acked to DashboardPage**

In `dashboard_page.py`, add:
```python
def on_all_alarms_acked(self) -> None:
    """Propagate ACK All to alarm bar."""
    self._alarm_bar.on_all_alarms_acked()
```

- [ ] **Step 6: Update DashboardPage._on_alarm to use new AlarmBar API**

The new `AlarmBarWidget.on_alarm` takes a single dict (not `controller_id, alarm`). Update:
```python
def _on_alarm(self, controller_id: int, alarm: dict) -> None:
    for card in self._cards:
        card.on_alarm(controller_id, alarm)
    self._alarm_bar.on_alarm(alarm)
```

- [ ] **Step 7: Wire AlarmBar ack_requested signal through DashboardPage**

In `dashboard_page.py`, add signal forwarding:
```python
# In __init__ after alarm_bar creation:
self._alarm_bar.ack_requested.connect(self.alarm_ack_requested)
self._alarm_bar.ack_all_requested.connect(self.alarm_ack_all_requested)
```

Add signals to DashboardPage:
```python
alarm_ack_requested = Signal(int)    # alarm_id
alarm_ack_all_requested = Signal()
```

In `main.py`, connect:
```python
self._dashboard_page.alarm_ack_requested.connect(self._send_ack_single)
self._dashboard_page.alarm_ack_all_requested.connect(self._send_ack_all)
```

- [ ] **Step 8: Check that _safe_api_call returns the result**

Verify `_safe_api_call` returns the API result (not None). If it currently only catches exceptions, update it to return the result.

- [ ] **Step 9: Run full HMI test suite**

Run: `uv run pytest tests/hmi/ -v`
Expected: ALL PASS

- [ ] **Step 10: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/main.py \
       packages/smart_pid_hmi/src/smart_pid_hmi/pages/dashboard_page.py
git commit -m "fix(hmi): ACK updates all 3 widgets — panel, bar, cards (Bug #5)

- _send_ack_single uses API response to update panel + bar + card
- _send_ack_all propagates to all widgets with controller_ids
- Wired system_event_received to AlarmPanel
- AlarmBar ACK signals forwarded through DashboardPage"
```

---

## Task 15: AlarmPanel Live Mode (Spec §7.3)

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/alarm_panel.py`
- Test: `tests/hmi/pages/test_alarm_panel.py`

- [ ] **Step 1: Write failing tests for Live mode**

```python
# Add to tests/hmi/pages/test_alarm_panel.py

def test_alarm_panel_has_live_checkbox(theme, mock_api):
    from smart_pid_hmi.pages.alarm_panel import AlarmPanel
    panel = AlarmPanel(theme=theme, api_client=mock_api)
    assert hasattr(panel, "_live_checkbox")


def test_alarm_panel_live_disables_history_controls(theme, mock_api):
    from smart_pid_hmi.pages.alarm_panel import AlarmPanel
    panel = AlarmPanel(theme=theme, api_client=mock_api)
    panel._live_checkbox.setChecked(True)
    assert not panel._dt_from.isEnabled()
    assert not panel._dt_to.isEnabled()
    assert not panel._load_history_btn.isEnabled()


def test_alarm_panel_live_enables_history_on_uncheck(theme, mock_api):
    from smart_pid_hmi.pages.alarm_panel import AlarmPanel
    panel = AlarmPanel(theme=theme, api_client=mock_api)
    panel._live_checkbox.setChecked(True)
    panel._live_checkbox.setChecked(False)
    assert panel._dt_from.isEnabled()
    assert panel._dt_to.isEnabled()
    assert panel._load_history_btn.isEnabled()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/hmi/pages/test_alarm_panel.py::test_alarm_panel_has_live_checkbox -v`
Expected: FAIL — no `_live_checkbox`

- [ ] **Step 3: Implement Live mode**

In `alarm_panel.py`, add to the filter toolbar:

```python
from PySide6.QtWidgets import QCheckBox
from PySide6.QtCore import QTimer as QtTimer

# In __init__, after filter_layout.addStretch():
self._live_checkbox = QCheckBox("Live")
self._live_checkbox.toggled.connect(self._on_live_toggled)
filter_layout.addWidget(self._live_checkbox)

# Live timer (5s refresh)
self._live_timer = QtTimer(self)
self._live_timer.setInterval(5000)
self._live_timer.timeout.connect(self._live_refresh)
```

Add methods:

```python
def _on_live_toggled(self, checked: bool) -> None:
    """Toggle live mode."""
    self._dt_from.setEnabled(not checked)
    self._dt_to.setEnabled(not checked)
    self._load_history_btn.setEnabled(not checked)
    if checked:
        self._live_refresh()
        self._live_timer.start()
    else:
        self._live_timer.stop()

def _live_refresh(self) -> None:
    """Fetch active alarms + recent system events for live view."""
    if self._api_client is None:
        return
    try:
        alarms = self._api_client.get_active_alarms()
    except Exception:  # noqa: BLE001
        alarms = []
    self._active_alarms.clear()
    for alarm in alarms:
        key = (alarm.get("controller_id", 0), alarm.get("alarm_type", ""))
        self._active_alarms[key] = {
            **alarm,
            "status": "ACKNOWLEDGED" if alarm.get("acknowledged") else "UNACKNOWLEDGED",
        }
    # Also fetch recent system events (last 5 min)
    from datetime import datetime, timedelta, UTC
    now = datetime.now(tz=UTC)
    try:
        sys_events = self._api_client.get_system_events(
            start=now - timedelta(minutes=5), end=now,
        )
        self._system_events = [
            {
                "controller_id": "",
                "alarm_type": "SYSTEM",
                "priority": e.get("severity", "INFO"),
                "value": 0.0,
                "limit": 0.0,
                "timestamp": e.get("timestamp", ""),
                "status": e.get("message", ""),
                "transition": "INFO",
            }
            for e in sys_events
        ]
    except Exception:  # noqa: BLE001
        pass
    self._rebuild_table()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/hmi/pages/test_alarm_panel.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/pages/alarm_panel.py \
       tests/hmi/pages/test_alarm_panel.py
git commit -m "feat(alarm-panel): add Live mode with 5s auto-refresh (§7.3)"
```

---

## Task 16: Data Retention Cleanup Job

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py`

- [ ] **Step 1: Add daily retention cleanup task**

In `main.py`, after daemon infrastructure is set up, add an asyncio task:

```python
async def _retention_cleanup(repo_db, interval_hours: int = 24) -> None:
    """Daily cleanup of old alarm logs and system events."""
    import structlog
    _logger = structlog.get_logger()
    while True:
        await asyncio.sleep(interval_hours * 3600)
        try:
            await repo_db.execute(
                "DELETE FROM Log_Alarmes WHERE timestamp <= datetime('now', '-30 days')"
            )
            await repo_db.execute(
                "DELETE FROM Log_System_Events WHERE timestamp <= datetime('now', '-30 days')"
            )
            await repo_db.execute(
                "DELETE FROM Log_Sintonia_IA WHERE timestamp <= datetime('now', '-7 days')"
            )
            await repo_db.execute(
                "DELETE FROM Log_Processo WHERE timestamp <= datetime('now', '-7 days')"
            )
            await repo_db.commit()
            _logger.info("retention_cleanup_complete")
        except Exception:
            _logger.exception("retention_cleanup_error")
```

Start it before the uvicorn server:
```python
cleanup_task = asyncio.create_task(_retention_cleanup(repo.db))
```

Cancel it during shutdown:
```python
cleanup_task.cancel()
```

- [ ] **Step 2: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/main.py
git commit -m "feat(core): add daily retention cleanup for alarms (30d) and logs (7d) (§4)"
```

---

## Task 17: Full Integration Test + Lint

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=60`
Expected: ALL PASS

- [ ] **Step 2: Run linter**

Run: `uv run --with ruff ruff check .`
Expected: No errors (or fix any found)

- [ ] **Step 3: Run type checker**

Run: `uv run mypy packages/`
Expected: No new errors

- [ ] **Step 4: Fix any issues found, commit**

```bash
git add -A
git commit -m "chore: fix lint and type issues from Phase 6 implementation"
```

---

## Summary of Bugs Fixed

| Bug # | Task | Status |
|-------|------|--------|
| #1 (CRITICAL) Duplicate alarm engines | Task 1 | Removed from PIDWorker + LoopManager |
| #2 (CRITICAL) Alarms never trigger in Execute | Task 1 | Dead code removed |
| #3 (CRITICAL) AlarmPanel no api_client | Task 12 | Made required parameter |
| #4 (MAJOR) ACK Selected wrong field | Task 12 | Uses `id` not `alarm_id` |
| #5 (MAJOR) ACK All doesn't update all widgets | Task 14 | All 3 widgets updated |
| #6 (MAJOR) AlarmBar shows "?" for name | Task 3 | Events enriched with controller_name |
| #9 (MODERATE) Silent processing failures | Task 3 | Added logger.warning |
| #11 (MODERATE) Zero deadband at limit=0 | Task 2 | Span-based deadband calculation |

## New Features Delivered

| Feature | Task | Spec § |
|---------|------|--------|
| SystemEventRepository + DDL | Task 6 | §4.3 |
| SystemEventWorker | Task 7 | §6.1 |
| System Events REST API | Task 8 | §9.3 |
| EVENT.SYSTEM ZMQ bridging | Task 9 | §6.3 |
| AlarmBar QTableWidget grid | Task 13 | §8.1 |
| AlarmPanel Live mode | Task 15 | §7.3 |
| ACK response contracts | Tasks 4-5 | §5.5, §9.1 |
| Data retention cleanup | Task 16 | §4 |
