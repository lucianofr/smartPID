# Design Spec: Foundation Fieldbus Signal Semantics & BKCAL Integration

**Date:** 2026-04-04
**Status:** Draft
**Scope:** Domain models, PID engine, mode manager, workers, OPC-UA adapter, events, API

---

## 1. Objective

Integrate Foundation Fieldbus (FF) signal semantics into the smartPID system so that every
process signal (PV, SP, CO, BKCAL_IN, BKCAL_OUT) carries value, quality status, and timestamp
as a single unit — matching the OPC-UA `DataValue` structure.

This enables:
- **Anti-windup direcional** based on downstream block saturation (limit bits)
- **Bumpless cascade handshake** (NI → IR → IA → GOOD_CASCADE)
- **Stale data detection** via timestamp watchdog
- **Correct IMAN tracking** with integral forcing (spec section 5.2)

Reference: `docs/spec_ff.md`

---

## 2. Domain Models (smart_pid_domain)

### 2.1. New Enums (`enums.py`)

```python
class SignalSeverity(StrEnum):
    """OPC-UA StatusCode severity bits 31:30."""
    GOOD = "GOOD"           # 0x00
    UNCERTAIN = "UNCERTAIN"  # 0x01
    BAD = "BAD"             # 0x02

class LimitBits(StrEnum):
    """OPC-UA StatusCode limit bits 9:8 — used for directional anti-windup."""
    NONE = "NONE"               # 0x00 — integration free
    LOW_LIMITED = "LOW_LIMITED"  # 0x01 — block negative integration
    HIGH_LIMITED = "HIGH_LIMITED"  # 0x02 — block positive integration
    CONSTANT = "CONSTANT"       # 0x03 — value locked, block all integration

class InitSubStatus(StrEnum):
    """FF handshake sub-status for cascade initialization."""
    NONE = "NONE"                # Normal operation, no handshake
    NI = "NI"                    # Not Invited — slave left cascade
    IR = "IR"                    # Initialization Request — slave requesting alignment
    IA = "IA"                    # Initialization Acknowledge — master confirms tracking
    GOOD_CASCADE = "GOOD_CASCADE"  # Handshake complete, cascade active
```

The existing `SignalStatus` enum is **replaced** by `SignalSeverity`. All references in the
codebase that use `SignalStatus` must migrate to `SignalSeverity` (same values: GOOD, BAD,
UNCERTAIN — just renamed for clarity).

### 2.2. New Value Objects (`models/signal.py`)

```python
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

    Mirrors the OPC-UA DataValue structure and Foundation Fieldbus signal semantics.
    Every signal in the PID engine (PV, SP, CO, BKCAL_IN, BKCAL_OUT) uses this type.
    """
    value: float
    status: FFSignalStatus = field(default_factory=FFSignalStatus)
    timestamp: datetime | None = None

    @staticmethod
    def good(value: float, ts: datetime | None = None) -> "FFSignal":
        """Create a signal with GOOD status."""
        return FFSignal(value=value, status=FFSignalStatus(), timestamp=ts)

    @staticmethod
    def bad(value: float = 0.0, ts: datetime | None = None) -> "FFSignal":
        """Create a signal with BAD status."""
        return FFSignal(
            value=value,
            status=FFSignalStatus(severity=SignalSeverity.BAD),
            timestamp=ts,
        )

    @staticmethod
    def with_limits(value: float, limit_bits: LimitBits, ts: datetime | None = None) -> "FFSignal":
        """Create a GOOD signal with specific limit bits."""
        return FFSignal(
            value=value,
            status=FFSignalStatus(limit_bits=limit_bits),
            timestamp=ts,
        )
```

### 2.3. Changes to Existing Models

**`TelemetryFrame`** (`models/telemetry.py`):

```python
@dataclass(frozen=True)
class TelemetryFrame:
    controller_id: int
    pv: FFSignal          # was: float
    sp: FFSignal          # was: float
    co: FFSignal          # was: float
    bkcal_in: FFSignal    # NEW — feedback from downstream block
    integral_val: float   # kept as float — internal state, not a process signal
    timestamp: datetime
    # REMOVED: status: SignalStatus — each signal now carries its own status
```

**`ControlAction`** (`models/telemetry.py`):

```python
@dataclass(frozen=True)
class ControlAction:
    controller_id: int
    co: FFSignal          # was: float
    bkcal_out: FFSignal   # NEW — backcalculation output to upstream block
    integral_val: float
    timestamp: datetime
```

**`TagBindings`** (`models/controller.py`):

```python
@dataclass
class TagBindings:
    node_id_pv: str = ""
    node_id_sp: str = ""
    node_id_co: str = ""
    node_id_integral: str = ""
    node_id_bkcal_in: str = ""   # NEW
    node_id_bkcal_out: str = ""  # NEW
```

---

## 3. PID Engine Changes

### 3.1. New Signature

```python
class PIDEngine:
    def compute(
        self,
        params: PIDParams,
        state: PIDState,
        pv: FFSignal,
        sp: FFSignal,
        bkcal_in: FFSignal,
        dt: float,
        out_limits: tuple[float, float],
        direct_acting: bool,
        arw_limits: tuple[float, float],
    ) -> PIDResult:
```

The engine extracts `pv.value` and `sp.value` for the calculation, but uses `bkcal_in.status`
for anti-windup decisions and `bkcal_in.value` for IMAN tracking.

### 3.2. Directional Anti-Windup (FF-based)

Two anti-windup mechanisms coexist — the **most restrictive wins**:

1. **Local ARW** (existing): based on output hitting `arw_hi_lim` / `arw_lo_lim`
2. **Downstream ARW** (new): based on `bkcal_in.status.limit_bits`

```python
# After computing integral increment
increment = gain * (dt / ti) * error

# Downstream anti-windup (FF limit bits from BKCAL_IN)
if bkcal_in.status.is_high_limited and increment > 0:
    increment = 0.0  # downstream saturated high — block positive integration
elif bkcal_in.status.is_low_limited and increment < 0:
    increment = 0.0  # downstream saturated low — block negative integration
elif bkcal_in.status.is_constant:
    increment = 0.0  # downstream locked — block all integration

# Local ARW (existing logic) still applies after this
```

### 3.3. BKCAL_OUT Generation

The PID engine generates `bkcal_out` as part of `PIDResult`:

| Mode | `bkcal_out.value` | `bkcal_out.status` |
|------|--------------------|--------------------|
| AUTO, CAS, RCAS | `cv` (computed output) | GOOD + limit bits reflecting output saturation |
| MAN | manual output value | GOOD |
| IMAN (tracking) | `bkcal_in.value` | severity=GOOD, sub_status=IA |
| OOS, LO | last known output | severity=BAD, sub_status=NI |

Limit bits on BKCAL_OUT in active modes:
- Output at `out_hi_lim` → `HIGH_LIMITED`
- Output at `out_lo_lim` → `LOW_LIMITED`
- Otherwise → `NONE`

### 3.4. PIDResult Expansion

```python
@dataclass(frozen=True)
class PIDResult:
    cv: float
    delta_cv: float
    error: float
    bkcal_out: FFSignal   # NEW
    new_state: PIDState
```

### 3.5. IMAN Tracking — Integral Forcing (spec section 5.2)

When the PID is in IMAN mode and `bkcal_in.sub_status == IR`, the normal PID calculation is
**skipped**. Instead, the integral accumulator (CV in velocity form) is forced directly:

```python
# Velocity form: CV is the accumulated output. Force it to match bkcal_in.
# The proportional and derivative terms are zero during tracking (error is not acted upon).
state.cv = bkcal_in.value
```

Since the velocity-form PID accumulates delta_cv into `state.cv`, forcing `state.cv` directly
to `bkcal_in.value` achieves the same result as the positional-form integral forcing
(`integral_forced = bkcal_in.value - Kp*e - D - bias`), but is simpler and avoids
introducing a bias term that does not exist in the current engine.

The output CV equals `bkcal_in.value` exactly. The output is emitted with
`sub_status = IA` to acknowledge initialization to the downstream block.

Additionally, `state.error_prev`, `state.pv_prev`, and `state.pv_prev2` are updated to
current values to prevent derivative kick on the first active cycle after tracking.

### 3.6. Stale Data Detection

New field in `PIDState`: `last_bkcal_timestamp: datetime | None`.

Each cycle, if BKCAL_IN has a timestamp and `now - bkcal_in.timestamp > 3 * scan_rate_ms`,
the signal is forced to `BAD` internally. This triggers cascade break (mode → IMAN) per
spec section 6.4.

---

## 4. Mode Manager Changes

### 4.1. BlockStatus Expansion

```python
@dataclass
class BlockStatus:
    pv: FFSignal              # was: pv_status: SignalStatus
    bkcal_in: FFSignal        # NEW
    tracking_active: bool
    shed_timeout_expired: bool
    simulate_active: bool
```

### 4.2. Cascade Handshake Evaluation

New method on `ModeManager`:

```python
@dataclass(frozen=True)
class CascadeAction:
    force_mode: ControllerMode | None  # mode to force, or None if no change
    tracking_target: float | None       # value to track in IMAN, or None
    emit_sub_status: InitSubStatus     # sub_status for BKCAL_OUT

def evaluate_cascade_handshake(
    self,
    current_mode: ControllerMode,
    bkcal_in: FFSignal,
) -> CascadeAction:
```

Decision table:

| `bkcal_in` condition | Current mode | Action |
|----------------------|--------------|--------|
| severity=BAD or sub_status=NI | CAS, RCAS | force → IMAN, emit NI |
| sub_status=IR, severity=GOOD/UNCERTAIN | IMAN | stay IMAN, track bkcal_in.value, emit IA |
| sub_status=GOOD_CASCADE, severity=GOOD | IMAN | force → CAS, requires bumpless, emit NONE |
| sub_status=NONE, severity=GOOD | AUTO | no action (normal operation, no cascade) |
| severity=BAD | IMAN (already) | stay IMAN, emit NI |

### 4.3. Forced Transition Priority (updated)

```
1. tracking_active           → force LO
2. pv.status.is_bad          → force MAN
3. bkcal_in stale (timeout)  → force IMAN (cascade break)
4. bkcal_in NI or BAD        → force IMAN (slave left cascade)
5. shed_timeout_expired      → force configured shed_mode
```

### 4.4. Bumpless Transfer on IMAN → CAS

When handshake completes (GOOD_CASCADE received), `ModeTransition.requires_bumpless = True`.
The PIDWorker calls `PIDEngine.bumpless_transfer()` with `cv = bkcal_in.value` so that the
transition has zero error.

---

## 5. Workers

### 5.1. IOWorker

Changes to `_run()` loop:

- Read full OPC-UA `DataValue` (value + StatusCode + SourceTimestamp) for each node
- Decode StatusCode using bit masks:
  - Severity: `(status_code & 0xC0000000) >> 30`
  - Limit bits: `(status_code & 0x00000300) >> 8`
- Map sub-status from InfoBits or dedicated handshake tags (configurable per controller)
- Build `TelemetryFrame` with `FFSignal` objects
- Read `bkcal_in` from `node_id_bkcal_in` node

New responsibility:
- After PIDWorker publishes `ACTION.CTRL.{cid}`, IOWorker writes `bkcal_out` to the
  `node_id_bkcal_out` OPC-UA node, encoding the StatusCode back with severity + limit bits +
  sub_status

### 5.2. PIDWorker

Changes to main loop:

```
1. _drain_telemetry()  → receives FFSignal fields (pv, sp, co, bkcal_in)
2. _drain_ai_actions() → unchanged
3. evaluate_cascade_handshake(mode, bkcal_in) → get CascadeAction
4. If CascadeAction.force_mode → apply mode transition
5. If mode is IMAN and bkcal_in.sub_status == IR:
     → execute integral forcing (tracking), skip normal PID
6. If mode is AUTO/CAS/RCAS:
     → normal PID compute with bkcal_in for directional anti-windup
7. Build bkcal_out FFSignal based on current mode and output state
8. Publish ACTION.CTRL.{cid} with co (FFSignal) and bkcal_out (FFSignal)
9. Publish STATUS.{cid} with all FFSignal fields
```

### 5.3. Stale Data Watchdog

In PIDWorker, each cycle before computation:

```python
if bkcal_in.timestamp is not None:
    age = (now - bkcal_in.timestamp).total_seconds()
    if age > 3 * (scan_rate_ms / 1000):
        bkcal_in = FFSignal.bad(bkcal_in.value, bkcal_in.timestamp)
        # This will trigger cascade break via evaluate_cascade_handshake
```

Same check applies to PV — if `pv.timestamp` is stale, force severity to BAD.

---

## 6. OPC-UA Adapter Changes

### 6.1. OPCUAAdapter (Client)

**`register_controller()`** — accepts two additional node IDs:
- `node_id_bkcal_in: str` — node to read BKCAL feedback from downstream
- `node_id_bkcal_out: str` — node to write BKCAL output for upstream

**`read_telemetry(cid) -> TelemetryFrame`** — changed from reading `float` values to reading
full `DataValue`:
- Uses `asyncua.Node.read_data_value()` instead of `read_value()`
- Decodes StatusCode via bit masks into `FFSignalStatus`
- Extracts `SourceTimestamp` into `FFSignal.timestamp`
- Includes `bkcal_in` read from the registered node

**New: `write_bkcal_out(cid, signal: FFSignal)`** — writes value and encodes StatusCode:
- Severity → bits 31:30
- Limit bits → bits 9:8
- Sub-status (IA, NI, etc.) → via InfoBits or dedicated tag (configurable)

**StatusCode decoding helper** (private method or utility):

```python
def _decode_status(self, status_code: int) -> FFSignalStatus:
    severity_bits = (status_code & 0xC0000000) >> 30
    severity = {0: SignalSeverity.GOOD, 1: SignalSeverity.UNCERTAIN, 2: SignalSeverity.BAD}
    limit = (status_code & 0x00000300) >> 8
    limit_bits = {0: LimitBits.NONE, 1: LimitBits.LOW_LIMITED, 2: LimitBits.HIGH_LIMITED, 3: LimitBits.CONSTANT}
    return FFSignalStatus(severity=severity[severity_bits], limit_bits=limit_bits[limit])

def _encode_status(self, status: FFSignalStatus) -> int:
    severity_map = {SignalSeverity.GOOD: 0, SignalSeverity.UNCERTAIN: 1, SignalSeverity.BAD: 2}
    limit_map = {LimitBits.NONE: 0, LimitBits.LOW_LIMITED: 1, LimitBits.HIGH_LIMITED: 2, LimitBits.CONSTANT: 3}
    return (severity_map[status.severity] << 30) | (limit_map[status.limit_bits] << 8)
```

### 6.2. OPCUAServer (Simulator)

- Add `BKCAL_IN` and `BKCAL_OUT` variables per controller folder (Float value + UInt32 status)
- `_WriteHandler` handles writes to BKCAL_IN (from external master)
- SimulatorAdapter updates BKCAL_OUT values reflecting simulated valve position and limits

### 6.3. Sub-Status Transport

The FF sub-status (NI, IR, IA, GOOD_CASCADE) does not map directly to standard OPC-UA
StatusCode bits. Two transport options (configurable per controller):

1. **Dedicated tags**: separate OPC-UA nodes `BKCAL_IN.SubStatus` and `BKCAL_OUT.SubStatus`
   as UInt32 or String. Simpler, explicit.
2. **InfoBits encoding**: pack sub-status into unused StatusCode bits (bits 15:10).
   More compact, closer to FF spec.

Default: **dedicated tags** (option 1) for clarity and interoperability. The
`TagBindings` model gains optional fields `node_id_bkcal_in_substatus` and
`node_id_bkcal_out_substatus`. When not configured, sub-status defaults to `NONE`.

---

## 7. Events

### 7.1. Modified Events

**`ControlActionComputed`**:
```python
@dataclass(frozen=True)
class ControlActionComputed:
    event_id: UUID
    controller_id: int
    co: float             # kept for backward compat — extracted from FFSignal
    integral_val: float
    delta_cv: float
    bkcal_out_value: float      # NEW
    bkcal_out_severity: str     # NEW
    bkcal_out_limit_bits: str   # NEW
    bkcal_out_sub_status: str   # NEW
    timestamp: datetime
```

### 7.2. New Event

```python
@dataclass(frozen=True)
class CascadeHandshakeChanged:
    event_id: UUID
    controller_id: int
    old_sub_status: InitSubStatus
    new_sub_status: InitSubStatus
    trigger: str            # e.g. "bkcal_in_bad", "ir_received", "good_cascade"
    timestamp: datetime
```

Published by PIDWorker when handshake state transitions occur. Subscribed by DBWorker
(historian) and AlarmWorker (for cascade fault alarms).

---

## 8. API Changes

### 8.1. TagBindings in Controller CRUD

`POST /controllers` and `PUT /controllers/{id}` accept the new fields:
- `node_id_bkcal_in: str` (optional, default "")
- `node_id_bkcal_out: str` (optional, default "")
- `node_id_bkcal_in_substatus: str` (optional, default "")
- `node_id_bkcal_out_substatus: str` (optional, default "")

`GET /controllers/{id}` returns them in the response.

### 8.2. STATUS Topic (ZMQ → HMI)

The `STATUS.{cid}` message on the ZMQ bus expands to include FF signal data:

```json
{
  "controller_id": 1,
  "pv": {"value": 50.2, "severity": "GOOD", "limit_bits": "NONE", "sub_status": "NONE", "timestamp": "..."},
  "sp": {"value": 50.0, "severity": "GOOD", "limit_bits": "NONE", "sub_status": "NONE", "timestamp": "..."},
  "co": {"value": 62.5, "severity": "GOOD", "limit_bits": "NONE", "sub_status": "NONE", "timestamp": "..."},
  "bkcal_in": {"value": 62.3, "severity": "GOOD", "limit_bits": "NONE", "sub_status": "GOOD_CASCADE", "timestamp": "..."},
  "bkcal_out": {"value": 62.5, "severity": "GOOD", "limit_bits": "NONE", "sub_status": "NONE", "timestamp": "..."},
  "integral_val": 45.1,
  "timestamp": "2026-04-04T10:30:00Z"
}
```

### 8.3. Backward Compatibility

For ZMQ deserialization, if a field is received as a plain `float` (old format), it is
auto-wrapped: `FFSignal.good(value)`. If status sub-fields are missing, defaults apply
(GOOD/NONE/NONE). This ensures HMI clients that haven't been updated continue to work.

---

## 9. SQLite / Historian

The historian batch insert for telemetry gains additional columns:

- `pv_severity`, `sp_severity`, `co_severity` (TEXT)
- `bkcal_in_value`, `bkcal_in_severity`, `bkcal_in_limit_bits`, `bkcal_in_sub_status` (REAL + TEXT)
- `bkcal_out_value`, `bkcal_out_severity`, `bkcal_out_limit_bits`, `bkcal_out_sub_status` (REAL + TEXT)

Migration: `ALTER TABLE` adds new columns with defaults (severity=GOOD, limit_bits=NONE,
sub_status=NONE, bkcal values=0.0). Existing data is preserved.

---

## 10. Testing Strategy

### 10.1. Unit Tests (domain)

- `FFSignal` and `FFSignalStatus` creation, factory methods, properties
- `FFSignal` equality and immutability (frozen)
- StatusCode decoding: all combinations of severity × limit bits

### 10.2. Unit Tests (PID engine)

- Normal compute with `FFSignal` inputs (regression — same results as before)
- Directional anti-windup: HIGH_LIMITED blocks positive integration
- Directional anti-windup: LOW_LIMITED blocks negative integration
- CONSTANT blocks all integration
- BKCAL_OUT generation: correct value and limit bits per mode
- IMAN tracking: integral forcing produces exact output match
- Stale data detection triggers BAD status

### 10.3. Unit Tests (mode manager)

- Handshake: CAS + NI → IMAN
- Handshake: IMAN + IR → stay IMAN + tracking
- Handshake: IMAN + GOOD_CASCADE → CAS + bumpless
- Priority: bad PV overrides cascade handshake
- Priority: tracking active overrides all

### 10.4. Integration Tests

- Full cascade handshake cycle: NI → IR → IA → GOOD_CASCADE → CAS active
- Anti-windup with simulated downstream saturation
- Stale data timeout breaks cascade
- ZMQ serialization/deserialization of FFSignal
- API CRUD with new TagBindings fields
- Backward-compatible deserialization (old float format)

---

## 11. Migration Checklist

1. Rename `SignalStatus` → `SignalSeverity` across codebase
2. Add new enums: `LimitBits`, `InitSubStatus`
3. Create `FFSignalStatus` and `FFSignal` in domain
4. Update `TelemetryFrame` and `ControlAction`
5. Update `TagBindings` with BKCAL node IDs
6. Update `PIDEngine.compute()` signature and logic
7. Add integral forcing for IMAN tracking
8. Add BKCAL_OUT generation to PIDResult
9. Update `ModeManager` with cascade handshake
10. Update `BlockStatus` to use `FFSignal`
11. Update `IOWorker` to read full DataValue
12. Update `PIDWorker` main loop
13. Update `OPCUAAdapter` read/write methods
14. Update `OPCUAServer` and `SimulatorAdapter`
15. Update events (`ControlActionComputed`, new `CascadeHandshakeChanged`)
16. Update ZMQ serialization (msgpack)
17. Update API schemas (TagBindings, STATUS topic)
18. SQLite migration for historian columns
19. Update all existing tests
20. Write new tests for FF-specific behavior
