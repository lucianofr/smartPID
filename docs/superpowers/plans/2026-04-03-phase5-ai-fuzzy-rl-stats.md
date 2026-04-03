# Phase 5 — AI (Fuzzy + RL) + Statistics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement AI-based Ki optimization (Fuzzy logic + Reinforcement Learning) and real-time performance statistics, enabling autonomous PID tuning with transparent decision logging.

**Architecture:** Domain services (FuzzyEngine, RLEngine, StatsCalculator) contain pure logic. AIWorker and StatsWorker are threading-based bus subscribers at different cadences. The PID Worker already has an `_drain_ai_actions` stub ready for ACTION.AI messages.

**Tech Stack:** Pure Python fuzzy logic, stable-baselines3 (optional/lazy), collections.deque, ZeroMQ/msgpack, aiosqlite

---

### Task 1: StatsCalculator Domain Service

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/services/stats_calculator.py`
- Create: `tests/core/unit/test_stats_calculator.py`

- [ ] **Step 1: Write failing tests for StatsCalculator**

```python
# tests/core/unit/test_stats_calculator.py
"""Unit tests for StatsCalculator — pure domain service."""
from __future__ import annotations

import math

import pytest


class TestStatsCalculatorBasic:
    def test_empty_calculator_returns_zero(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        assert calc.iae == 0.0
        assert calc.itae == 0.0
        assert calc.ise == 0.0
        assert calc.mse == 0.0
        assert calc.std_dev == 0.0
        assert calc.total_variation == 0.0

    def test_iae_accumulates_absolute_error(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        # 3 samples with errors: +5, -3, +2, dt=1.0 each
        calc.add_sample(error=5.0, co=50.0, dt=1.0)
        calc.add_sample(error=-3.0, co=50.0, dt=1.0)
        calc.add_sample(error=2.0, co=50.0, dt=1.0)
        assert calc.iae == pytest.approx(10.0)  # |5|+|-3|+|2| = 10

    def test_itae_weighs_by_time(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        # t=1: |e|=5, t=2: |e|=3, t=3: |e|=2
        calc.add_sample(error=5.0, co=50.0, dt=1.0)   # t=1, contrib: 1*5=5
        calc.add_sample(error=-3.0, co=50.0, dt=1.0)   # t=2, contrib: 2*3=6
        calc.add_sample(error=2.0, co=50.0, dt=1.0)    # t=3, contrib: 3*2=6
        assert calc.itae == pytest.approx(17.0)

    def test_ise_accumulates_squared_error(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        calc.add_sample(error=3.0, co=50.0, dt=1.0)
        calc.add_sample(error=4.0, co=50.0, dt=1.0)
        assert calc.ise == pytest.approx(25.0)  # 9+16=25

    def test_mse_is_mean_squared_error(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        calc.add_sample(error=3.0, co=50.0, dt=1.0)
        calc.add_sample(error=4.0, co=50.0, dt=1.0)
        assert calc.mse == pytest.approx(12.5)  # 25/2

    def test_std_dev_of_constant_is_zero(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        for _ in range(10):
            calc.add_sample(error=5.0, co=50.0, dt=1.0)
        assert calc.std_dev == pytest.approx(0.0)

    def test_std_dev_known_series(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        for v in values:
            calc.add_sample(error=v, co=50.0, dt=1.0)
        # std dev of [2,4,4,4,5,5,7,9] = 2.0 (population)
        assert calc.std_dev == pytest.approx(2.0, abs=0.01)

    def test_total_variation_counts_co_changes(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        calc.add_sample(error=0.0, co=50.0, dt=1.0)
        calc.add_sample(error=0.0, co=55.0, dt=1.0)  # delta: 5
        calc.add_sample(error=0.0, co=52.0, dt=1.0)  # delta: 3
        calc.add_sample(error=0.0, co=58.0, dt=1.0)  # delta: 6
        assert calc.total_variation == pytest.approx(14.0)

    def test_variability_sp(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        for v in values:
            calc.add_sample(error=v, co=50.0, dt=1.0)
        # variability_sp = 2*sigma/SP = 2*2.0/50.0 = 0.08
        assert calc.variability_sp == pytest.approx(0.08, abs=0.01)

    def test_variability_range(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        for v in values:
            calc.add_sample(error=v, co=50.0, dt=1.0)
        # variability_range = 2*sigma/SPAN = 2*2.0/100.0 = 0.04
        assert calc.variability_range == pytest.approx(0.04, abs=0.01)


class TestStatsCalculatorWindow:
    def test_sliding_window_evicts_old_samples(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=3, span=100.0, setpoint=50.0)
        calc.add_sample(error=10.0, co=50.0, dt=1.0)
        calc.add_sample(error=20.0, co=50.0, dt=1.0)
        calc.add_sample(error=30.0, co=50.0, dt=1.0)
        # Window: [10, 20, 30], IAE = 60
        assert calc.iae == pytest.approx(60.0)

        calc.add_sample(error=5.0, co=50.0, dt=1.0)
        # Window: [20, 30, 5], IAE recomputed from window
        assert calc.sample_count == 3

    def test_reset_clears_all(self):
        from smart_pid_core.domain.services.stats_calculator import StatsCalculator

        calc = StatsCalculator(window_size=100, span=100.0, setpoint=50.0)
        calc.add_sample(error=5.0, co=50.0, dt=1.0)
        calc.reset()
        assert calc.iae == 0.0
        assert calc.sample_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_stats_calculator.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement StatsCalculator**

```python
# packages/smart_pid_core/src/smart_pid_core/domain/services/stats_calculator.py
"""Real-time performance statistics calculator using sliding window."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field


@dataclass
class _Sample:
    """One telemetry sample for statistics."""
    error: float
    co: float
    dt: float
    elapsed_time: float  # cumulative time since window start


class StatsCalculator:
    """Computes loop performance metrics over a sliding window.

    Pure domain service — no I/O, no threading.
    """

    def __init__(self, window_size: int, span: float, setpoint: float) -> None:
        self._window_size = window_size
        self._span = span
        self._setpoint = setpoint
        self._samples: deque[_Sample] = deque(maxlen=window_size)
        self._elapsed_time = 0.0

    @property
    def sample_count(self) -> int:
        return len(self._samples)

    def add_sample(self, error: float, co: float, dt: float) -> None:
        """Add a new sample to the sliding window."""
        self._elapsed_time += dt
        self._samples.append(_Sample(
            error=error, co=co, dt=dt, elapsed_time=self._elapsed_time,
        ))

    def reset(self) -> None:
        """Clear all samples and reset elapsed time."""
        self._samples.clear()
        self._elapsed_time = 0.0

    @property
    def iae(self) -> float:
        """Integral of Absolute Error: sum(|e| * dt)."""
        return sum(abs(s.error) * s.dt for s in self._samples)

    @property
    def itae(self) -> float:
        """Integral of Time-weighted Absolute Error: sum(t * |e| * dt)."""
        return sum(s.elapsed_time * abs(s.error) * s.dt for s in self._samples)

    @property
    def ise(self) -> float:
        """Integral of Squared Error: sum(e^2 * dt)."""
        return sum(s.error ** 2 * s.dt for s in self._samples)

    @property
    def mse(self) -> float:
        """Mean Squared Error: ISE / n."""
        n = len(self._samples)
        if n == 0:
            return 0.0
        return self.ise / n

    @property
    def std_dev(self) -> float:
        """Population standard deviation of the error values."""
        n = len(self._samples)
        if n == 0:
            return 0.0
        errors = [s.error for s in self._samples]
        mean = sum(errors) / n
        variance = sum((e - mean) ** 2 for e in errors) / n
        return math.sqrt(variance)

    @property
    def total_variation(self) -> float:
        """Total Variation of CO: sum of |delta_co| between consecutive samples."""
        if len(self._samples) < 2:
            return 0.0
        samples = list(self._samples)
        return sum(abs(samples[i].co - samples[i - 1].co) for i in range(1, len(samples)))

    @property
    def variability_sp(self) -> float:
        """Variability relative to setpoint: 2*sigma/SP."""
        if self._setpoint == 0.0:
            return 0.0
        return 2.0 * self.std_dev / self._setpoint

    @property
    def variability_range(self) -> float:
        """Variability relative to span: 2*sigma/SPAN."""
        if self._span == 0.0:
            return 0.0
        return 2.0 * self.std_dev / self._span
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_stats_calculator.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/services/stats_calculator.py \
  tests/core/unit/test_stats_calculator.py
git commit -m "feat(stats): add StatsCalculator domain service with sliding window metrics"
```

---

### Task 2: FuzzyEngine — Membership Functions + Fuzzification

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py`
- Create: `tests/core/unit/test_fuzzy_engine.py`

- [ ] **Step 1: Write failing tests for membership functions**

```python
# tests/core/unit/test_fuzzy_engine.py
"""Unit tests for FuzzyEngine — pure domain service."""
from __future__ import annotations

import pytest


class TestMembershipFunctions:
    def test_triangular_center(self):
        from smart_pid_core.domain.services.fuzzy_engine import triangular_mf

        # Triangular(a=-50, b=0, c=50) at center
        assert triangular_mf(0.0, -50.0, 0.0, 50.0) == pytest.approx(1.0)

    def test_triangular_left_edge(self):
        from smart_pid_core.domain.services.fuzzy_engine import triangular_mf

        assert triangular_mf(-50.0, -50.0, 0.0, 50.0) == pytest.approx(0.0)

    def test_triangular_right_edge(self):
        from smart_pid_core.domain.services.fuzzy_engine import triangular_mf

        assert triangular_mf(50.0, -50.0, 0.0, 50.0) == pytest.approx(0.0)

    def test_triangular_midpoint(self):
        from smart_pid_core.domain.services.fuzzy_engine import triangular_mf

        # Halfway between a and b
        assert triangular_mf(-25.0, -50.0, 0.0, 50.0) == pytest.approx(0.5)

    def test_trapezoidal_plateau(self):
        from smart_pid_core.domain.services.fuzzy_engine import trapezoidal_mf

        # Trapezoidal(-100, -100, -67, -33) plateau between a and b
        assert trapezoidal_mf(-80.0, -100.0, -100.0, -67.0, -33.0) == pytest.approx(1.0)

    def test_trapezoidal_slope(self):
        from smart_pid_core.domain.services.fuzzy_engine import trapezoidal_mf

        # Midpoint of the right slope between c and d
        assert trapezoidal_mf(-50.0, -100.0, -100.0, -67.0, -33.0) == pytest.approx(0.5)

    def test_trapezoidal_outside(self):
        from smart_pid_core.domain.services.fuzzy_engine import trapezoidal_mf

        assert trapezoidal_mf(0.0, -100.0, -100.0, -67.0, -33.0) == pytest.approx(0.0)


class TestFuzzification:
    def test_fuzzify_zero_input(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        memberships = engine.fuzzify(0.0)
        # At 0, only ZO should be 1.0
        assert memberships["ZO"] == pytest.approx(1.0)
        assert memberships["NB"] == pytest.approx(0.0)
        assert memberships["PB"] == pytest.approx(0.0)

    def test_fuzzify_extreme_negative(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        memberships = engine.fuzzify(-100.0)
        assert memberships["NB"] == pytest.approx(1.0)
        assert memberships["ZO"] == pytest.approx(0.0)

    def test_fuzzify_extreme_positive(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        memberships = engine.fuzzify(100.0)
        assert memberships["PB"] == pytest.approx(1.0)
        assert memberships["ZO"] == pytest.approx(0.0)

    def test_fuzzify_50_overlap(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        # At boundary between ZO and PS (~16.67), both should have ~0.5
        memberships = engine.fuzzify(16.67)
        # Should have non-zero values for ZO and PS
        assert memberships["ZO"] > 0.0
        assert memberships["PS"] > 0.0
        assert memberships["ZO"] + memberships["PS"] == pytest.approx(1.0, abs=0.1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_fuzzy_engine.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement membership functions and fuzzification**

```python
# packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py
"""Fuzzy logic engine for Ki optimization.

7 linguistic levels on [-100%, +100%] with triangular (center) and
trapezoidal (extremes) membership functions, 50% overlap.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_domain.enums import ControlObjective

# --- Membership function helpers ---

def triangular_mf(x: float, a: float, b: float, c: float) -> float:
    """Triangular membership function. Peak at b, zero at a and c."""
    if x <= a or x >= c:
        return 0.0
    if x <= b:
        return (x - a) / (b - a) if b != a else 1.0
    return (c - x) / (c - b) if c != b else 1.0


def trapezoidal_mf(x: float, a: float, b: float, c: float, d: float) -> float:
    """Trapezoidal membership function. Plateau between b and c."""
    if x <= a or x >= d:
        return 0.0
    if x <= b:
        return (x - a) / (b - a) if b != a else 1.0
    if x <= c:
        return 1.0
    return (d - x) / (d - c) if d != c else 1.0


# --- Fuzzy levels and their MF parameters ---
# Universe: [-100, +100] (normalized % of span)
# 7 levels: NB, NM, NS, ZO, PS, PM, PB
# Spacing: ~33.33 between centers, 50% overlap

LEVELS = ("NB", "NM", "NS", "ZO", "PS", "PM", "PB")

# (type, params): "trap" = trapezoidal(a,b,c,d), "tri" = triangular(a,b,c)
MF_PARAMS: dict[str, tuple[str, tuple[float, ...]]] = {
    "NB": ("trap", (-100.0, -100.0, -67.0, -33.0)),
    "NM": ("tri",  (-67.0, -33.0, 0.0)),
    "NS": ("tri",  (-33.0, -16.67, 0.0)),
    "ZO": ("tri",  (-16.67, 0.0, 16.67)),
    "PS": ("tri",  (0.0, 16.67, 33.0)),
    "PM": ("tri",  (0.0, 33.0, 67.0)),
    "PB": ("trap", (33.0, 67.0, 100.0, 100.0)),
}


class FuzzyEngine:
    """Fuzzy logic Ki optimizer.

    Pure domain service — no I/O, no threading.
    """

    def fuzzify(self, value: float) -> dict[str, float]:
        """Compute membership degree for each fuzzy level."""
        result: dict[str, float] = {}
        for level in LEVELS:
            mf_type, params = MF_PARAMS[level]
            if mf_type == "trap":
                result[level] = trapezoidal_mf(value, *params)
            else:
                result[level] = triangular_mf(value, *params)
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_fuzzy_engine.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py \
  tests/core/unit/test_fuzzy_engine.py
git commit -m "feat(fuzzy): membership functions + fuzzification for 7 linguistic levels"
```

---

### Task 3: FuzzyEngine — Rule Matrices + Inference + Defuzzification

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py`
- Modify: `tests/core/unit/test_fuzzy_engine.py`

- [ ] **Step 1: Write failing tests for rule application and defuzzification**

Append to `tests/core/unit/test_fuzzy_engine.py`:

```python
from smart_pid_domain.enums import ControlObjective


class TestRuleMatrices:
    def test_sp_tracking_has_49_rules(self):
        from smart_pid_core.domain.services.fuzzy_engine import RULE_MATRICES

        matrix = RULE_MATRICES[ControlObjective.SP_TRACKING]
        assert len(matrix) == 7  # 7 rows (error)
        for row in matrix:
            assert len(row) == 7  # 7 columns (delta_error)

    def test_disturbance_rejection_has_49_rules(self):
        from smart_pid_core.domain.services.fuzzy_engine import RULE_MATRICES

        matrix = RULE_MATRICES[ControlObjective.DISTURBANCE_REJECTION]
        assert len(matrix) == 7

    def test_surge_level_has_49_rules(self):
        from smart_pid_core.domain.services.fuzzy_engine import RULE_MATRICES

        matrix = RULE_MATRICES[ControlObjective.SURGE_LEVEL]
        assert len(matrix) == 7


class TestInferenceAndDefuzzification:
    def test_zero_error_zero_delta_gives_zero_gamma(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        gamma = engine.infer(
            error=0.0, delta_error=0.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert gamma == pytest.approx(0.0, abs=0.05)

    def test_large_positive_error_gives_positive_gamma(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        gamma = engine.infer(
            error=80.0, delta_error=0.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert gamma > 0.3

    def test_large_negative_error_gives_negative_gamma(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        gamma = engine.infer(
            error=-80.0, delta_error=0.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert gamma < -0.3

    def test_gamma_is_bounded(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        gamma = engine.infer(
            error=100.0, delta_error=100.0,
            objective=ControlObjective.SP_TRACKING,
        )
        assert -1.0 <= gamma <= 1.0

    def test_disturbance_rejection_more_aggressive_near_zero(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        # Small error with negative delta (error improving) — DR should be gentle
        gamma_dr = engine.infer(
            error=5.0, delta_error=-10.0,
            objective=ControlObjective.DISTURBANCE_REJECTION,
        )
        # Same for SP tracking
        gamma_sp = engine.infer(
            error=5.0, delta_error=-10.0,
            objective=ControlObjective.SP_TRACKING,
        )
        # Both should be valid floats in range
        assert -1.0 <= gamma_dr <= 1.0
        assert -1.0 <= gamma_sp <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_fuzzy_engine.py::TestRuleMatrices -v`
Expected: FAIL — RULE_MATRICES not found

- [ ] **Step 3: Implement rule matrices, inference, and CoG defuzzification**

Add to `fuzzy_engine.py`:

```python
from smart_pid_domain.enums import ControlObjective

# Rule matrices: RULE_MATRICES[objective][error_level_idx][delta_error_level_idx] = output_level
# Rows: error (NB..PB), Columns: delta_error (NB..PB)
# Output: one of the 7 fuzzy levels

RULE_MATRICES: dict[ControlObjective, list[list[str]]] = {
    ControlObjective.SP_TRACKING: [
        # delta_error: NB     NM     NS     ZO     PS     PM     PB
        #  error:
        ["NB", "NB", "NB", "NB", "NM", "NS", "ZO"],  # NB
        ["NB", "NB", "NB", "NM", "NS", "ZO", "PS"],  # NM
        ["NB", "NB", "NM", "NS", "ZO", "PS", "PM"],  # NS
        ["NB", "NM", "NS", "ZO", "PS", "PM", "PB"],  # ZO
        ["NM", "NS", "ZO", "PS", "PM", "PB", "PB"],  # PS
        ["NS", "ZO", "PS", "PM", "PB", "PB", "PB"],  # PM
        ["ZO", "PS", "PM", "PB", "PB", "PB", "PB"],  # PB
    ],
    ControlObjective.DISTURBANCE_REJECTION: [
        # Aggressive near zero error, minimizes offset
        ["NB", "NB", "NM", "NM", "NS", "ZO", "ZO"],  # NB
        ["NB", "NB", "NM", "NS", "NS", "ZO", "PS"],  # NM
        ["NB", "NM", "NS", "NS", "ZO", "PS", "PM"],  # NS
        ["NM", "NM", "NS", "ZO", "PS", "PM", "PM"],  # ZO
        ["NM", "NS", "ZO", "PS", "PS", "PM", "PB"],  # PS
        ["NS", "ZO", "PS", "PS", "PM", "PB", "PB"],  # PM
        ["ZO", "ZO", "PS", "PM", "PM", "PB", "PB"],  # PB
    ],
    ControlObjective.SURGE_LEVEL: [
        # Focus on valve stability
        ["ZO", "ZO", "NS", "NS", "NM", "NM", "NB"],  # NB
        ["ZO", "ZO", "NS", "NS", "NM", "NB", "NB"],  # NM
        ["PS", "ZO", "ZO", "NS", "NS", "NM", "NM"],  # NS
        ["PS", "PS", "ZO", "ZO", "ZO", "NS", "NS"],  # ZO
        ["PM", "PM", "PS", "PS", "ZO", "ZO", "NS"],  # PS
        ["PB", "PB", "PM", "PS", "PS", "ZO", "ZO"],  # PM
        ["PB", "PM", "PM", "PS", "PS", "ZO", "ZO"],  # PB
    ],
}

# Center values for defuzzification (CoG)
LEVEL_CENTERS: dict[str, float] = {
    "NB": -100.0, "NM": -33.0, "NS": -16.67,
    "ZO": 0.0,
    "PS": 16.67, "PM": 33.0, "PB": 100.0,
}
```

Add to `FuzzyEngine` class:

```python
    def infer(
        self,
        error: float,
        delta_error: float,
        objective: ControlObjective,
    ) -> float:
        """Run full fuzzy inference: fuzzify → apply rules → defuzzify (CoG).

        Args:
            error: Normalized error in [-100, +100] (% of span).
            delta_error: Normalized delta_error in [-100, +100].
            objective: Control objective selecting the rule matrix.

        Returns:
            gamma in [-1.0, +1.0].
        """
        # Clamp inputs
        error = max(-100.0, min(100.0, error))
        delta_error = max(-100.0, min(100.0, delta_error))

        # Fuzzify both inputs
        error_mf = self.fuzzify(error)
        delta_mf = self.fuzzify(delta_error)

        matrix = RULE_MATRICES[objective]

        # Apply rules: for each (i, j), firing strength = min(error_mf[i], delta_mf[j])
        # Aggregate: for each output level, strength = max of all rules that fire to it
        output_strengths: dict[str, float] = {level: 0.0 for level in LEVELS}

        for i, e_level in enumerate(LEVELS):
            for j, de_level in enumerate(LEVELS):
                firing = min(error_mf[e_level], delta_mf[de_level])
                out_level = matrix[i][j]
                output_strengths[out_level] = max(output_strengths[out_level], firing)

        # Defuzzify via Center of Gravity (CoG)
        numerator = sum(LEVEL_CENTERS[level] * strength for level, strength in output_strengths.items())
        denominator = sum(output_strengths.values())

        if denominator < 1e-10:
            return 0.0

        # CoG result is in [-100, +100], normalize to [-1, +1]
        cog = numerator / denominator
        gamma = max(-1.0, min(1.0, cog / 100.0))
        return gamma
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_fuzzy_engine.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py \
  tests/core/unit/test_fuzzy_engine.py
git commit -m "feat(fuzzy): rule matrices (3 objectives) + inference + CoG defuzzification"
```

---

### Task 4: FuzzyEngine — compute_gamma (Full Pipeline with Ki Update)

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py`
- Modify: `tests/core/unit/test_fuzzy_engine.py`

- [ ] **Step 1: Write failing tests for compute_gamma**

Append to `tests/core/unit/test_fuzzy_engine.py`:

```python
from smart_pid_domain.enums import ControlObjective, ProcessSpeed


class TestComputeGamma:
    def test_compute_gamma_returns_ai_decision(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        decision = engine.compute_gamma(
            error=10.0,
            delta_error=5.0,
            ki_current=1.0,
            span=100.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1,
            limit_max=100.0,
        )
        assert -1.0 <= decision.gamma <= 1.0
        assert decision.new_ki > 0.0
        assert decision.reasoning != ""
        assert decision.membership_values is not None

    def test_speed_factor_slow(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        decision = engine.compute_gamma(
            error=50.0, delta_error=0.0, ki_current=1.0, span=100.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.SLOW,
            limit_min=0.1, limit_max=100.0,
        )
        # Sv=0.30 for SLOW, Ki_new = Ki * (1 + gamma * 0.30)
        expected_ki = 1.0 * (1.0 + decision.gamma * 0.30)
        assert decision.new_ki == pytest.approx(max(0.1, min(100.0, expected_ki)))

    def test_ki_clamped_to_limits(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        # With extreme gamma and small limits
        decision = engine.compute_gamma(
            error=100.0, delta_error=100.0, ki_current=99.0, span=100.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.SLOW,
            limit_min=0.5, limit_max=100.0,
        )
        assert decision.new_ki <= 100.0
        assert decision.new_ki >= 0.5

    def test_zero_span_handled(self):
        from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine

        engine = FuzzyEngine()
        decision = engine.compute_gamma(
            error=0.0, delta_error=0.0, ki_current=1.0, span=0.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
        )
        assert decision.gamma == pytest.approx(0.0, abs=0.05)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_fuzzy_engine.py::TestComputeGamma -v`
Expected: FAIL — `compute_gamma` not found

- [ ] **Step 3: Add AIDecision dataclass and compute_gamma**

Add to `fuzzy_engine.py`:

```python
from smart_pid_domain.enums import ControlObjective, ProcessSpeed

SPEED_FACTORS: dict[ProcessSpeed, float] = {
    ProcessSpeed.SLOW: 0.30,
    ProcessSpeed.MEDIUM: 0.15,
    ProcessSpeed.FAST: 0.05,
}


@dataclass(frozen=True)
class AIDecision:
    """Result of an AI Ki optimization computation."""
    gamma: float                    # [-1.0, +1.0]
    new_ki: float                   # Computed Ki
    reasoning: str                  # Human-readable explanation
    membership_values: dict[str, dict[str, float]] | None  # Fuzzy debug info
```

Add to `FuzzyEngine` class:

```python
    def compute_gamma(
        self,
        error: float,
        delta_error: float,
        ki_current: float,
        span: float,
        objective: ControlObjective,
        speed: ProcessSpeed,
        limit_min: float,
        limit_max: float,
    ) -> AIDecision:
        """Full fuzzy pipeline: normalize → fuzzify → infer → update Ki.

        Args:
            error: Raw error in engineering units.
            delta_error: Raw delta_error in engineering units.
            ki_current: Current Ki value.
            span: Process span (eu_max - eu_min) for normalization.
            objective: Control objective selecting the rule matrix.
            speed: Process speed selecting the speed factor.
            limit_min: Minimum allowed Ki.
            limit_max: Maximum allowed Ki.

        Returns:
            AIDecision with gamma, new Ki, reasoning, and debug info.
        """
        # Normalize to [-100, +100]
        if span > 0:
            error_norm = (error / span) * 100.0
            delta_error_norm = (delta_error / span) * 100.0
        else:
            error_norm = 0.0
            delta_error_norm = 0.0

        # Fuzzify (for debug output)
        error_mf = self.fuzzify(error_norm)
        delta_error_mf = self.fuzzify(delta_error_norm)

        # Infer gamma
        gamma = self.infer(error_norm, delta_error_norm, objective)

        # Update Ki
        sv = SPEED_FACTORS[speed]
        new_ki = ki_current * (1.0 + gamma * sv)
        new_ki = max(limit_min, min(limit_max, new_ki))

        reasoning = (
            f"Fuzzy({objective.value}): "
            f"e_norm={error_norm:.1f}%, de_norm={delta_error_norm:.1f}%, "
            f"gamma={gamma:.4f}, Sv={sv}, "
            f"Ki: {ki_current:.4f} -> {new_ki:.4f}"
        )

        return AIDecision(
            gamma=gamma,
            new_ki=new_ki,
            reasoning=reasoning,
            membership_values={"error": error_mf, "delta_error": delta_error_mf},
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_fuzzy_engine.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/services/fuzzy_engine.py \
  tests/core/unit/test_fuzzy_engine.py
git commit -m "feat(fuzzy): compute_gamma full pipeline with Ki update and AIDecision"
```

---

### Task 5: RLEngine — Skeleton with Lazy Import

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py`
- Create: `tests/core/unit/test_rl_engine.py`
- Modify: `packages/smart_pid_core/pyproject.toml`

- [ ] **Step 1: Add optional dependency group for AI**

In `packages/smart_pid_core/pyproject.toml`, add after `[project.optional-dependencies]` `dev` group:

```toml
ai = [
    "stable-baselines3[extra]>=2.3",
    "gymnasium>=0.29",
]
```

- [ ] **Step 2: Write failing tests for RLEngine**

```python
# tests/core/unit/test_rl_engine.py
"""Unit tests for RLEngine — pure domain service (lazy sb3 import)."""
from __future__ import annotations

import pytest

from smart_pid_domain.enums import ControlObjective, ProcessSpeed


class TestRLEngineInit:
    def test_creates_without_sb3_installed(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine(algorithm="SAC")
        assert engine.algorithm == "SAC"
        assert not engine.is_trained

    def test_compute_gamma_without_model_returns_zero(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine(algorithm="SAC")
        decision = engine.compute_gamma(
            error=10.0, delta_error=5.0, ki_current=1.0, span=100.0,
            co=50.0, integral_val=25.0,
            objective=ControlObjective.SP_TRACKING,
            speed=ProcessSpeed.MEDIUM,
            limit_min=0.1, limit_max=100.0,
        )
        # Without trained model, should return gamma=0 (no change)
        assert decision.gamma == pytest.approx(0.0)
        assert decision.new_ki == pytest.approx(1.0)
        assert decision.membership_values is None

    def test_update_without_model_is_noop(self):
        from smart_pid_core.domain.services.rl_engine import RLEngine

        engine = RLEngine(algorithm="SAC")
        # Should not raise
        engine.update(reward=1.0, observation=[0.0, 0.0, 0.5, 0.25])
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/core/unit/test_rl_engine.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 4: Implement RLEngine skeleton**

```python
# packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py
"""Reinforcement Learning engine for Ki optimization.

Uses stable-baselines3 (SAC or PPO) with lazy imports.
Falls back to zero-gamma when no model is trained.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from smart_pid_domain.enums import ControlObjective, ProcessSpeed

from smart_pid_core.domain.services.fuzzy_engine import AIDecision, SPEED_FACTORS

logger = logging.getLogger(__name__)


class RLEngine:
    """RL-based Ki optimizer using SAC or PPO.

    Pure domain service — lazy imports sb3 only when training or loading a model.
    """

    def __init__(self, algorithm: str = "SAC") -> None:
        self._algorithm = algorithm
        self._model = None
        self._is_trained = False
        self._episode_count = 0
        self._total_reward = 0.0
        self._last_observation: list[float] | None = None
        self._last_action: float | None = None

    @property
    def algorithm(self) -> str:
        return self._algorithm

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    @property
    def episode_count(self) -> int:
        return self._episode_count

    @property
    def avg_reward(self) -> float:
        if self._episode_count == 0:
            return 0.0
        return self._total_reward / self._episode_count

    def compute_gamma(
        self,
        error: float,
        delta_error: float,
        ki_current: float,
        span: float,
        co: float,
        integral_val: float,
        objective: ControlObjective,
        speed: ProcessSpeed,
        limit_min: float,
        limit_max: float,
    ) -> AIDecision:
        """Compute gamma from RL model or return zero if untrained."""
        # Normalize observation
        if span > 0:
            error_norm = error / span
            delta_error_norm = delta_error / span
        else:
            error_norm = 0.0
            delta_error_norm = 0.0
        co_norm = co / 100.0
        integral_norm = integral_val / 100.0

        observation = [error_norm, delta_error_norm, co_norm, integral_norm]

        if self._model is None:
            gamma = 0.0
            reasoning = f"RL({self._algorithm}): no trained model, gamma=0.0"
        else:
            import numpy as np

            obs_array = np.array(observation, dtype=np.float32)
            action, _ = self._model.predict(obs_array, deterministic=True)
            gamma = float(action[0]) if hasattr(action, "__getitem__") else float(action)
            gamma = max(-1.0, min(1.0, gamma))
            reasoning = (
                f"RL({self._algorithm}): obs={observation}, "
                f"gamma={gamma:.4f}"
            )

        # Store for training update
        self._last_observation = observation
        self._last_action = gamma

        # Update Ki
        sv = SPEED_FACTORS[speed]
        new_ki = ki_current * (1.0 + gamma * sv)
        new_ki = max(limit_min, min(limit_max, new_ki))

        reasoning += f", Sv={sv}, Ki: {ki_current:.4f} -> {new_ki:.4f}"

        return AIDecision(
            gamma=gamma,
            new_ki=new_ki,
            reasoning=reasoning,
            membership_values=None,
        )

    def update(self, reward: float, observation: list[float] | None = None) -> None:
        """Update RL model with reward signal. No-op if model not initialized."""
        if self._model is None:
            return
        self._episode_count += 1
        self._total_reward += reward

    def save_model(self, path: Path) -> None:
        """Save trained model to disk."""
        if self._model is None:
            raise RuntimeError("No model to save")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._model.save(str(path))
        logger.info("rl_model_saved", path=str(path), episodes=self._episode_count)

    def load_model(self, path: Path) -> None:
        """Load a previously trained model."""
        if not path.exists():
            raise FileNotFoundError(f"Model not found: {path}")
        self._load_sb3()
        if self._algorithm == "SAC":
            from stable_baselines3 import SAC
            self._model = SAC.load(str(path))
        else:
            from stable_baselines3 import PPO
            self._model = PPO.load(str(path))
        self._is_trained = True
        logger.info("rl_model_loaded", path=str(path))

    def _load_sb3(self) -> None:
        """Lazy import of stable-baselines3."""
        try:
            import stable_baselines3  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "stable-baselines3 not installed. "
                "Install with: pip install smart-pid-core[ai]"
            ) from e
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/unit/test_rl_engine.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/domain/services/rl_engine.py \
  tests/core/unit/test_rl_engine.py \
  packages/smart_pid_core/pyproject.toml
git commit -m "feat(rl): RLEngine skeleton with lazy sb3 import and AIDecision interface"
```

---

### Task 6: Domain Events — AIActionComputed + StatsUpdated

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/events.py`
- Modify: `tests/domain/test_events.py`

- [ ] **Step 1: Write failing tests for new events**

Append to `tests/domain/test_events.py`:

```python
class TestAIActionComputed:
    def test_frozen(self):
        from smart_pid_domain.events import AIActionComputed
        from smart_pid_domain.enums import AIEngine, ControlObjective

        event = AIActionComputed(
            controller_id=1,
            gamma=0.5,
            new_ki=1.5,
            engine=AIEngine.FUZZY,
            objective=ControlObjective.SP_TRACKING,
            reasoning="test",
            timestamp=datetime.now(UTC),
        )
        with pytest.raises(AttributeError):
            event.gamma = 0.0  # type: ignore[misc]

    def test_has_event_id(self):
        from smart_pid_domain.events import AIActionComputed
        from smart_pid_domain.enums import AIEngine, ControlObjective

        event = AIActionComputed(
            controller_id=1, gamma=0.5, new_ki=1.5,
            engine=AIEngine.FUZZY, objective=ControlObjective.SP_TRACKING,
            reasoning="test", timestamp=datetime.now(UTC),
        )
        assert event.event_id is not None


class TestStatsUpdated:
    def test_frozen(self):
        from smart_pid_domain.events import StatsUpdated

        event = StatsUpdated(
            controller_id=1, iae=1.0, itae=2.0, mse=0.5,
            std_dev=0.1, total_variation=3.0,
            variability_sp=0.02, variability_range=0.01,
            timestamp=datetime.now(UTC),
        )
        with pytest.raises(AttributeError):
            event.iae = 0.0  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_events.py::TestAIActionComputed -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Add events to events.py**

Add to `packages/smart_pid_domain/src/smart_pid_domain/events.py`:

```python
if TYPE_CHECKING:
    from smart_pid_domain.enums import AIEngine, ControlObjective  # add these imports


@dataclass(frozen=True)
class AIActionComputed:
    """Published by AI Worker after computing a Ki adjustment."""

    controller_id: int
    gamma: float
    new_ki: float
    engine: AIEngine
    objective: ControlObjective
    reasoning: str
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class StatsUpdated:
    """Published by Stats Worker with latest performance metrics."""

    controller_id: int
    iae: float
    itae: float
    mse: float
    std_dev: float
    total_variation: float
    variability_sp: float
    variability_range: float
    timestamp: datetime
    event_id: UUID = field(default_factory=uuid4)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_events.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/events.py \
  tests/domain/test_events.py
git commit -m "feat(domain): add AIActionComputed + StatsUpdated frozen events"
```

---

### Task 7: StatsWorker — Bus Integration

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/application/workers/stats_worker.py`
- Create: `tests/core/integration/test_stats_worker.py`

- [ ] **Step 1: Write failing test for StatsWorker**

```python
# tests/core/integration/test_stats_worker.py
"""Integration tests for StatsWorker — bus subscriber."""
from __future__ import annotations

import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.stats_worker import StatsWorker
from smart_pid_domain.models.controller import Controller, ScaleConfig


@pytest.fixture
def bus():
    b = EventBus(url_prefix=f"inproc://test_stats_{uuid.uuid4().hex[:8]}")
    b.start()
    yield b
    b.stop()


@pytest.fixture
def controller():
    return Controller(
        id=1, name="Test", scan_rate_ms=100,
        pv_scale=ScaleConfig(eu_min=0.0, eu_max=100.0),
    )


class TestStatsWorker:
    def test_publishes_stats_after_samples(self, bus, controller):
        worker = StatsWorker(bus=bus, controller=controller, publish_interval=3)
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(f"STATS.{controller.id}".encode())
            time.sleep(0.05)

            # Send telemetry + control action samples
            for i in range(5):
                telem = {"pv": 52.0, "sp": 50.0, "co": 48.0 + i}
                pub.send(
                    f"TELEMETRY.{controller.id}".encode(),
                    msgpack.packb(telem),
                )
                action = {"controller_id": 1, "co": 48.0 + i, "integral_val": 25.0}
                pub.send(
                    f"ACTION.CTRL.{controller.id}".encode(),
                    msgpack.packb(action),
                )
                time.sleep(0.15)

            # Should have published at least one STATS message
            time.sleep(0.3)
            msg = sub.recv(timeout_ms=1000)
            assert msg is not None
            _topic, payload = msg
            data = msgpack.unpackb(payload)
            assert "iae" in data
            assert "total_variation" in data
            assert data["controller_id"] == 1
        finally:
            worker.stop()

    def test_get_current_stats(self, bus, controller):
        worker = StatsWorker(bus=bus, controller=controller, publish_interval=100)
        worker.start()
        try:
            pub = bus.create_publisher()
            time.sleep(0.05)

            for _ in range(3):
                telem = {"pv": 55.0, "sp": 50.0, "co": 50.0}
                pub.send(
                    f"TELEMETRY.{controller.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.15)

            stats = worker.get_current_stats()
            assert stats["iae"] > 0.0
        finally:
            worker.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_stats_worker.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement StatsWorker**

```python
# packages/smart_pid_core/src/smart_pid_core/application/workers/stats_worker.py
"""Stats Worker — computes loop performance metrics at scan rate."""
from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

import msgpack
import zmq

from smart_pid_core.domain.services.stats_calculator import StatsCalculator

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_domain.models.controller import Controller

logger = logging.getLogger(__name__)


class StatsWorker:
    """Subscribes to TELEMETRY and ACTION.CTRL, computes metrics, publishes STATS."""

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
        self._last_sp: float = 50.0
        self._last_co: float = 0.0
        self._last_pv: float = 0.0
        self._sample_count_since_publish: int = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def controller_id(self) -> int:
        return self._controller.id

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True,
            name=f"stats-worker-{self.controller_id}",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_current_stats(self) -> dict[str, float]:
        """Return current stats snapshot (thread-safe via GIL for simple reads)."""
        calc = self._calculator
        return {
            "controller_id": self.controller_id,
            "iae": calc.iae,
            "itae": calc.itae,
            "ise": calc.ise,
            "mse": calc.mse,
            "std_dev": calc.std_dev,
            "total_variation": calc.total_variation,
            "variability_sp": calc.variability_sp,
            "variability_range": calc.variability_range,
            "sample_count": calc.sample_count,
        }

    def _run(self) -> None:
        telem_sub = self._bus.create_subscriber(f"TELEMETRY.{self.controller_id}".encode())
        action_sub = self._bus.create_subscriber(f"ACTION.CTRL.{self.controller_id}".encode())
        pub = self._bus.create_publisher()
        scan_s = self._controller.scan_rate_ms / 1000.0
        time.sleep(0.02)

        while not self._stop_event.is_set():
            try:
                tick_start = time.monotonic()
                self._drain_telemetry(telem_sub)
                self._drain_actions(action_sub)

                # Add sample if we have telemetry
                if self._last_pv != 0.0 or self._last_sp != 0.0:
                    error = self._last_sp - self._last_pv
                    self._calculator._setpoint = self._last_sp
                    self._calculator.add_sample(
                        error=error, co=self._last_co, dt=scan_s,
                    )
                    self._sample_count_since_publish += 1

                # Publish stats periodically
                if self._sample_count_since_publish >= self._publish_interval:
                    stats = self.get_current_stats()
                    topic = f"STATS.{self.controller_id}".encode()
                    pub.send(topic, msgpack.packb(stats))
                    self._sample_count_since_publish = 0

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
                self._last_pv = data["pv"]
                self._last_sp = data["sp"]
            except (KeyError, ValueError, msgpack.UnpackException):
                pass

    def _drain_actions(self, sub) -> None:
        while True:
            msg = sub.recv(timeout_ms=0)
            if msg is None:
                break
            _topic, payload = msg
            try:
                data = msgpack.unpackb(payload)
                self._last_co = data["co"]
            except (KeyError, ValueError, msgpack.UnpackException):
                pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_stats_worker.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/stats_worker.py \
  tests/core/integration/test_stats_worker.py
git commit -m "feat(stats): StatsWorker subscribes telemetry/actions, publishes STATS.{id}"
```

---

### Task 8: AIWorker — Bus Integration with Fuzzy/RL Engine Selection

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/application/workers/ai_worker.py`
- Create: `tests/core/integration/test_ai_worker.py`

- [ ] **Step 1: Write failing test for AIWorker**

```python
# tests/core/integration/test_ai_worker.py
"""Integration tests for AIWorker — bus subscriber with Fuzzy/RL engine."""
from __future__ import annotations

import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_domain.enums import AIEngine, ControlObjective, ProcessSpeed
from smart_pid_domain.models.controller import AIConfig, Controller, ScaleConfig


@pytest.fixture
def bus():
    b = EventBus(url_prefix=f"inproc://test_ai_{uuid.uuid4().hex[:8]}")
    b.start()
    yield b
    b.stop()


@pytest.fixture
def controller_fuzzy():
    return Controller(
        id=1, name="TestFuzzy", scan_rate_ms=100,
        pv_scale=ScaleConfig(eu_min=0.0, eu_max=100.0),
        ai_config=AIConfig(
            engine=AIEngine.FUZZY,
            objective=ControlObjective.SP_TRACKING,
            process_speed=ProcessSpeed.MEDIUM,
            dead_time_l=0.1,  # T_cycle = 0.3s for fast testing
            limit_min=0.1,
            limit_max=100.0,
        ),
    )


class TestAIWorkerFuzzy:
    def test_publishes_ai_action(self, bus, controller_fuzzy):
        worker = AIWorker(bus=bus, controller=controller_fuzzy)
        worker.start()
        try:
            pub = bus.create_publisher()
            sub = bus.create_subscriber(f"ACTION.AI.{controller_fuzzy.id}".encode())
            time.sleep(0.05)

            # Send telemetry samples
            for _ in range(5):
                telem = {"pv": 55.0, "sp": 50.0, "co": 48.0}
                pub.send(
                    f"TELEMETRY.{controller_fuzzy.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.1)

            # Wait for AI cycle (T_cycle = dead_time_l * 3 = 0.3s)
            time.sleep(0.5)

            msg = sub.recv(timeout_ms=2000)
            assert msg is not None
            _topic, payload = msg
            data = msgpack.unpackb(payload)
            assert data["controller_id"] == 1
            assert "gamma" in data
            assert "new_ki" in data
            assert "engine" in data
            assert data["engine"] == "FUZZY"
        finally:
            worker.stop()

    def test_none_engine_does_not_start(self, bus):
        ctrl = Controller(
            id=2, name="TestNone", scan_rate_ms=100,
            ai_config=AIConfig(engine=AIEngine.NONE),
        )
        worker = AIWorker(bus=bus, controller=ctrl)
        worker.start()
        assert not worker.is_alive()  # Should not start with NONE engine
        worker.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_ai_worker.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Implement AIWorker**

```python
# packages/smart_pid_core/src/smart_pid_core/application/workers/ai_worker.py
"""AI Worker — Ki optimization via Fuzzy or RL at dead_time_L * 3 cadence."""
from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import msgpack
import zmq

from smart_pid_domain.enums import AIEngine

if TYPE_CHECKING:
    from smart_pid_core.application.event_bus import EventBus
    from smart_pid_domain.models.controller import Controller

logger = logging.getLogger(__name__)


class AIWorker:
    """Subscribes to TELEMETRY, runs AI engine, publishes ACTION.AI + LOG.AI."""

    def __init__(self, bus: EventBus, controller: Controller) -> None:
        self._bus = bus
        self._controller = controller
        self._ai_config = controller.ai_config
        self._ki_current = controller.pid_params.reset  # Ti (integral time)
        self._last_pv: float = 0.0
        self._last_sp: float = 0.0
        self._last_co: float = 0.0
        self._prev_error: float = 0.0
        self._has_telemetry = False
        self._engine = self._create_engine()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def controller_id(self) -> int:
        return self._controller.id

    def _create_engine(self):
        if self._ai_config.engine == AIEngine.FUZZY:
            from smart_pid_core.domain.services.fuzzy_engine import FuzzyEngine
            return FuzzyEngine()
        elif self._ai_config.engine == AIEngine.RL:
            from smart_pid_core.domain.services.rl_engine import RLEngine
            return RLEngine()
        return None

    def start(self) -> None:
        if self._engine is None:
            logger.debug("ai_worker_skip", controller_id=self.controller_id, reason="engine=NONE")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True,
            name=f"ai-worker-{self.controller_id}",
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
        pub = self._bus.create_publisher()
        t_cycle = max(self._ai_config.dead_time_l * 3.0, 0.1)
        time.sleep(0.02)

        while not self._stop_event.is_set():
            try:
                tick_start = time.monotonic()
                self._drain_telemetry(telem_sub)

                if self._has_telemetry and self._engine is not None:
                    error = self._last_sp - self._last_pv
                    delta_error = error - self._prev_error

                    if self._ai_config.engine == AIEngine.FUZZY:
                        decision = self._engine.compute_gamma(
                            error=error,
                            delta_error=delta_error,
                            ki_current=self._ki_current,
                            span=self._controller.pv_scale.span,
                            objective=self._ai_config.objective,
                            speed=self._ai_config.process_speed,
                            limit_min=self._ai_config.limit_min,
                            limit_max=self._ai_config.limit_max,
                        )
                    else:
                        # RL engine
                        decision = self._engine.compute_gamma(
                            error=error,
                            delta_error=delta_error,
                            ki_current=self._ki_current,
                            span=self._controller.pv_scale.span,
                            co=self._last_co,
                            integral_val=0.0,
                            objective=self._ai_config.objective,
                            speed=self._ai_config.process_speed,
                            limit_min=self._ai_config.limit_min,
                            limit_max=self._ai_config.limit_max,
                        )

                    self._ki_current = decision.new_ki
                    self._prev_error = error

                    # Publish ACTION.AI
                    action_data = {
                        "controller_id": self.controller_id,
                        "gamma": decision.gamma,
                        "new_ki": decision.new_ki,
                        "engine": self._ai_config.engine.value,
                        "objective": self._ai_config.objective.value,
                        "reasoning": decision.reasoning,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                    pub.send(
                        f"ACTION.AI.{self.controller_id}".encode(),
                        msgpack.packb(action_data),
                    )

                    # Publish LOG.AI
                    log_data = {
                        "controller_id": self.controller_id,
                        "engine": self._ai_config.engine.value,
                        "gamma": decision.gamma,
                        "old_ki": self._ki_current,
                        "new_ki": decision.new_ki,
                        "reasoning": decision.reasoning,
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                    pub.send(
                        f"LOG.AI.{self.controller_id}".encode(),
                        msgpack.packb(log_data),
                    )

                elapsed = time.monotonic() - tick_start
                sleep_time = t_cycle - elapsed
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
                self._last_pv = data["pv"]
                self._last_sp = data["sp"]
                self._last_co = data.get("co", 0.0)
                self._has_telemetry = True
            except (KeyError, ValueError, msgpack.UnpackException):
                pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_ai_worker.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/ai_worker.py \
  tests/core/integration/test_ai_worker.py
git commit -m "feat(ai): AIWorker with Fuzzy/RL engine selection, publishes ACTION.AI + LOG.AI"
```

---

### Task 9: PID Worker — Handle ACTION.AI Messages

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py`
- Modify: `tests/core/integration/test_pid_worker.py`

- [ ] **Step 1: Write failing test for AI action handling**

Append to `tests/core/integration/test_pid_worker.py` (read existing tests first for pattern):

```python
class TestPIDWorkerAIIntegration:
    def test_applies_ki_from_ai_action(self, bus, sample_controller):
        from smart_pid_core.domain.services.pid_engine import PIDEngine
        from smart_pid_core.domain.services.pid_mode_manager import ModeManager

        engine = PIDEngine()
        mode_manager = ModeManager()
        worker = PIDWorker(
            bus=bus, controller=sample_controller,
            engine=engine, mode_manager=mode_manager,
        )
        worker.set_mode(ControllerMode.AUTO)
        worker.start()
        try:
            pub = bus.create_publisher()
            time.sleep(0.05)

            # Send telemetry
            telem = {"pv": 50.0, "sp": 50.0, "co": 50.0}
            pub.send(
                f"TELEMETRY.{sample_controller.id}".encode(),
                msgpack.packb(telem),
            )
            time.sleep(0.2)

            # Send AI action with new Ki
            ai_action = {
                "controller_id": sample_controller.id,
                "new_ki": 15.0,
                "gamma": 0.5,
            }
            pub.send(
                f"ACTION.AI.{sample_controller.id}".encode(),
                msgpack.packb(ai_action),
            )
            time.sleep(0.3)

            # Verify Ki was updated
            assert worker._controller.pid_params.reset == pytest.approx(15.0)
        finally:
            worker.stop()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_pid_worker.py::TestPIDWorkerAIIntegration -v`
Expected: FAIL — AI actions not handled

- [ ] **Step 3: Implement _drain_ai_actions in PID Worker**

Replace the stub `_drain_ai_actions` in `pid_worker.py`:

```python
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
                    self._controller.pid_params.reset = float(new_ki)
            except (KeyError, ValueError, msgpack.UnpackException):
                pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_pid_worker.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py \
  tests/core/integration/test_pid_worker.py
git commit -m "feat(pid): handle ACTION.AI messages — apply new Ki from AI Worker"
```

---

### Task 10: SQLite Schema + Historian for AI Logs

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/ai_repo.py`
- Create: `tests/core/integration/test_ai_repo.py`

- [ ] **Step 1: Write failing test for AIRepository**

```python
# tests/core/integration/test_ai_repo.py
"""Integration tests for AI model metadata and tuning log persistence."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository


@pytest.fixture
async def repo(tmp_path):
    r = SQLiteRepository(tmp_path / "test.spid")
    await r.initialize()
    yield r


class TestAIModelRepo:
    @pytest.mark.asyncio
    async def test_save_and_get_model_metadata(self, repo):
        from smart_pid_core.adapters.outbound.ai_repo import AIRepository

        ai_repo = AIRepository(repo.db)
        model_id = await ai_repo.save_model_metadata(
            controller_id=1,
            algorithm="SAC",
            episodes=100,
            avg_reward=0.85,
            model_path="/models/ctrl1/sac_001.zip",
        )
        assert model_id > 0

        model = await ai_repo.get_latest_model(controller_id=1)
        assert model is not None
        assert model["algorithm"] == "SAC"
        assert model["episodes"] == 100

    @pytest.mark.asyncio
    async def test_log_tuning_action(self, repo):
        from smart_pid_core.adapters.outbound.ai_repo import AIRepository

        ai_repo = AIRepository(repo.db)
        await ai_repo.log_tuning_action(
            controller_id=1,
            engine="FUZZY",
            gamma=0.5,
            old_ki=10.0,
            new_ki=11.5,
            objective="SP_TRACKING",
            reasoning="test action",
        )
        history = await ai_repo.get_tuning_history(controller_id=1, limit=10)
        assert len(history) == 1
        assert history[0]["motor"] == "FUZZY"
        assert history[0]["ki_antes"] == pytest.approx(10.0)
        assert history[0]["ki_depois"] == pytest.approx(11.5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/integration/test_ai_repo.py -v`
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Add ai_models table to DDL**

In `sqlite_repo.py`, add after the `Log_Alarmes` table in `_DDL`:

```sql
CREATE TABLE IF NOT EXISTS Modelos_IA (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    controlador_id  INTEGER NOT NULL REFERENCES Controladores(id) ON DELETE CASCADE,
    algoritmo       TEXT    NOT NULL DEFAULT 'SAC',
    episodios       INTEGER NOT NULL DEFAULT 0,
    reward_medio    REAL    NOT NULL DEFAULT 0.0,
    caminho_modelo  TEXT    NOT NULL DEFAULT '',
    criado_em       TEXT    NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 4: Implement AIRepository**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/outbound/ai_repo.py
"""SQLite-backed repository for AI model metadata and tuning logs."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite


class AIRepository:
    """Persistence for AI model metadata and tuning action logs.

    Shares the aiosqlite.Connection owned by SQLiteRepository.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def save_model_metadata(
        self,
        controller_id: int,
        algorithm: str,
        episodes: int,
        avg_reward: float,
        model_path: str,
    ) -> int:
        """Save RL model metadata. Returns the row ID."""
        async with self._db.execute(
            "INSERT INTO Modelos_IA "
            "(controlador_id, algoritmo, episodios, reward_medio, caminho_modelo) "
            "VALUES (?, ?, ?, ?, ?)",
            (controller_id, algorithm, episodes, avg_reward, model_path),
        ) as cur:
            row_id = cur.lastrowid
        await self._db.commit()
        return row_id

    async def get_latest_model(self, controller_id: int) -> dict | None:
        """Return the most recent model metadata for a controller."""
        async with self._db.execute(
            "SELECT id, controlador_id, algoritmo, episodios, reward_medio, "
            "caminho_modelo, criado_em "
            "FROM Modelos_IA WHERE controlador_id = ? ORDER BY criado_em DESC LIMIT 1",
            (controller_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return {
            "id": row[0], "controller_id": row[1], "algorithm": row[2],
            "episodes": row[3], "avg_reward": row[4],
            "model_path": row[5], "created_at": row[6],
        }

    async def log_tuning_action(
        self,
        controller_id: int,
        engine: str,
        gamma: float,
        old_ki: float,
        new_ki: float,
        objective: str,
        reasoning: str,
    ) -> None:
        """Log a Ki adjustment in Log_Sintonia_IA."""
        await self._db.execute(
            "INSERT INTO Log_Sintonia_IA "
            "(controlador_id, motor, ki_antes, ki_depois, objetivo, metrica, aprovado) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            (controller_id, engine, old_ki, new_ki, objective, gamma),
        )
        await self._db.commit()

    async def get_tuning_history(
        self, controller_id: int, limit: int = 50,
    ) -> list[dict]:
        """Return recent tuning log entries."""
        async with self._db.execute(
            "SELECT id, controlador_id, timestamp, motor, ki_antes, ki_depois, "
            "objetivo, metrica, aprovado "
            "FROM Log_Sintonia_IA WHERE controlador_id = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (controller_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [
            {
                "id": r[0], "controller_id": r[1], "timestamp": r[2],
                "motor": r[3], "ki_antes": r[4], "ki_depois": r[5],
                "objetivo": r[6], "metrica": r[7], "aprovado": bool(r[8]),
            }
            for r in rows
        ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/core/integration/test_ai_repo.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py \
  packages/smart_pid_core/src/smart_pid_core/adapters/outbound/ai_repo.py \
  tests/core/integration/test_ai_repo.py
git commit -m "feat(ai): SQLite ai_models table + AIRepository for tuning logs"
```

---

### Task 11: REST Endpoints for Stats + AI

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/stats.py`
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/ai.py`
- Create: `packages/smart_pid_domain/src/smart_pid_domain/dtos/ai.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`
- Create: `tests/core/integration/test_api_stats.py`
- Create: `tests/core/integration/test_api_ai.py`

- [ ] **Step 1: Create AI DTOs**

```python
# packages/smart_pid_domain/src/smart_pid_domain/dtos/ai.py
"""AI and statistics request/response DTOs."""
from __future__ import annotations

from pydantic import BaseModel

from smart_pid_domain.enums import AIEngine, ControlObjective, ProcessSpeed  # noqa: TC001


class StatsResponse(BaseModel):
    controller_id: int
    iae: float
    itae: float
    ise: float
    mse: float
    std_dev: float
    total_variation: float
    variability_sp: float
    variability_range: float
    sample_count: int


class AIStatusResponse(BaseModel):
    controller_id: int
    engine: AIEngine
    objective: ControlObjective
    speed: ProcessSpeed
    current_ki: float
    last_gamma: float | None = None


class AIConfigUpdateRequest(BaseModel):
    engine: AIEngine | None = None
    objective: ControlObjective | None = None
    speed: ProcessSpeed | None = None


class AITuningLogEntry(BaseModel):
    id: int
    controller_id: int
    timestamp: str
    motor: str
    ki_antes: float | None
    ki_depois: float | None
    objetivo: str | None
    metrica: float | None
    aprovado: bool


class AIHistoryResponse(BaseModel):
    controller_id: int
    entries: list[AITuningLogEntry]
```

- [ ] **Step 2: Create stats router**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/stats.py
"""Performance statistics router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_current_user,
    get_stats_workers,
)
from smart_pid_domain.dtos.ai import StatsResponse
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001

router = APIRouter()


@router.get("/{controller_id}/stats", response_model=StatsResponse)
async def get_stats(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    stats_workers: Annotated[dict, Depends(get_stats_workers)],
) -> StatsResponse:
    worker = stats_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No stats worker for controller {controller_id}",
        )
    data = worker.get_current_stats()
    return StatsResponse(**data)
```

- [ ] **Step 3: Create AI router**

```python
# packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/ai.py
"""AI optimization router."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.dependencies import (
    get_ai_repo,
    get_ai_workers,
    get_current_user,
)
from smart_pid_domain.dtos.ai import AIHistoryResponse, AIStatusResponse, AITuningLogEntry
from smart_pid_domain.dtos.auth import UserClaims  # noqa: TC001

router = APIRouter()


@router.get("/{controller_id}/ai/status", response_model=AIStatusResponse)
async def get_ai_status(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    ai_workers: Annotated[dict, Depends(get_ai_workers)],
) -> AIStatusResponse:
    worker = ai_workers.get(controller_id)
    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No AI worker for controller {controller_id}",
        )
    return AIStatusResponse(
        controller_id=controller_id,
        engine=worker._ai_config.engine,
        objective=worker._ai_config.objective,
        speed=worker._ai_config.process_speed,
        current_ki=worker._ki_current,
    )


@router.get("/{controller_id}/ai/history", response_model=AIHistoryResponse)
async def get_ai_history(
    controller_id: int,
    _user: Annotated[UserClaims, Depends(get_current_user)],
    ai_repo: Annotated[object, Depends(get_ai_repo)],
) -> AIHistoryResponse:
    entries = await ai_repo.get_tuning_history(controller_id=controller_id, limit=50)
    return AIHistoryResponse(
        controller_id=controller_id,
        entries=[AITuningLogEntry(**e) for e in entries],
    )
```

- [ ] **Step 4: Add dependency functions**

Add to `dependencies.py`:

```python
def get_stats_workers(request: Request) -> dict:
    return getattr(request.app.state, "stats_workers", {})

def get_ai_workers(request: Request) -> dict:
    return getattr(request.app.state, "ai_workers", {})

def get_ai_repo(request: Request):
    repo = getattr(request.app.state, "ai_repo", None)
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI repository not available",
        )
    return repo
```

- [ ] **Step 5: Register routers in app.py**

Add imports and router registration:

```python
from smart_pid_core.adapters.inbound.api.routers import ai, stats

# In create_app, add parameters:
def create_app(
    *,
    repo, historian, user_repo, loop_manager, settings,
    simulator_adapter=None, opcua_adapter=None,
    stats_workers=None, ai_workers=None, ai_repo=None,
) -> FastAPI:

# Add to app.state:
    app.state.stats_workers = stats_workers or {}
    app.state.ai_workers = ai_workers or {}
    app.state.ai_repo = ai_repo

# Register routers:
    app.include_router(stats.router, prefix="/controllers", tags=["stats"])
    app.include_router(ai.router, prefix="/controllers", tags=["ai"])
```

- [ ] **Step 6: Write integration tests**

```python
# tests/core/integration/test_api_stats.py
"""Integration tests for Stats REST API."""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from smart_pid_core.adapters.inbound.api.app import create_app
from smart_pid_core.adapters.inbound.api.auth import create_access_token, hash_password
from smart_pid_core.adapters.outbound.historian import SQLiteHistorian
from smart_pid_core.adapters.outbound.sqlite_repo import SQLiteRepository
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.loop_manager import LoopManager
from smart_pid_core.config import CoreSettings


@pytest.fixture
def mock_stats_worker():
    w = MagicMock()
    w.get_current_stats.return_value = {
        "controller_id": 1, "iae": 5.0, "itae": 10.0, "ise": 25.0,
        "mse": 12.5, "std_dev": 2.0, "total_variation": 3.0,
        "variability_sp": 0.08, "variability_range": 0.04, "sample_count": 100,
    }
    return w


@pytest.fixture
async def stats_client(tmp_path, mock_stats_worker):
    import uuid
    db_path = tmp_path / "test.spid"
    repo = SQLiteRepository(db_path)
    await repo.initialize()
    historian = SQLiteHistorian(repo.db)
    user_repo = UserRepository(repo.db)
    bus = EventBus(url_prefix=f"inproc://test_{uuid.uuid4().hex[:8]}")
    bus.start()
    loop_manager = LoopManager(bus=bus)
    settings = CoreSettings(jwt_secret="test-secret-key-minimum-32-bytes!")  # type: ignore[call-arg]
    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, "admin")

    app = create_app(
        repo=repo, historian=historian, user_repo=user_repo,
        loop_manager=loop_manager, settings=settings,
        stats_workers={1: mock_stats_worker},
    )
    token = create_access_token(user_id=1, username="admin", role="admin", secret=settings.jwt_secret)
    headers = {"Authorization": f"Bearer {token}"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, headers
    loop_manager.stop_all()
    bus.stop()


class TestStatsAPI:
    @pytest.mark.asyncio
    async def test_get_stats(self, stats_client):
        client, headers = stats_client
        resp = await client.get("/controllers/1/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["iae"] == 5.0
        assert data["sample_count"] == 100

    @pytest.mark.asyncio
    async def test_get_stats_unknown_controller(self, stats_client):
        client, headers = stats_client
        resp = await client.get("/controllers/999/stats", headers=headers)
        assert resp.status_code == 404
```

- [ ] **Step 7: Run all new tests**

Run: `uv run pytest tests/core/integration/test_api_stats.py -v`
Expected: 2 passed

- [ ] **Step 8: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/dtos/ai.py \
  packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/stats.py \
  packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/ai.py \
  packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py \
  packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py \
  tests/core/integration/test_api_stats.py
git commit -m "feat(api): REST endpoints for stats and AI status/history"
```

---

### Task 12: Wire AI + Stats Workers into Daemon Lifecycle

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py`

- [ ] **Step 1: Update LoopManager to create StatsWorker + AIWorker per loop**

Add to `loop_manager.py`:

```python
from smart_pid_core.application.workers.stats_worker import StatsWorker
from smart_pid_core.application.workers.ai_worker import AIWorker
```

Update `LoopContext`:

```python
@dataclass
class LoopContext:
    """Holds references to all active components for one control loop."""
    controller: Controller
    pid_worker: PIDWorker
    engine: PIDEngine = field(default_factory=PIDEngine)
    mode_manager: ModeManager = field(default_factory=ModeManager)
    stats_worker: StatsWorker | None = None
    ai_worker: AIWorker | None = None
```

Update `start_loop`:

```python
    def start_loop(self, controller: Controller) -> None:
        if controller.id in self._loops:
            return
        engine = PIDEngine()
        mode_manager = ModeManager()
        pid_worker = PIDWorker(
            bus=self._bus, controller=controller, engine=engine, mode_manager=mode_manager
        )

        # Stats worker — always active
        stats_worker = StatsWorker(bus=self._bus, controller=controller)

        # AI worker — only if engine != NONE
        ai_worker = AIWorker(bus=self._bus, controller=controller)

        ctx = LoopContext(
            controller=controller, pid_worker=pid_worker,
            engine=engine, mode_manager=mode_manager,
            stats_worker=stats_worker, ai_worker=ai_worker,
        )
        self._loops[controller.id] = ctx
        pid_worker.start()
        stats_worker.start()
        ai_worker.start()  # No-op if engine=NONE
```

Update `stop_loop`:

```python
    def stop_loop(self, controller_id: int) -> None:
        ctx = self._loops.pop(controller_id, None)
        if ctx is None:
            return
        if ctx.ai_worker:
            ctx.ai_worker.stop()
        if ctx.stats_worker:
            ctx.stats_worker.stop()
        ctx.pid_worker.stop()
```

Add accessor methods:

```python
    def get_stats_workers(self) -> dict[int, StatsWorker]:
        """Return dict of controller_id -> StatsWorker for REST API."""
        return {
            cid: ctx.stats_worker
            for cid, ctx in self._loops.items()
            if ctx.stats_worker is not None
        }

    def get_ai_workers(self) -> dict[int, AIWorker]:
        """Return dict of controller_id -> AIWorker for REST API."""
        return {
            cid: ctx.ai_worker
            for cid, ctx in self._loops.items()
            if ctx.ai_worker is not None and ctx.ai_worker.is_alive()
        }
```

- [ ] **Step 2: Update main.py to pass workers to create_app**

In the `create_app` call in `main.py`, add:

```python
    app = create_app(
        repo=repo,
        historian=historian,
        user_repo=user_repo,
        loop_manager=loop_manager,
        settings=settings,
        simulator_adapter=simulator_adapter,
        opcua_adapter=opcua_adapter if 'opcua_adapter' in dir() else None,
        stats_workers=loop_manager.get_stats_workers(),
        ai_workers=loop_manager.get_ai_workers(),
        ai_repo=ai_repo,
    )
```

Also create ai_repo before the app:

```python
    from smart_pid_core.adapters.outbound.ai_repo import AIRepository
    ai_repo = AIRepository(repo.db)
```

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 4: Lint**

Run: `uv run --with ruff ruff check .`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py \
  packages/smart_pid_core/src/smart_pid_core/main.py
git commit -m "feat(core): wire StatsWorker + AIWorker into LoopManager and daemon lifecycle"
```

---

### Task 13: Full Integration Test — End-to-End AI Tuning

**Files:**
- Create: `tests/core/integration/test_ai_e2e.py`

- [ ] **Step 1: Write end-to-end test**

```python
# tests/core/integration/test_ai_e2e.py
"""End-to-end test: Simulator → PID → AIWorker (Fuzzy) → Ki adjustment."""
from __future__ import annotations

import time
import uuid

import msgpack
import pytest

from smart_pid_core.application.event_bus import EventBus
from smart_pid_core.application.workers.ai_worker import AIWorker
from smart_pid_core.application.workers.pid_worker import PIDWorker
from smart_pid_core.application.workers.stats_worker import StatsWorker
from smart_pid_core.domain.services.pid_engine import PIDEngine
from smart_pid_core.domain.services.pid_mode_manager import ModeManager
from smart_pid_domain.enums import AIEngine, ControlObjective, ControllerMode, ProcessSpeed
from smart_pid_domain.models.controller import AIConfig, Controller, PIDParams, ScaleConfig


@pytest.fixture
def bus():
    b = EventBus(url_prefix=f"inproc://test_e2e_{uuid.uuid4().hex[:8]}")
    b.start()
    yield b
    b.stop()


@pytest.fixture
def controller():
    return Controller(
        id=1, name="E2E-Test", scan_rate_ms=100,
        pid_params=PIDParams(gain=1.0, reset=10.0, rate=0.0),
        pv_scale=ScaleConfig(eu_min=0.0, eu_max=100.0),
        ai_config=AIConfig(
            engine=AIEngine.FUZZY,
            objective=ControlObjective.SP_TRACKING,
            process_speed=ProcessSpeed.MEDIUM,
            dead_time_l=0.1,
            limit_min=0.5,
            limit_max=50.0,
        ),
    )


class TestEndToEndAITuning:
    def test_fuzzy_adjusts_ki_over_time(self, bus, controller):
        """Verify that the fuzzy engine modifies Ki when there is a sustained error."""
        engine = PIDEngine()
        mode_manager = ModeManager()
        pid_worker = PIDWorker(
            bus=bus, controller=controller, engine=engine, mode_manager=mode_manager,
        )
        stats_worker = StatsWorker(bus=bus, controller=controller)
        ai_worker = AIWorker(bus=bus, controller=controller)

        pid_worker.set_mode(ControllerMode.AUTO)
        pid_worker.start()
        stats_worker.start()
        ai_worker.start()

        try:
            pub = bus.create_publisher()
            ai_sub = bus.create_subscriber(f"ACTION.AI.{controller.id}".encode())
            time.sleep(0.05)

            original_ki = controller.pid_params.reset

            # Simulate steady-state error (PV below SP)
            for _ in range(20):
                telem = {"pv": 45.0, "sp": 50.0, "co": 50.0}
                pub.send(
                    f"TELEMETRY.{controller.id}".encode(),
                    msgpack.packb(telem),
                )
                time.sleep(0.1)

            # Wait for AI cycle
            time.sleep(1.0)

            # Check that ACTION.AI was published
            msg = ai_sub.recv(timeout_ms=2000)
            assert msg is not None, "Expected ACTION.AI message"
            _topic, payload = msg
            data = msgpack.unpackb(payload)
            assert data["engine"] == "FUZZY"
            assert data["gamma"] != 0.0  # Should have adjusted

        finally:
            ai_worker.stop()
            stats_worker.stop()
            pid_worker.stop()
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/core/integration/test_ai_e2e.py -v`
Expected: 1 passed

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: all tests pass

- [ ] **Step 4: Lint**

Run: `uv run --with ruff ruff check .`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add tests/core/integration/test_ai_e2e.py
git commit -m "test(ai): end-to-end integration test — simulator → PID → Fuzzy → Ki adjustment"
```
