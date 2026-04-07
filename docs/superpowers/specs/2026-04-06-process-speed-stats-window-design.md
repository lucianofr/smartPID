# Process Speed as Mandatory Controller Field with Performance Windows

**Date:** 2026-04-06
**Status:** Draft
**Scope:** Domain, Core (StatsWorker, AI engines), HMI (ControllerDialog), API/DTOs

---

## Summary

Promote `ProcessSpeed` from an AI-only configuration to a **mandatory** Controller-level field that determines the sliding window for performance statistics calculation. Expand from 3 to 4 categories aligned with real-world process dynamics.

## Motivation

Performance indicators (IAE, ITAE, ISE, MSE, std_dev, TV, variability) must be computed over a time window that matches the process dynamics. A flow loop (seconds) and a furnace temperature loop (hours) need fundamentally different evaluation windows. Today, `StatsWorker` uses a hardcoded `window_size=1800` samples regardless of process type, and `ProcessSpeed` only lives inside `AIConfig`.

## Design

### 1. Enum — `ProcessSpeed` (smart_pid_domain/enums.py)

Expand from 3 members (SLOW, MEDIUM, FAST) to 4 members with embedded metadata via properties:

| Member | `stats_window_s` | `ai_period_s` | `speed_factor` | UI Label |
|---|---|---|---|---|
| `ULTRA_FAST` | 5 | 30 | 0.02 | Ultra Fast — Motors / Converters |
| `FAST` | 60 | 180 (3 min) | 0.05 | Fast — Flow / Pressure |
| `MEDIUM` | 1200 (20 min) | 1800 (30 min) | 0.15 | Medium — Level / Heat Exchangers |
| `SLOW` | 7200 (2 h) | 14400 (4 h) | 0.30 | Slow — Furnaces / Distillation |

Properties on the enum:
- `stats_window_s -> int` — sliding window for performance statistics (seconds)
- `ai_period_s -> int` — AI optimization cycle period (seconds)
- `speed_factor -> float` — AI tuning aggressiveness factor
- `label -> str` — human-readable description for UI

Implementation approach: properties with lookup dicts internal to the enum class, ensuring every member must have all metadata defined.

### 2. Model — `Controller` (smart_pid_domain/models/controller.py)

- **Add** `process_speed: ProcessSpeed = ProcessSpeed.MEDIUM` as a direct field on `Controller`
- **Remove** `process_speed` from `AIConfig`

`AIConfig` retains: `engine`, `objective`, `dead_time_l`, `limit_min`, `limit_max`.

### 3. StatsWorker — Dynamic Window (smart_pid_core/application/workers/stats_worker.py)

Replace hardcoded `window_size=1800` with computation from controller config:

```python
window_seconds = controller.process_speed.stats_window_s
window_size = window_seconds * 1000 // controller.scan_rate_ms
```

Examples:
- FAST loop, scan_rate=1000ms → window_size = 60
- MEDIUM loop, scan_rate=1000ms → window_size = 1200
- SLOW loop, scan_rate=500ms → window_size = 14400

Stats are published every 5 seconds (fixed interval), regardless of process speed: `publish_interval = max(1, 5000 // scan_rate_ms)`. The AI Worker runs independently on its own timer defined by `ProcessSpeed.ai_period_s`.

### 4. AI Engines — Fuzzy & RL (smart_pid_core/domain/services/)

Both engines currently read `controller.ai_config.process_speed` to derive `speed_factor`. Change to read `controller.process_speed.speed_factor` directly.

Affected files:
- `fuzzy_engine.py`
- `rl_engine.py`

### 5. ControllerDialog — HMI (smart_pid_hmi/widgets/controller_dialog.py)

- **Move** the Process Speed combo from the "AI Configuration" tab to the "General" tab (below Scan Rate — it is fundamental loop configuration, not AI-specific)
- Populate combo with descriptive labels: "Ultra Fast — Motors / Converters", etc.
- Map label ↔ enum value for storage
- Default selection: MEDIUM
- Field is always present and always has a value (no empty option)

### 6. DTOs and API

**DTOs** (`smart_pid_domain/dtos/controllers.py`):
- Add `process_speed: ProcessSpeed` to `ControllerCreate` and `ControllerUpdate` (root level)
- Remove `process_speed` from `AIConfigDTO`

**Router** (`smart_pid_core/adapters/inbound/api/routers/controllers.py`):
- `_body_to_controller()`: read `process_speed` from request body root
- `_to_response()`: include `process_speed` at response root

### 7. SQLite Repository

The `process_speed` column already exists in the controllers table (stored as enum string value). The repository mapping needs to read/write from `Controller.process_speed` instead of `Controller.ai_config.process_speed`. No schema migration needed — just the mapping code in `sqlite_repo.py`.

### 8. Existing Tests

Tests that construct `AIConfig(process_speed=...)` need updating to use `Controller(process_speed=...)` instead. Tests that construct `ProcessSpeed.FAST` etc. continue working (member still exists). Tests referencing `ProcessSpeed.SLOW` with old semantics (3-value enum) need the new ULTRA_FAST member acknowledged where relevant.

## Out of Scope

- User-adjustable window override per loop (future enhancement)
- Different window sizes for different metrics (all metrics use the same window)
- Migration script for existing DB rows (existing rows default to MEDIUM via the enum default)
