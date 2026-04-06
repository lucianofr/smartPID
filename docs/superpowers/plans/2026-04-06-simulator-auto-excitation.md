# Simulator Auto-Excitation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add auto SP variation and auto disturbance injection to the simulator so Fuzzy/RL tuning algorithms can be tested without manual intervention.

**Architecture:** Two independent timers per controller (accumulated seconds per tick) trigger SP or disturbance changes every `max(10 × tau1, 1.0)` seconds. All state lives in `_ControllerSim`; two new PUT endpoints configure it. The HMI adds two new groups to `SimulatorPage` with Apply buttons.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, PySide6, uv monorepo.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `packages/smart_pid_domain/src/smart_pid_domain/dtos/simulator.py` | Modify | Add `AutoSPRequest`, `AutoDisturbanceRequest`; extend `ControllerSimStatus` |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/simulator_adapter.py` | Modify | Add 9 fields to `_ControllerSim`; auto-excitation in `_tick()`; `set_auto_sp()`, `set_auto_disturbance()` |
| `packages/smart_pid_core/src/smart_pid_core/main.py` | Modify | Pass `pv_min`/`pv_max` from `ctrl.pv_scale` when registering controllers |
| `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/simulator.py` | Modify | Add `PUT /{id}/auto-sp` and `PUT /{id}/auto-disturbance` |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py` | Modify | Add `set_simulator_auto_sp()` and `set_simulator_auto_disturbance()` |
| `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py` | Modify | Add two abstract methods to `APIClientPort` |
| `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py` | Modify | Add period label, Auto SP group, Auto Disturbance group, two new signals |
| `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` | Modify | Wire two new signals to `_send_sim_auto_sp` / `_send_sim_auto_dist` |
| `tests/core/unit/test_simulator_dtos.py` | Create | DTO validation tests |
| `tests/core/unit/test_simulator_auto_excitation.py` | Create | Unit tests for adapter auto-excitation logic |
| `tests/core/integration/test_simulator_auto_endpoints.py` | Create | Integration tests for the two new endpoints |

---

## Task 1: DTOs — AutoSPRequest, AutoDisturbanceRequest, ControllerSimStatus extension ✅

## Task 2: SimulatorAdapter — auto-excitation fields, logic, and methods ✅

## Task 3: REST endpoints — PUT /{id}/auto-sp and PUT /{id}/auto-disturbance ✅

## Task 4: HMI — ApiClient and ports.py ✅

## Task 5: HMI — SimulatorPage UI groups and signals

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`

### Step 5.1: Add signals and period label

In `packages/smart_pid_hmi/src/smart_pid_hmi/pages/simulator_page.py`, add to the signals block (after `pid_mode_changed`):

```python
    auto_sp_changed = Signal(bool, float, float)     # enabled, sp_min_pct, sp_max_pct
    auto_disturbance_changed = Signal(bool, float)   # enabled, max_amplitude_pct
```

### Step 5.2: Add period label and auto-excitation groups

After `layout.addWidget(pid_group)`, add:

```python
        # --- Excitation period label ---
        self._period_label = QLabel()
        self._period_label.setStyleSheet(
            f"font-size: {theme.font_size_body}px; color: {theme.fg_secondary};"
        )
        layout.addWidget(self._period_label)
        self._update_period_label()

        # --- Auto SP Variation group ---
        auto_sp_group = QGroupBox("Auto SP Variation")
        auto_sp_layout = QVBoxLayout(auto_sp_group)

        auto_sp_enable_row = QHBoxLayout()
        self._auto_sp_enable = QCheckBox("Enable")
        self._auto_sp_enable.setObjectName("auto_sp_enable")
        auto_sp_enable_row.addWidget(self._auto_sp_enable)
        auto_sp_enable_row.addStretch()
        auto_sp_layout.addLayout(auto_sp_enable_row)

        sp_min_row = QHBoxLayout()
        sp_min_row.addWidget(QLabel("SP Min (%):"))
        self._auto_sp_min = QDoubleSpinBox()
        self._auto_sp_min.setObjectName("auto_sp_min")
        self._auto_sp_min.setRange(0.0, 100.0)
        self._auto_sp_min.setValue(30.0)
        self._auto_sp_min.setDecimals(1)
        sp_min_row.addWidget(self._auto_sp_min, stretch=1)
        auto_sp_layout.addLayout(sp_min_row)

        sp_max_row = QHBoxLayout()
        sp_max_row.addWidget(QLabel("SP Max (%):"))
        self._auto_sp_max = QDoubleSpinBox()
        self._auto_sp_max.setObjectName("auto_sp_max")
        self._auto_sp_max.setRange(0.0, 100.0)
        self._auto_sp_max.setValue(70.0)
        self._auto_sp_max.setDecimals(1)
        sp_max_row.addWidget(self._auto_sp_max, stretch=1)
        auto_sp_layout.addLayout(sp_max_row)

        auto_sp_apply = QPushButton("Apply")
        auto_sp_apply.setObjectName("auto_sp_apply")
        auto_sp_apply.clicked.connect(self._on_auto_sp_apply)
        auto_sp_layout.addWidget(auto_sp_apply)
        layout.addWidget(auto_sp_group)

        # --- Auto Disturbance group ---
        auto_dist_group = QGroupBox("Auto Disturbance")
        auto_dist_layout = QVBoxLayout(auto_dist_group)

        auto_dist_enable_row = QHBoxLayout()
        self._auto_dist_enable = QCheckBox("Enable")
        self._auto_dist_enable.setObjectName("auto_dist_enable")
        auto_dist_enable_row.addWidget(self._auto_dist_enable)
        auto_dist_enable_row.addStretch()
        auto_dist_layout.addLayout(auto_dist_enable_row)

        amp_row = QHBoxLayout()
        amp_row.addWidget(QLabel("Max Amplitude (%):"))
        self._auto_dist_amp = QDoubleSpinBox()
        self._auto_dist_amp.setObjectName("auto_dist_amp")
        self._auto_dist_amp.setRange(0.0, 100.0)
        self._auto_dist_amp.setValue(10.0)
        self._auto_dist_amp.setDecimals(1)
        amp_row.addWidget(self._auto_dist_amp, stretch=1)
        auto_dist_layout.addLayout(amp_row)

        auto_dist_apply = QPushButton("Apply")
        auto_dist_apply.setObjectName("auto_dist_apply")
        auto_dist_apply.clicked.connect(self._on_auto_dist_apply)
        auto_dist_layout.addWidget(auto_dist_apply)
        layout.addWidget(auto_dist_group)
```

Connect the tau1 spinbox to update the period label. Add this right after `self._tau1_slider = self._make_param_row(...)`:

```python
        self._tau1_slider.valueChanged.connect(self._update_period_label)
```

### Step 5.3: Add helper methods

```python
    def _update_period_label(self) -> None:
        tau1 = self._tau1_slider.value()
        period = max(10.0 * tau1, 1.0)
        self._period_label.setText(f"Excitation Period (10 \u00d7 \u03c41): {period:.1f} s")

    def _on_auto_sp_apply(self) -> None:
        lo = self._auto_sp_min.value()
        hi = self._auto_sp_max.value()
        if lo >= hi:
            return  # ignore invalid range
        self.auto_sp_changed.emit(self._auto_sp_enable.isChecked(), lo, hi)

    def _on_auto_dist_apply(self) -> None:
        self.auto_disturbance_changed.emit(
            self._auto_dist_enable.isChecked(),
            self._auto_dist_amp.value(),
        )
```

### Step 5.4: Populate auto-excitation fields from status

In the existing `populate_from_status()` method, add:

```python
        if status.auto_sp is not None:
            self._auto_sp_enable.setChecked(status.auto_sp.enabled)
            self._auto_sp_min.setValue(status.auto_sp.sp_min_pct)
            self._auto_sp_max.setValue(status.auto_sp.sp_max_pct)
        if status.auto_disturbance is not None:
            self._auto_dist_enable.setChecked(status.auto_disturbance.enabled)
            self._auto_dist_amp.setValue(status.auto_disturbance.max_amplitude_pct)
```

---

## Task 6: HMI — MainWindow wiring

**Files:**
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/main.py`

### Step 6.1: Connect signals

After `self._simulator_page.pid_mode_changed.connect(self._send_sim_pid_mode)`, add:

```python
        self._simulator_page.auto_sp_changed.connect(self._send_sim_auto_sp)
        self._simulator_page.auto_disturbance_changed.connect(self._send_sim_auto_dist)
```

### Step 6.2: Add handler methods

After `_send_sim_pid_mode()`, add:

```python
    def _send_sim_auto_sp(self, enabled: bool, sp_min_pct: float, sp_max_pct: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        self._safe_api_call(
            self._api_client.set_simulator_auto_sp, cid, enabled, sp_min_pct, sp_max_pct,
        )

    def _send_sim_auto_dist(self, enabled: bool, max_amplitude_pct: float) -> None:
        cid = self._simulator_page.current_controller_id
        if cid is None:
            return
        self._safe_api_call(
            self._api_client.set_simulator_auto_disturbance, cid, enabled, max_amplitude_pct,
        )
```
