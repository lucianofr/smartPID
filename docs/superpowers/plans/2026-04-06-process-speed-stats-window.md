# Process Speed Stats Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote ProcessSpeed to a mandatory Controller-level field with 4 categories that define performance statistics windows and AI speed factors.

**Architecture:** Expand the ProcessSpeed StrEnum with embedded metadata properties (stats_window_s, speed_factor, label). Move the field from AIConfig to Controller root. StatsWorker computes window_size dynamically from process_speed + scan_rate.

**Tech Stack:** Python 3.13, pydantic v2, PySide6, aiosqlite, pytest

---

### Task 1: Expand ProcessSpeed Enum with Properties

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/enums.py:41-44`
- Test: `tests/domain/test_models.py`

- [ ] **Step 1: Update the failing test**

In `tests/domain/test_models.py`, update the existing `test_process_speed_values` test and add property tests:

```python
def test_process_speed_values(self) -> None:
    assert len(ProcessSpeed) == 4
    assert ProcessSpeed.ULTRA_FAST == "ULTRA_FAST"
    assert ProcessSpeed.FAST == "FAST"
    assert ProcessSpeed.MEDIUM == "MEDIUM"
    assert ProcessSpeed.SLOW == "SLOW"

def test_process_speed_stats_window(self) -> None:
    assert ProcessSpeed.ULTRA_FAST.stats_window_s == 5
    assert ProcessSpeed.FAST.stats_window_s == 60
    assert ProcessSpeed.MEDIUM.stats_window_s == 1200
    assert ProcessSpeed.SLOW.stats_window_s == 7200

def test_process_speed_speed_factor(self) -> None:
    assert ProcessSpeed.ULTRA_FAST.speed_factor == 0.02
    assert ProcessSpeed.FAST.speed_factor == 0.05
    assert ProcessSpeed.MEDIUM.speed_factor == 0.15
    assert ProcessSpeed.SLOW.speed_factor == 0.30

def test_process_speed_label(self) -> None:
    assert "Motors" in ProcessSpeed.ULTRA_FAST.label
    assert "Flow" in ProcessSpeed.FAST.label
    assert "Level" in ProcessSpeed.MEDIUM.label
    assert "Furnaces" in ProcessSpeed.SLOW.label
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_models.py::TestEnums::test_process_speed_values -v`
Expected: FAIL — `assert len(ProcessSpeed) == 4` fails (currently 3)

- [ ] **Step 3: Implement expanded ProcessSpeed enum**

Replace the `ProcessSpeed` class in `packages/smart_pid_domain/src/smart_pid_domain/enums.py:41-44` with:

```python
class ProcessSpeed(StrEnum):
    """Process dynamics speed — determines stats window and AI speed factor."""
    ULTRA_FAST = "ULTRA_FAST"
    FAST = "FAST"
    MEDIUM = "MEDIUM"
    SLOW = "SLOW"

    @property
    def stats_window_s(self) -> int:
        """Default statistics sliding window in seconds."""
        return _STATS_WINDOWS[self]

    @property
    def speed_factor(self) -> float:
        """AI tuning aggressiveness factor (Sv)."""
        return _SPEED_FACTORS[self]

    @property
    def label(self) -> str:
        """Human-readable label with process examples for UI."""
        return _LABELS[self]


_STATS_WINDOWS: dict[ProcessSpeed, int] = {
    ProcessSpeed.ULTRA_FAST: 5,
    ProcessSpeed.FAST: 60,
    ProcessSpeed.MEDIUM: 1200,
    ProcessSpeed.SLOW: 7200,
}

_SPEED_FACTORS: dict[ProcessSpeed, float] = {
    ProcessSpeed.ULTRA_FAST: 0.02,
    ProcessSpeed.FAST: 0.05,
    ProcessSpeed.MEDIUM: 0.15,
    ProcessSpeed.SLOW: 0.30,
}

_LABELS: dict[ProcessSpeed, str] = {
    ProcessSpeed.ULTRA_FAST: "Ultra Fast \u2014 Motors / Converters",
    ProcessSpeed.FAST: "Fast \u2014 Flow / Pressure",
    ProcessSpeed.MEDIUM: "Medium \u2014 Level / Heat Exchangers",
    ProcessSpeed.SLOW: "Slow \u2014 Furnaces / Distillation",
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_models.py -v -k "process_speed"`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/enums.py tests/domain/test_models.py
git commit -m "feat(domain): expand ProcessSpeed to 4 categories with metadata properties"
```

---

### Task 2: Move process_speed from AIConfig to Controller

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py:48-56` (AIConfig) and `:114-166` (Controller)
- Test: `tests/domain/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/domain/test_models.py`:

```python
def test_controller_has_process_speed(self) -> None:
    """process_speed is a direct field on Controller, not inside AIConfig."""
    c = Controller()
    assert c.process_speed == ProcessSpeed.MEDIUM
    assert not hasattr(c.ai_config, "process_speed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_models.py::TestController::test_controller_has_process_speed -v`
Expected: FAIL — `assert not hasattr(c.ai_config, "process_speed")` fails

- [ ] **Step 3: Move the field**

In `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py`:

Remove `process_speed` from `AIConfig` (line 53):

```python
@dataclass
class AIConfig:
    """AI optimization configuration."""

    engine: AIEngine = AIEngine.NONE
    objective: ControlObjective = ControlObjective.DISTURBANCE_REJECTION
    dead_time_l: float = 1.0      # Estimated dead time (seconds)
    limit_min: float = 0.1        # Ki/Ti minimum clamp
    limit_max: float = 100.0      # Ki/Ti maximum clamp
```

Add `process_speed` to `Controller` after `scan_rate_ms` (line ~122):

```python
    scan_rate_ms: int = 1000
    process_speed: ProcessSpeed = ProcessSpeed.MEDIUM
```

- [ ] **Step 4: Run tests to verify the new test passes**

Run: `uv run pytest tests/domain/test_models.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/models/controller.py tests/domain/test_models.py
git commit -m "refactor(domain): move process_speed from AIConfig to Controller"
```

---

### Task 3: Update DTOs

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py`
- Test: `tests/domain/test_controller_dtos.py`

- [ ] **Step 1: Update the failing test**

In `tests/domain/test_controller_dtos.py`, update the test that checks `AIConfigDTO` and add a test for root-level `process_speed`:

Find the test that asserts `a.process_speed == "MEDIUM"` (line ~57) and update it to verify `process_speed` is NOT in `AIConfigDTO` and IS in `ControllerCreate`:

```python
def test_ai_config_dto_no_process_speed(self) -> None:
    a = AIConfigDTO()
    assert not hasattr(a, "process_speed") or "process_speed" not in a.model_fields

def test_controller_create_has_process_speed(self) -> None:
    c = ControllerCreate(name="TEST")
    assert c.process_speed == "MEDIUM"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/test_controller_dtos.py -v -k "process_speed"`
Expected: FAIL — `AIConfigDTO` still has `process_speed`

- [ ] **Step 3: Update DTOs**

In `packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py`:

Remove `process_speed` from `AIConfigDTO` (line 32):

```python
class AIConfigDTO(BaseModel):
    """AI optimization config (mirrors domain AIConfig)."""

    engine: str = "NONE"
    objective: str = "DISTURBANCE_REJECTION"
    dead_time_l: float = 1.0
    limit_min: float = 0.1
    limit_max: float = 100.0
```

Add `process_speed` to `ControllerCreate` after `scan_rate_ms` (line ~89):

```python
    scan_rate_ms: int = 1000
    process_speed: str = "MEDIUM"
```

Add `process_speed` to `ControllerUpdate` after `scan_rate_ms` (line ~144):

```python
    scan_rate_ms: int | None = None
    process_speed: str | None = None
```

Add `process_speed` to `ControllerResponse` after `scan_rate_ms` (line ~197):

```python
    scan_rate_ms: int = 1000
    process_speed: str = "MEDIUM"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_controller_dtos.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/controllers.py tests/domain/test_controller_dtos.py
git commit -m "refactor(dto): move process_speed from AIConfigDTO to controller root"
```

---

### Task 4: Update API Router Mappings

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py`
- Test: `tests/core/integration/test_api_controllers.py`

- [ ] **Step 1: Update the failing test**

In `tests/core/integration/test_api_controllers.py`, update the test that sends `process_speed` inside `ai_config` (line ~172) to send it at root level, and update the assertion (line ~222):

Find `"process_speed": "SLOW"` inside an `ai_config` dict and move it to the root of the request body. Change:

```python
"ai_config": {
    ...
    "process_speed": "SLOW",
    ...
}
```

to:

```python
"process_speed": "SLOW",
"ai_config": {
    ...
}
```

And update the response assertion from:

```python
assert data["ai_config"]["process_speed"] == "SLOW"
```

to:

```python
assert data["process_speed"] == "SLOW"
```

Similarly for the update test (line ~270), move `"process_speed": "FAST"` from inside `ai_config` to root level.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/core/integration/test_api_controllers.py -v`
Expected: FAIL — router still reads from `ai_config`

- [ ] **Step 3: Update router mappings**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py`:

**`_to_response` function (line ~63):** Add `process_speed` at root and remove from `ai_config`:

```python
        process_speed=str(c.process_speed),
```

Add this after `scan_rate_ms=c.scan_rate_ms,` (line ~74). And change the `ai_config` block (line ~126-133) to remove `process_speed`:

```python
        ai_config=AIConfigDTO(
            engine=str(c.ai_config.engine),
            objective=str(c.ai_config.objective),
            dead_time_l=c.ai_config.dead_time_l,
            limit_min=c.ai_config.limit_min,
            limit_max=c.ai_config.limit_max,
        ),
```

**`_body_to_controller` function (line ~155):** Add `process_speed` at root and remove from `AIConfig`:

```python
        process_speed=ProcessSpeed(body.process_speed),
```

Add this after `scan_rate_ms=body.scan_rate_ms,` (line ~162). And change the `ai_config` block (line ~214-221):

```python
        ai_config=AIConfig(
            engine=AIEngine(body.ai_config.engine),
            objective=ControlObjective(body.ai_config.objective),
            dead_time_l=body.ai_config.dead_time_l,
            limit_min=body.ai_config.limit_min,
            limit_max=body.ai_config.limit_max,
        ),
```

**`_NESTED_BUILDERS` dict (line ~275-279):** Update the `ai_config` builder to not include `process_speed`:

```python
    "ai_config": (AIConfigDTO, lambda dto: AIConfig(
        engine=AIEngine(dto.engine), objective=ControlObjective(dto.objective),
        dead_time_l=dto.dead_time_l,
        limit_min=dto.limit_min, limit_max=dto.limit_max,
    )),
```

**`_ENUM_FIELDS` dict (line ~283-290):** Add `process_speed`:

```python
_ENUM_FIELDS: dict[str, type] = {
    "execution_mode": ExecutionMode,
    "pid_structure": PIDStructure,
    "integral_type": IntegralType,
    "tuning_write_mode": TuningWriteMode,
    "mode_normal": ControllerMode,
    "shed_opt": ControllerMode,
    "process_speed": ProcessSpeed,
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_api_controllers.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py tests/core/integration/test_api_controllers.py
git commit -m "refactor(api): move process_speed to controller root in router"
```

---

### Task 5: Update SQLite Repository

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py`
- Test: `tests/core/integration/test_api_controllers.py` (already updated, serves as integration test)

- [ ] **Step 1: Update save mapping**

In `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py`, change line 335:

From:
```python
            "process_speed": str(c.ai_config.process_speed),
```

To:
```python
            "process_speed": str(c.process_speed),
```

- [ ] **Step 2: Update load mapping**

In the same file, change line 415:

From:
```python
            ai_config=AIConfig(
                engine=AIEngine(row["ai_engine"]),
                objective=ControlObjective(row["objetivo_controle"]),
                process_speed=ProcessSpeed(row["process_speed"]),
                dead_time_l=row["tempo_morto_l"],
                limit_min=row["ai_limit_min"],
                limit_max=row["ai_limit_max"],
            ),
```

To:
```python
            process_speed=ProcessSpeed(row["process_speed"]),
            ai_config=AIConfig(
                engine=AIEngine(row["ai_engine"]),
                objective=ControlObjective(row["objetivo_controle"]),
                dead_time_l=row["tempo_morto_l"],
                limit_min=row["ai_limit_min"],
                limit_max=row["ai_limit_max"],
            ),
```

- [ ] **Step 3: Run tests to verify roundtrip works**

Run: `uv run pytest tests/core/integration/test_api_controllers.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py
git commit -m "refactor(sqlite): read/write process_speed from Controller root"
```

---

### Task 6: Update AI Engines (remove SPEED_FACTORS dict)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py:104-108`
- Modify: `packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py:13`
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/workers/ai_worker.py:102,116`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/ai.py:42`
- Test: `tests/core/unit/test_fuzzy_engine.py`, `tests/core/unit/test_rl_engine.py`

- [ ] **Step 1: Remove SPEED_FACTORS from fuzzy_engine.py**

In `packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py`, delete lines 104-108 (the `SPEED_FACTORS` dict). Replace usage at line 230:

From:
```python
        sv = SPEED_FACTORS[speed]
```

To:
```python
        sv = speed.speed_factor
```

- [ ] **Step 2: Update rl_engine.py import and usage**

In `packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py`:

Change line 13 from:
```python
from smart_pid_core.domain.services.fuzzy_engine import SPEED_FACTORS, AIDecision
```

To:
```python
from smart_pid_core.domain.services.fuzzy_engine import AIDecision
```

Change line 336 from:
```python
        sv = SPEED_FACTORS[speed]
```

To:
```python
        sv = speed.speed_factor
```

- [ ] **Step 3: Update ai_worker.py to read from controller**

In `packages/smart_pid_core/src/smart_pid_core/application/workers/ai_worker.py`, change lines 102 and 116:

From:
```python
                            speed=self._ai_config.process_speed,
```

To:
```python
                            speed=self._controller.process_speed,
```

(Both occurrences at lines 102 and 116.)

- [ ] **Step 4: Update ai.py router**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/ai.py`, change line 42:

From:
```python
        speed=worker._ai_config.process_speed,
```

To:
```python
        speed=worker._controller.process_speed,
```

- [ ] **Step 5: Update AI integration tests**

In `tests/core/integration/test_ai_worker.py`, change line 32:

From:
```python
            process_speed=ProcessSpeed.MEDIUM,
```

To (remove from AIConfig constructor, ensure Controller has it):

If `process_speed` was being passed to `AIConfig(...)`, remove it. Ensure the `Controller(...)` constructor in the test fixture includes `process_speed=ProcessSpeed.MEDIUM`.

Similarly in `tests/core/integration/test_ai_e2e.py`, line 37: move `process_speed` from `AIConfig(...)` to `Controller(...)`.

- [ ] **Step 6: Run all AI tests**

Run: `uv run pytest tests/core/unit/test_fuzzy_engine.py tests/core/unit/test_rl_engine.py tests/core/integration/test_ai_worker.py tests/core/integration/test_ai_e2e.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py \
      packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py \
      packages/smart_pid_core/src/smart_pid_core/application/workers/ai_worker.py \
      packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/ai.py \
      tests/core/integration/test_ai_worker.py tests/core/integration/test_ai_e2e.py
git commit -m "refactor(ai): use ProcessSpeed.speed_factor, remove SPEED_FACTORS dict"
```

---

### Task 7: StatsWorker Dynamic Window

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/workers/stats_worker.py:24-35`
- Test: `tests/core/unit/test_stats_calculator.py` (existing), new test for window computation

- [ ] **Step 1: Write the failing test**

Create or add to `tests/core/unit/test_stats_worker.py`:

```python
from smart_pid_domain.enums import ProcessSpeed


class TestStatsWorkerWindowSize:
    """Verify window_size is computed from process_speed and scan_rate."""

    def test_fast_1000ms(self) -> None:
        """FAST (60s window) at 1000ms scan → 60 samples."""
        assert _compute_window_size(ProcessSpeed.FAST, 1000) == 60

    def test_medium_1000ms(self) -> None:
        """MEDIUM (1200s window) at 1000ms scan → 1200 samples."""
        assert _compute_window_size(ProcessSpeed.MEDIUM, 1000) == 1200

    def test_slow_500ms(self) -> None:
        """SLOW (7200s window) at 500ms scan → 14400 samples."""
        assert _compute_window_size(ProcessSpeed.SLOW, 500) == 14400

    def test_ultra_fast_100ms(self) -> None:
        """ULTRA_FAST (5s window) at 100ms scan → 50 samples."""
        assert _compute_window_size(ProcessSpeed.ULTRA_FAST, 100) == 50


def _compute_window_size(speed: ProcessSpeed, scan_rate_ms: int) -> int:
    """Mirror the formula used in StatsWorker."""
    return speed.stats_window_s * 1000 // scan_rate_ms
```

- [ ] **Step 2: Run test to verify formula is correct**

Run: `uv run pytest tests/core/unit/test_stats_worker.py::TestStatsWorkerWindowSize -v`
Expected: PASS (pure formula test — validates the arithmetic)

- [ ] **Step 3: Update StatsWorker.__init__**

In `packages/smart_pid_core/src/smart_pid_core/application/workers/stats_worker.py`, change the `__init__` method:

From:
```python
    def __init__(
        self,
        bus: EventBus,
        controller: Controller,
        window_size: int = 1800,
        publish_interval: int = 60,
    ) -> None:
        self._bus = bus
        self._controller = controller
        self._publish_interval = publish_interval
        self._calculator = StatsCalculator(
            window_size=window_size,
            span=controller.pv_scale.span,
            setpoint=50.0,  # Updated from telemetry
        )
```

To:
```python
    def __init__(
        self,
        bus: EventBus,
        controller: Controller,
    ) -> None:
        self._bus = bus
        self._controller = controller
        window_size = (
            controller.process_speed.stats_window_s * 1000
            // controller.scan_rate_ms
        )
        self._publish_interval = max(1, window_size // 5)
        self._calculator = StatsCalculator(
            window_size=window_size,
            span=controller.pv_scale.span,
            setpoint=50.0,  # Updated from telemetry
        )
```

- [ ] **Step 4: Run full test suite to check nothing broke**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/stats_worker.py \
      tests/core/unit/test_stats_worker.py
git commit -m "feat(stats): dynamic window size from ProcessSpeed"
```

---

### Task 8: Update ControllerDialog — Move Process Speed to General Tab

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_dialog.py`
- Test: `tests/hmi/widgets/test_controller_dialog.py`, `tests/hmi/widgets/test_add_controller_dialog.py`

- [ ] **Step 1: Update the tests**

In `tests/hmi/widgets/test_controller_dialog.py`:

Move `"process_speed": "SLOW"` from inside `ai_config` to root level in the edit_data fixture (line ~28). Change:

```python
    "process_speed": "SLOW",
```

from inside the `ai_config` dict to the root of the `edit_data` dict.

Update assertions: where the test checks `data["ai_config"]["process_speed"]`, change to `data["process_speed"]`.

In `tests/hmi/widgets/test_add_controller_dialog.py` (line ~116): if it checks for `process_speed` inside `ai_config` keys, update to check at root level. Remove `"process_speed"` from the AI config key check and add a root-level check:

```python
assert data["process_speed"] == "MEDIUM"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/hmi/widgets/test_controller_dialog.py tests/hmi/widgets/test_add_controller_dialog.py -v`
Expected: FAIL — dialog still returns `process_speed` inside `ai_config`

- [ ] **Step 3: Update ControllerDialog**

In `packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_dialog.py`:

**Move combo to General tab** — in `_build_general_tab()`, after the scan_rate row (line ~155), add:

```python
        self._process_speed = QComboBox()
        for member in ProcessSpeed:
            self._process_speed.addItem(member.label, member.value)
        idx = self._process_speed.findData(ProcessSpeed.MEDIUM.value)
        if idx >= 0:
            self._process_speed.setCurrentIndex(idx)
        form.addRow("Process Speed:", self._process_speed)
```

**Remove from AI tab** — in `_build_ai_tab()`, remove the `_ai_speed` combo (lines ~306-307):

```python
        self._ai_speed = _enum_combo(ProcessSpeed, ProcessSpeed.MEDIUM.value)
        form.addRow("Process Speed:", self._ai_speed)
```

**Update `_populate`** — in the `_populate` method:

Remove from the AI section (line ~509):
```python
        self._set_combo(self._ai_speed, ai.get("process_speed"))
```

Add to the General section (after scan_rate, around line ~386):
```python
        if "process_speed" in data:
            idx = self._process_speed.findData(data["process_speed"])
            if idx >= 0:
                self._process_speed.setCurrentIndex(idx)
```

**Update `get_controller_data`** — move `process_speed` from inside `ai_config` to root:

Remove from `ai_config` dict (line ~617):
```python
                "process_speed": self._ai_speed.currentText(),
```

Add at root level after `scan_rate_ms` (line ~519):
```python
            "process_speed": self._process_speed.currentData(),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/hmi/widgets/test_controller_dialog.py tests/hmi/widgets/test_add_controller_dialog.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_hmi/src/smart_pid_hmi/widgets/controller_dialog.py \
      tests/hmi/widgets/test_controller_dialog.py \
      tests/hmi/widgets/test_add_controller_dialog.py
git commit -m "feat(hmi): move Process Speed to General tab with descriptive labels"
```

---

### Task 9: Full Suite Validation and Lint

**Files:** None (validation only)

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v --timeout=60`
Expected: All PASS

- [ ] **Step 2: Run linter**

Run: `uv run --with ruff ruff check .`
Expected: Clean (no errors)

- [ ] **Step 3: Fix any issues found**

If lint or test failures found, fix and re-run.

- [ ] **Step 4: Final commit (if any fixes)**

```bash
git add -A
git commit -m "chore: lint fixes for process speed refactor"
```
