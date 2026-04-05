# Monitor + Supervisor Mode Design

**Date:** 2026-04-05
**Status:** Approved
**Scope:** Architectural pivot — SmartPID operates as monitor and tuning optimizer for external PIDs

---

## 1. Overview

The SmartPID system shifts from executing PID control internally to **monitoring and optimizing** PID controllers running on external DCS/PLC systems. The internal PID engine code is preserved but disabled behind a configuration flag for future use.

### Operating Model

- **Read**: All process variables via OPC-UA — PV, SP, CO, Mode, Kp/Ti/Td, BKCAL_IN/BKCAL_OUT, Status/Limits (full FF/HART signal set)
- **Analyze**: Performance metrics (IAE, ITAE, ISE, variability), alarm evaluation, AI-driven tuning optimization (Fuzzy/RL)
- **Write**: Only tuning parameters (Kp, Ti, Td) back to the DCS, subject to authorization and guardrails

---

## 2. Execution Mode Flag

### Configuration

New setting in `CoreSettings` (pydantic-settings, prefix `SPID_`):

```
SPID_EXECUTION_MODE=monitor   # "monitor" (default) | "execute"
```

### Behavior by Mode

| Component       | `monitor`                              | `execute` (future)         |
|-----------------|----------------------------------------|----------------------------|
| IOWorker        | Reads telemetry only, no BKCAL write   | Reads telemetry + writes BKCAL_OUT |
| PIDWorker       | Not started                            | Started, runs compute()    |
| MonitorWorker   | Started, publishes STATUS              | Not started (PIDWorker publishes STATUS) |
| AIWorker        | Started, writes tuning to DCS          | Started, mutates PIDWorker params |
| ModeManager     | Not used                               | Used by PIDWorker          |
| Commands Router | SP/Mode/Output return 409              | Full functionality          |

### Implementation

`LoopManager.start_loop()` checks `settings.execution_mode`:
- `monitor`: starts MonitorWorker, StatsWorker, AIWorker (in supervisor mode). Skips PIDWorker.
- `execute`: current behavior — starts PIDWorker, StatsWorker, AIWorker (in internal mode).

---

## 3. MonitorWorker (New)

Replaces PIDWorker's STATUS publishing role in monitor mode.

### Responsibilities

- Subscribe to `TELEMETRY.{id}` from EventBus
- Enrich telemetry:
  - Calculate error: `error = PV.value - SP.value`
  - Detect output saturation via CO limit bits (`LimitBits.HIGH`, `LimitBits.LOW`)
  - Read external PID mode from telemetry
- Publish `STATUS.{id}` to EventBus — consumed by AlarmWorker, StatsWorker, TelemetryPublisher, HMI

### Interface

```python
class MonitorWorker(threading.Thread):
    def __init__(
        self,
        controller_id: str,
        bus_ctx: zmq.Context,
        scan_rate_ms: int,
    ) -> None: ...
```

### STATUS Message Schema

Same schema as PIDWorker currently publishes, ensuring downstream consumers (AlarmWorker, TelemetryPublisher, HMI) require zero changes:

```python
{
    "controller_id": str,
    "pv": FFSignal.to_dict(),
    "sp": FFSignal.to_dict(),
    "co": FFSignal.to_dict(),
    "bkcal_in": FFSignal.to_dict(),
    "bkcal_out": FFSignal.to_dict(),
    "error": float,
    "mode": str,          # external PID mode read from OPC-UA
    "saturated": bool,    # derived from CO limit bits
    "timestamp": float,
}
```

---

## 4. TagBindings Expansion

### New Fields

Added to the `TagBindings` model in `smart_pid_domain`:

```python
@dataclass
class TagBindings:
    # Existing
    node_id_pv: str
    node_id_sp: str
    node_id_co: str
    node_id_bkcal_in: str   # from FF signals work
    node_id_bkcal_out: str  # from FF signals work

    # New — tuning parameters (read + write)
    node_id_kp: str = ""
    node_id_ti: str = ""
    node_id_td: str = ""

    # New — external mode (read-only)
    node_id_mode: str = ""
```

Empty string means "not mapped" — all new fields are optional.

---

## 5. OPCUAAdapter Extensions

### New Methods

```python
class OPCUAAdapter:
    # Existing
    async def read_telemetry(self, controller_id: str) -> TelemetryFrame: ...
    async def write_bkcal_out(self, controller_id: str, bkcal: FFSignal) -> None: ...

    # New
    async def read_pid_params(self, controller_id: str) -> PIDParamsRead:
        """Read current Kp, Ti, Td from DCS. Returns None for unmapped tags."""

    async def write_pid_params(
        self, controller_id: str, kp: float | None, ti: float | None, td: float | None
    ) -> None:
        """Write tuning parameters to DCS. Only writes non-None values."""

    async def read_external_mode(self, controller_id: str) -> str | None:
        """Read PID mode from DCS. Returns None if node_id_mode not mapped."""
```

### PIDParamsRead (New Domain Model)

```python
@dataclass(frozen=True)
class PIDParamsRead:
    kp: float | None
    ti: float | None
    td: float | None
    timestamp: float
```

---

## 6. Tuning Write-Back

### Controller-Level Configuration

New fields on the `Controller` model:

```python
@dataclass
class Controller:
    # ... existing fields ...

    # Tuning write-back config
    tuning_write_mode: TuningWriteMode = TuningWriteMode.APPROVAL_REQUIRED
    max_tuning_change_pct: float = 10.0   # max % change per AI cycle (guardrail)
```

### TuningWriteMode Enum

```python
class TuningWriteMode(StrEnum):
    AUTO_APPLY = "auto_apply"
    APPROVAL_REQUIRED = "approval_required"
    DISABLED = "disabled"
```

### Guardrails (Always Active)

Regardless of `tuning_write_mode`, every write-back is clamped:

```
delta_kp = new_kp - current_kp
max_delta = current_kp * (max_tuning_change_pct / 100)
clamped_kp = current_kp + clamp(delta_kp, -max_delta, max_delta)
```

Same logic for Ti and Td. This prevents the AI from making large jumps in a single cycle.

### Condition: External PID Must Be in Auto

Tuning write-back is only allowed when the external PID mode (read via `node_id_mode`) is "Auto" or equivalent. If the PID is in Manual/Cascade/OOS, the write-back is suppressed and logged.

---

## 7. AIWorker Changes (Monitor Mode)

In monitor mode, AIWorker behavior changes:

| Aspect                | Current (execute mode)                  | Monitor mode                           |
|-----------------------|-----------------------------------------|----------------------------------------|
| Input                 | Subscribes to `TELEMETRY.{id}`          | Same                                   |
| Computation           | Fuzzy/RL computes new Ki                | Fuzzy/RL computes new Kp, Ti, Td (Phase 5 expansion) |
| Output (auto_apply)   | Publishes `ACTION.AI.{id}` to PIDWorker | Calls `OPCUAAdapter.write_pid_params()` |
| Output (approval)     | N/A                                     | Publishes `TUNING_RECOMMENDATION.{id}` |
| Guardrails            | `ai_limit_min/max`                      | `max_tuning_change_pct` + `ai_limit_min/max` |

### Tuning Recommendation Event (New)

```python
@dataclass(frozen=True)
class TuningRecommendation:
    id: UUID
    controller_id: str
    current_kp: float
    current_ti: float
    current_td: float
    recommended_kp: float
    recommended_ti: float
    recommended_td: float
    reason: str           # e.g. "fuzzy_sp_tracking", "rl_disturbance"
    timestamp: float
    status: TuningRecStatus = TuningRecStatus.PENDING
```

```python
class TuningRecStatus(StrEnum):
    PENDING = "pending"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"
```

---

## 8. Commands Router Changes

### Blocked Endpoints (Monitor Mode)

These endpoints return `409 Conflict` with body `{"detail": "Not available in monitor mode. PID is controlled by external DCS."}`:

- `POST /commands/setpoint`
- `POST /commands/mode`
- `POST /commands/output`

### New Endpoint

```
POST /commands/apply-tuning/{controller_id}
```

- Requires: auth (existing JWT)
- Retrieves latest pending `TuningRecommendation` for the controller
- Applies guardrails and writes to DCS via `OPCUAAdapter.write_pid_params()`
- Returns applied values and confirmation
- Returns 404 if no pending recommendation
- Returns 409 if external PID not in Auto mode

```
GET /commands/tuning-recommendations/{controller_id}
```

- Returns list of recent recommendations (pending, applied, rejected, expired)
- Supports filtering by status

---

## 9. IOWorker Changes (Monitor Mode)

In monitor mode:

- `read_telemetry()` loop: **unchanged** — continues reading PV, SP, CO, BKCAL_IN, BKCAL_OUT from OPC-UA and publishing `TELEMETRY.{id}`
- `_drain_and_write_bkcal()`: **skipped** — no subscription to `ACTION.CTRL.*`, no BKCAL_OUT write-back
- New: also reads external PID params (Kp/Ti/Td) and mode at a slower cadence (configurable, default every 10s) and includes them in telemetry or publishes separately as `PARAMS.{id}`

---

## 10. Data Flow (Monitor Mode)

```
DCS/PLC (External PID)
    |
    v  OPC-UA read (PV, SP, CO, BKCAL, Mode, Kp/Ti/Td, Status)
IOWorker
    |
    +---> TELEMETRY.{id}
    |         |
    |    +----+--------+--------+
    |    |              |        |
    |    v              v        v
    | MonitorWorker  StatsWorker DBWorker
    |    |              |
    |    v              v
    | STATUS.{id}   STATS.{id}
    |    |
    |    +-------+-------+
    |    |               |
    |    v               v
    | AlarmWorker  TelemetryPublisher --> HMI
    |
    +---> PARAMS.{id} (every 10s)
              |
              v
           AIWorker (Fuzzy/RL)
              |
              v
         tuning_write_mode?
              |
       +------+------+
       |              |
   auto_apply    approval_required
       |              |
       v              v
  write_pid_params  TUNING_RECOMMENDATION.{id}
  (with guardrails)       |
       |              HMI shows recommendation
       v              Operator clicks "Apply"
      DCS                 |
                          v
                   POST /commands/apply-tuning
                          |
                          v
                   write_pid_params (with guardrails)
                          |
                          v
                         DCS
```

---

## 11. Domain Model Changes Summary

| Model             | Change                                                        |
|-------------------|---------------------------------------------------------------|
| `TagBindings`     | Add `node_id_kp`, `node_id_ti`, `node_id_td`, `node_id_mode` |
| `Controller`      | Add `tuning_write_mode`, `max_tuning_change_pct`              |
| `CoreSettings`    | Add `execution_mode: str = "monitor"`                         |
| `TuningWriteMode` | New StrEnum                                                   |
| `TuningRecStatus` | New StrEnum                                                   |
| `PIDParamsRead`   | New frozen dataclass                                          |
| `TuningRecommendation` | New frozen dataclass                                    |

---

## 12. What Is NOT Changed

- **PIDEngine, ModeManager, PIDWorker**: Code preserved as-is. Not started in monitor mode. No deletions.
- **AlarmWorker, DBWorker, StatsWorker**: Zero changes — they consume `STATUS.{id}` and `TELEMETRY.{id}` which maintain the same schema.
- **TelemetryPublisher**: Zero changes — forwards topics as before.
- **HMI ZMQ subscriber**: Zero changes — receives same STATUS messages.
- **SQLite schema, Historian**: Zero changes.
- **FFSignal model**: Used as-is for all signal reads.

---

## 13. Testing Strategy

- **Unit**: MonitorWorker enrichment logic, guardrail clamping, TuningRecommendation lifecycle
- **Unit**: LoopManager mode branching (monitor vs execute)
- **Unit**: Commands router returns 409 in monitor mode
- **Integration**: IOWorker reads telemetry without writing BKCAL in monitor mode
- **Integration**: AIWorker auto-apply flow end-to-end (read params -> compute -> write with guardrails)
- **Integration**: Approval flow (recommend -> API approve -> write)
- **Integration**: Guardrail enforcement (AI recommends large change, verify clamping)
- **Integration**: External mode gate (suppress write when PID not in Auto)
