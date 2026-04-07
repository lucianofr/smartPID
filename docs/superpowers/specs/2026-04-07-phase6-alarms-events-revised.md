# Phase 6 Revised: Alarms, Events & ACK Workflow — Design Spec

**Date:** 2026-04-07
**Status:** Draft (replaces 2026-04-03-phase6-alarms-rbac-design.md alarm sections)
**Depends on:** Phase 2 (auth/JWT), Phase 3a (HMI desktop)
**Scope:** Alarm engine, alarm worker, system events, ACK workflow, AlarmBar grid, AlarmPanel, REST API

---

## 1. Fundamental Principle

**Rule: One AlarmEngine, one evaluation point.**

The `AlarmWorker` is the **sole component** that evaluates alarms. It:
- Subscribes to `STATUS.*` on the internal ZMQ inproc bus
- Calls `AlarmEngine.evaluate()` for each telemetry frame
- Publishes `EVENT.ALARM.{controller_id}` on the bus
- Enqueues persistence via `AlarmRepository`

The `PIDWorker` **does NOT evaluate alarms**. All references to AlarmEngine inside PIDWorker and LoopManager must be removed. This eliminates:
- Duplicate AlarmEngine instances with independent state
- Duplicate alarm events on the bus
- Timing conflicts between two engines evaluating the same PV

**Rationale:** Alarm evaluation does not require scan-rate precision (milliseconds). One evaluation per telemetry frame in AlarmWorker (which receives `STATUS.*` right after PIDWorker publishes) is sufficient. In real industrial systems (IEC 62682), the alarm engine is always a separate module from the controller.

---

## 2. AlarmEngine (Detection Logic)

Pure domain service, no I/O. Located at `packages/smart_pid_core/src/smart_pid_core/domain/services/alarm_engine.py`.

### 2.1 Interface

```python
class AlarmEngine:
    def evaluate(
        self,
        controller_id: int,
        pv: float,
        sp: float,
        alarm_config: AlarmConfig,
        sp_ramping: bool,
        pv_range: tuple[float, float] | None = None,  # (pv_min, pv_max) for deadband
    ) -> list[AlarmTransition]: ...

    def remove_controller(self, controller_id: int) -> None: ...
```

### 2.2 Alarm Types

| Type | Trigger condition | Clear condition |
|------|-------------------|-----------------|
| HIHI | `PV >= limit` | `PV < (limit - deadband)` |
| HI | `PV >= limit` | `PV < (limit - deadband)` |
| LO | `PV <= limit` | `PV > (limit + deadband)` |
| LOLO | `PV <= limit` | `PV > (limit + deadband)` |
| DV_HI | `(PV - SP) >= limit` | `(PV - SP) < (limit - deadband)` |
| DV_LO | `(SP - PV) >= limit` | `(SP - PV) < (limit - deadband)` |

### 2.3 Deadband — Calculated Over Span, Not Limit

```python
# WRONG (current): deadband = abs(limit) * deadband_percent / 100.0
# CORRECT (new):
if pv_range is not None:
    span = pv_range[1] - pv_range[0]
    deadband = span * deadband_percent / 100.0
else:
    deadband = abs(limit) * deadband_percent / 100.0  # fallback
```

This fixes the bug where `limit = 0.0` produces zero deadband. The instrument span (e.g., 0–200°C → span = 200) is the correct industrial reference (ISA-18.2 recommends deadband as % of span).

### 2.4 Delay ON / Delay OFF

- `delay_on_s`: Minimum time the condition must remain true before triggering. Prevents spurious alarms from spikes.
- `delay_off_s`: Minimum time the condition must remain false before clearing. Prevents chattering at the edge.
- Both use `time.monotonic()` for immunity to clock adjustments.
- If PV oscillates and re-enters the alarm zone during delay_off, the timer resets (correct ISA-18.2 behavior).

### 2.5 Deviation Alarm Suppression

DV_HI and DV_LO are **suppressed** when `sp_ramping=True` (SP ramp active). During a ramp, the PV-SP error is expected and should not generate a deviation alarm.

### 2.6 Internal State Per Point

```python
@dataclass
class _PointState:
    active: bool = False
    pending_trigger_since: float | None = None   # monotonic timestamp
    pending_clear_since: float | None = None      # monotonic timestamp
```

Dictionary key: `(controller_id, alarm_type)`. Cleaned via `remove_controller()` when a loop is deleted.

---

## 3. AlarmWorker

Located at `packages/smart_pid_core/src/smart_pid_core/application/workers/alarm_worker.py`.

Daemon thread, same pattern as PIDWorker/DBWorker.

### 3.1 Lifecycle

```
LoopManager.start() → AlarmWorker.start()
LoopManager.stop()  → AlarmWorker.stop()
```

### 3.2 Subscription and Processing

1. Subscribes to `STATUS.*` on the ZMQ inproc bus (XPUB/XSUB)
2. For each msgpack frame received:
   - Extracts `controller_id`, `pv`, `sp`, `sp_ramping` from payload
   - Looks up `AlarmConfig` from internal cache (`_alarm_configs[controller_id]`)
   - Looks up `pv_range` from controller cache (`_pv_ranges[controller_id]`)
   - If config does not exist for this controller → **skip with `logger.debug`** (not silent)
   - Calls `AlarmEngine.evaluate(controller_id, pv, sp, config, sp_ramping, pv_range)`
3. For each `AlarmTransition` returned:
   - Enriches with `controller_name` and `controller_description` (from controller cache)
   - Publishes `EVENT.ALARM.{controller_id}` on the bus (msgpack)
   - Enqueues async persistence via `AlarmRepository`

### 3.3 Hot-Reload

```python
def update_config(self, controller_id: int, config: AlarmConfig) -> None: ...
def update_pv_range(self, controller_id: int, pv_min: float, pv_max: float) -> None: ...
def remove_controller(self, controller_id: int) -> None: ...
```

Called by the API when the user changes alarm configuration or instrument range. Thread-safe via GIL (atomic reference replacement in dict).

### 3.4 Exception Handling — Mandatory Logging

```python
except (msgpack.UnpackException, KeyError, ValueError) as exc:
    logger.warning("AlarmWorker: failed to process frame: %s", exc)
    # DO NOT silence — the current `pass` is a bug
```

### 3.5 Alarm Event Schema (Published on Bus)

```python
{
    "controller_id": int,
    "controller_name": str,
    "controller_description": str,
    "alarm_type": str,              # "HIHI", "HI", "LO", etc.
    "priority": str,                # "CRITICAL", "WARNING", etc.
    "transition": str,              # "TRIGGERED" or "CLEARED"
    "value": float,                 # PV at the moment
    "limit": float,                 # Configured limit
    "timestamp": str,               # ISO 8601
}
```

### 3.6 What AlarmWorker Does NOT Do

- Does not compute PID (that's PIDWorker)
- Does not persist directly (delegates to AlarmRepository via async)
- Does not manage ACK (that's the API + AlarmRepository)

---

## 4. Persistence

**3 separate tables, 3 distinct repositories.** Each event category has its own schema, lifecycle, and retention.

### 4.1 `Log_Alarmes` (Loop Alarms)

```sql
CREATE TABLE IF NOT EXISTS Log_Alarmes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    controlador_id INTEGER NOT NULL,
    tipo_alarme TEXT NOT NULL CHECK(tipo_alarme IN ('HIHI','HI','LO','LOLO','DV_HI','DV_LO')),
    prioridade TEXT NOT NULL CHECK(prioridade IN ('CRITICAL','WARNING','ADVISORY','LOG')),
    valor REAL NOT NULL,
    limite REAL NOT NULL,
    disparado_em TEXT NOT NULL,
    normalizado_em TEXT,
    reconhecido INTEGER NOT NULL DEFAULT 0,
    reconhecido_por TEXT,
    reconhecido_em TEXT,
    FOREIGN KEY (controlador_id) REFERENCES Controladores(id)
);

CREATE INDEX IF NOT EXISTS idx_alarmes_controller ON Log_Alarmes(controlador_id);
CREATE INDEX IF NOT EXISTS idx_alarmes_triggered ON Log_Alarmes(disparado_em);
CREATE INDEX IF NOT EXISTS idx_alarmes_active ON Log_Alarmes(normalizado_em, reconhecido);
```

- Retention: **30 days**
- Lifecycle: TRIGGERED → (ACK) → CLEARED → (ACK) → REMOVED
- `AlarmRepository`: `insert_alarm`, `mark_cleared`, `acknowledge`, `acknowledge_all`, `get_active`, `get_history`

### 4.2 `Log_Sintonia_IA` (AI Logs — Existing, No Changes)

```sql
CREATE TABLE IF NOT EXISTS Log_Sintonia_IA (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    controlador_id INTEGER NOT NULL,
    valor_anterior REAL,
    valor_novo REAL,
    justificativa TEXT,
    FOREIGN KEY (controlador_id) REFERENCES Controladores(id)
);
```

- Retention: **7 days** (same as Log_Processo)
- Write-once, read-many. No ACK, no state transitions.
- Existing repository, no changes.

### 4.3 `Log_System_Events` (New)

```sql
CREATE TABLE IF NOT EXISTS Log_System_Events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    source TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('CRITICAL','WARNING','INFO')),
    message TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sysevents_timestamp ON Log_System_Events(timestamp);
CREATE INDEX IF NOT EXISTS idx_sysevents_severity ON Log_System_Events(severity);
```

- Retention: **30 days** (same as alarms)
- Write-once, read-many. No ACK.
- `source` identifies the origin: `"OPCUA"`, `"BACKEND"`, `"ZMQ"`, `"PROJECT"`, `"WORKER"`
- `SystemEventRepository`: `insert_event`, `get_history(start, end, source?, severity?, limit, offset)`

### 4.4 Typical System Events

| Source | Severity | Example Message |
|--------|----------|-----------------|
| BACKEND | INFO | "Backend started" / "Backend shutdown" |
| OPCUA | WARNING | "OPC-UA connection lost to opc.tcp://..." |
| OPCUA | INFO | "OPC-UA reconnected" |
| PROJECT | INFO | "Project 'PlantaA' opened" |
| WORKER | CRITICAL | "PIDWorker crashed for controller 3, restarting" |
| ZMQ | WARNING | "ZMQ publisher socket bind failed on port 5555" |

---

## 5. ACK Workflow (ISA-18.2 Simplified)

### 5.1 State Machine Per Alarm Instance

```
TRIGGERED ──────────────────► UNACKNOWLEDGED (blinking)
    │                              │
    │ (operator ACK)               │ (PV normalizes before ACK)
    │                              ▼
    │                        CLEARED_UNACK (visible, no blink)
    │                              │
    ▼                              │ (operator ACK)
ACKNOWLEDGED (solid) ──────────────┤
    │                              ▼
    │ (PV normalizes)         REMOVED (from active list)
    ▼                              ▲
REMOVED ───────────────────────────┘
```

### 5.2 Visibility Rules

- **Active** = `normalizado_em IS NULL`
- **Visible in active list** = `normalizado_em IS NULL OR reconhecido = 0`
- **Removed from active list** = `normalizado_em IS NOT NULL AND reconhecido = 1`
- Priority **LOG**: persists in DB but **does NOT appear** in AlarmBar or card header. Visible only in AlarmPanel with explicit filter.

### 5.3 ACK Single — Full Flow

1. HMI: user selects alarm row in AlarmBar grid or AlarmPanel table, clicks ACK
2. Widget reads the `id` field from `Qt.ItemDataRole.UserRole` — **not** `alarm_id`
3. HMI emits signal `ack_requested(alarm_id: int)`
4. MainWindow sends `POST /alarms/{alarm_id}/ack` (with JWT)
5. Backend: AlarmRepository marks `reconhecido=1, reconhecido_por=username, reconhecido_em=now`
6. Backend: returns the updated alarm (with `controller_id` and `alarm_type`)
7. MainWindow receives response and **updates all 3 widgets**:
   - `AlarmPanel`: changes alarm status in table to ACKNOWLEDGED
   - `AlarmBar`: changes row to solid color, stops blinking, updates counters
   - `ControllerCard`: stops blinking, changes to solid color

### 5.4 ACK All — Full Flow

1. HMI: user clicks "ACK ALL" (in AlarmBar or AlarmPanel)
2. MainWindow sends `POST /alarms/ack-all` (with JWT)
3. Backend: `AlarmRepository.acknowledge_all()` marks all unacknowledged, returns **count and list of affected controller_ids**
4. MainWindow receives response and **updates all 3 widgets**:
   - `AlarmPanel`: changes status of all UNACKNOWLEDGED → ACKNOWLEDGED
   - `AlarmBar`: stops all row blinking, updates counters
   - `ControllerCard`: stops blink on all affected cards

### 5.5 ACK All Response Contract

```python
# Response from POST /alarms/ack-all
{
    "acknowledged_count": int,
    "controller_ids": list[int],   # affected controller IDs
}
```

### 5.6 Critical Rule

ACK is a **UI consistency** operation — it is not enough to make the API call. All 3 widgets (panel, bar, cards) **must** reflect the change immediately without depending on manual refresh or the next ZMQ event.

---

## 6. System Events

New subsystem to capture and persist infrastructure events that are currently lost in Python logging.

### 6.1 SystemEventWorker

Daemon thread, same pattern as AlarmWorker. But does **not** subscribe to `STATUS.*` — instead, it is a **facade** that other components call directly.

```python
class SystemEventWorker:
    def emit(self, source: str, severity: str, message: str) -> None:
        """Thread-safe. Can be called from any thread."""
        # 1. Publishes EVENT.SYSTEM on the ZMQ inproc bus
        # 2. Enqueues persistence in SystemEventRepository
```

### 6.2 Callers

| Component | When | Source | Severity |
|-----------|------|--------|----------|
| `main.py` | Startup / shutdown | BACKEND | INFO |
| `main.py` | Project open / close | PROJECT | INFO |
| IOWorker | OPC-UA connect / disconnect / reconnect | OPCUA | INFO / WARNING |
| IOWorker | OPC-UA connection failed | OPCUA | CRITICAL |
| LoopManager | Worker crash + restart | WORKER | CRITICAL |
| AlarmWorker | Frame processing error | WORKER | WARNING |
| TelemetryPublisher | ZMQ bind failure | ZMQ | WARNING |

### 6.3 ZMQ Topic

`EVENT.SYSTEM` (no controller_id suffix — these are global events).

Event schema:
```python
{
    "source": str,       # "OPCUA", "BACKEND", "ZMQ", "PROJECT", "WORKER"
    "severity": str,     # "CRITICAL", "WARNING", "INFO"
    "message": str,
    "timestamp": str,    # ISO 8601
}
```

Bridged by TelemetryPublisher to TCP PUB socket. Add `b"EVENT.SYSTEM"` to `_BRIDGE_TOPICS` list.

### 6.4 HMI Reception

- `TelemetrySub`: add subscription to `EVENT.SYSTEM`
- `BusBridge`: new signal `system_event_received = Signal(object)`, emitted in `_drain()` when topic starts with `EVENT.SYSTEM`
- `MainWindow`: connects `bus_bridge.system_event_received` → `alarm_panel.on_system_event()`
- `AlarmPanel`: inserts into table with category "System Event", color based on severity

### 6.5 REST API

| Endpoint | Method | Min Role | Description |
|----------|--------|----------|-------------|
| `/system-events` | GET | OPERATOR | History with filters (start, end, source, severity, limit, offset) |

No ACK for system events — they are read-only.

### 6.6 Retention

Daily cleanup: `DELETE FROM Log_System_Events WHERE timestamp <= datetime('now', '-30 days')`

Executed by the same job that cleans `Log_Alarmes`.

---

## 7. HMI: AlarmPanel

Full revision of the alarm management page.

### 7.1 Construction: `api_client` Required

```python
# WRONG (current):
self._alarm_panel = AlarmPanel(theme=theme)

# CORRECT:
self._alarm_panel = AlarmPanel(theme=theme, api_client=self._api_client)
```

`api_client` becomes a **required parameter** (no `None` default). This guarantees at construction time that history and active alarms work.

### 7.2 Multi-Select Filters with CheckableComboBox

Custom widget replacing simple QComboBox. Each combo shows internal checkboxes and displays condensed text of selections (e.g., "CRITICAL, WARNING").

3 multi-select filters:

| Filter | Options |
|--------|---------|
| **Category** | Loop Alarm, AI Log, System Event |
| **Priority** | CRITICAL, WARNING, ADVISORY, LOG (+ INFO for System Events) |
| **Type** | HIHI, HI, LO, LOLO, DV_HI, DV_LO (only when category includes Loop Alarm) |

Plus 2 time filters:
- **From**: QDateTimeEdit (default: 24h ago)
- **To**: QDateTimeEdit (default: now)

**"Apply"** button filters locally over data already loaded in the table.
**"Load History"** button queries the backend with the selected filters.

### 7.3 Live Mode

**"Live"** checkbox in the top-right corner of the panel:

- **When activated:**
  - Disables From/To fields and "Load History" button
  - Starts a **5-second timer** that calls `GET /alarms/active` + `GET /system-events?start={now-5min}&end={now}`
  - Real-time ZMQ events (via BusBridge) continue to be inserted immediately
  - Table shows the **last 100 entries** (combination of 3 categories), ordered by timestamp descending
  - Category, Priority, and Type filters continue working (local filter over live data)

- **When deactivated:**
  - Re-enables From/To and "Load History"
  - Stops the timer
  - Keeps current data in the table (does not clear)

### 7.4 Table: Columns and Data

| Column | Source (Loop Alarm) | Source (AI Log) | Source (System Event) |
|--------|--------------------|-----------------|-----------------------|
| Timestamp | `disparado_em` | `timestamp` | `timestamp` |
| Category | "Loop Alarm" | "AI Log" | "System Event" |
| Controller | `controller_name` | `controller_name` | "—" |
| Type | `tipo_alarme` | "AI_TUNING" | `source` |
| Priority | `prioridade` | "—" | `severity` |
| Value | `valor` | `valor_novo` | "—" |
| Message | auto-generated | `justificativa` | `message` |
| Status | UNACK/ACK/CLEARED | "—" | "—" |

- Row colors by priority: CRITICAL=red, WARNING=yellow, ADVISORY=blue, LOG/INFO=gray
- UNACKNOWLEDGED rows blink (QTimer 500ms background visibility toggle)
- `id` field stored in `Qt.ItemDataRole.UserRole` for ACK — **not** `alarm_id`

### 7.5 ACK Buttons

- **"ACK Selected"**: enabled when selection contains row(s) with category "Loop Alarm" and status UNACKNOWLEDGED. Reads `id` from `UserRole`. Emits `ack_requested(alarm_id)`.
- **"ACK All"**: always enabled when UNACKNOWLEDGED alarms exist. Emits `ack_all_requested()`.
- Both buttons are **disabled** for AI Log and System Event categories (they have no ACK).

---

## 8. HMI: AlarmBar + Controller Cards

### 8.1 AlarmBar — Active Alarms Grid (Dashboard Footer)

**Complete replacement:** The current "pills" design is removed. The AlarmBar becomes a **QTableWidget** fixed at the bottom of the dashboard (fixed height ~150px, with vertical scroll if needed).

**Grid columns:**

| Column | Content | Width |
|--------|---------|-------|
| **Priority** | Icon + text (CRITICAL / WARNING / ADVISORY) | Fixed, ~100px |
| **Level** | Alarm type triggered (HIHI, HI, LO, LOLO, DV_HI, DV_LO) | Fixed, ~80px |
| **Loop** | `controller_name` (e.g., "TIC-101") | Fixed, ~100px |
| **Description** | `controller_description` (e.g., "Temp. Reator A") | Stretch |
| **Date/Time** | Trigger timestamp, format `dd/MM/yyyy HH:mm:ss` | Fixed, ~150px |
| **ACK** | Clickable button/checkbox per row | Fixed, ~60px |

**Row visual behavior:**

| State | Row background | Text |
|-------|---------------|------|
| UNACKNOWLEDGED + CRITICAL | Blinking red (500ms toggle) | White bold |
| UNACKNOWLEDGED + WARNING | Blinking yellow (500ms toggle) | Black bold |
| UNACKNOWLEDGED + ADVISORY | Blinking blue (500ms toggle) | White bold |
| ACKNOWLEDGED + any | Solid priority color (no blink) | Normal |

- Priority **LOG**: **does NOT appear** in the grid (only in AlarmPanel).
- **CLEARED** alarm (normalized): row is **removed** from the grid.

**ACK column — per-row interaction:**

- UNACKNOWLEDGED alarm: displays clickable icon (e.g., empty checkbox or "ACK" button)
- Click → emits `ack_requested(alarm_id)` → MainWindow sends `POST /alarms/{id}/ack`
- After ACK: icon changes to check (✓), row stops blinking, color becomes solid
- Already ACKNOWLEDGED alarm: check icon (✓), not clickable

**"ACK ALL" button:**

Positioned to the right of the grid. Acknowledges all visible alarms in the grid at once.

**Dashboard layout:**

```
┌──────────────────────────────────────────────────────────┐
│  Grid de Cards (top)                                      │
├────────────────────────────────────┬─────────────────────┤
│  Trend Chart (70%)                 │  Faceplate (30%)    │
├────────────────────────────────────┴─────────────────┬───┤
│  [ ACTIVE ALARMS: 3 ]                                │ACK│
│  Priority | Level | Loop    | Description  | DateTime│ALL│
│  🔴 CRITICAL HIHI   TIC-101  Temp Reactor A  07/04…  │   │
│  ⚠️ WARNING  HI     FIC-203  Flow Feed       07/04…  │   │
│  🔴 CRITICAL LOLO   LIC-005  Tank Level      07/04…  │   │
└──────────────────────────────────────────────────────┴───┘
```

**Sorting:** By priority (CRITICAL first), then by timestamp (most recent first).

**Header with counters:**

```
[ ACTIVE ALARMS ] CRITICAL: 2 | WARNING: 1 | ADVISORY: 0
```

Counters reflect only UNACKNOWLEDGED alarms.

**State update methods (called by MainWindow):**

```python
def on_alarm(self, alarm: dict) -> None:                    # TRIGGERED or CLEARED
def on_alarm_acked(self, controller_id: int, alarm_type: str) -> None:  # ACK single
def on_all_alarms_acked(self) -> None:                      # ACK all
```

### 8.2 Controller Cards (Alarm Header)

Each card has an **alarm strip** at the top with ISA-18.2 behavior:

| State | Visual |
|-------|--------|
| No alarm | Strip hidden, neutral border |
| UNACKNOWLEDGED | **Blinking** strip (500ms) in priority color + icon |
| ACKNOWLEDGED | **Solid** strip in priority color + icon, no blink |
| CLEARED (normalized) | Strip disappears, border returns to neutral |

**Multiple simultaneous alarms:**

A controller can have multiple active alarms (e.g., HI + HIHI). The card displays only the **highest priority** one (CRITICAL > WARNING > ADVISORY). The internal `_active_alarms` dict tracks all, but the visual shows the "worst".

Hierarchy: `CRITICAL > WARNING > ADVISORY` (LOG never appears on the card).

**Icons by priority:**
- CRITICAL: red octagon
- WARNING: yellow triangle
- ADVISORY: blue info circle

**State update methods (called by MainWindow):**

```python
def on_alarm(self, alarm: dict) -> None:
def on_alarm_ack(self, controller_id: int, alarm_type: str | None = None) -> None:
```

When `alarm_type=None` in ACK, marks **all** alarms of the card as acknowledged (used in ACK All).

---

## 9. REST API

### 9.1 Alarm Endpoints

| Endpoint | Method | Min Role | Description |
|----------|--------|----------|-------------|
| `/alarms/active` | GET | OPERATOR | Active alarms (visible in active list) |
| `/alarms/history` | GET | OPERATOR | History with filters |
| `/alarms/{alarm_id}/ack` | POST | OPERATOR | ACK single |
| `/alarms/ack-all` | POST | OPERATOR | ACK all unacknowledged |

**`GET /alarms/active`**

Query params: `controller_id?`, `priority?`

Returns alarms where `normalizado_em IS NULL OR reconhecido = 0`.

```python
# Response
[{
    "id": int,
    "controller_id": int,
    "controller_name": str,        # JOIN with Controladores
    "controller_description": str,  # JOIN with Controladores
    "alarm_type": str,
    "priority": str,
    "value": float,
    "limit": float,
    "triggered_at": str,
    "cleared_at": str | None,
    "acknowledged": bool,
    "ack_by": str | None,
    "ack_at": str | None,
}]
```

**`GET /alarms/history`**

Query params: `start`, `end`, `controller_id?`, `priority?`, `alarm_type?`, `limit=100`, `offset=0`

Returns all alarms in the interval (including those already removed from active list).

**`POST /alarms/{alarm_id}/ack`**

- Validates the alarm exists and `reconhecido = 0`
- Marks `reconhecido=1, reconhecido_por=username, reconhecido_em=now`
- Records audit trail (`ACK_ALARM`)
- Returns the updated alarm (with `controller_id` and `alarm_type` for HMI widget update)

```python
# Response
{
    "id": int,
    "controller_id": int,
    "alarm_type": str,
    "priority": str,
    "acknowledged": True,
}
```

**`POST /alarms/ack-all`**

- Marks all where `reconhecido = 0`
- Records audit trail (`ACK_ALARM_ALL`)
- Returns count and list of affected controllers

```python
# Response
{
    "acknowledged_count": int,
    "controller_ids": list[int],
}
```

### 9.2 Alarm Configuration Endpoints

| Endpoint | Method | Min Role | Description |
|----------|--------|----------|-------------|
| `/controllers/{id}/alarm-config` | GET | OPERATOR | Alarm config for controller |
| `/controllers/{id}/alarm-config` | PUT | SUPERVISOR | Update config + hot-reload AlarmWorker |

The PUT:
1. Validates values (HIHI limit > HI > LO > LOLO, deadband >= 0, delays >= 0)
2. Persists in `Configuracao_Alarmes`
3. Calls `alarm_worker.update_config(controller_id, new_config)`
4. If the controller has `pv_min/pv_max`, calls `alarm_worker.update_pv_range(controller_id, pv_min, pv_max)`
5. Records audit trail (`CONFIG_ALARM`)

### 9.3 System Events Endpoints

| Endpoint | Method | Min Role | Description |
|----------|--------|----------|-------------|
| `/system-events` | GET | OPERATOR | History with filters |

Query params: `start`, `end`, `source?`, `severity?`, `limit=100`, `offset=0`

```python
# Response
[{
    "id": int,
    "timestamp": str,
    "source": str,
    "severity": str,
    "message": str,
}]
```

### 9.4 AI Log Endpoints (Existing, No Changes)

| Endpoint | Method | Min Role | Description |
|----------|--------|----------|-------------|
| `/controllers/{id}/ai-log` | GET | OPERATOR | AI decision history |

---

## 10. Bug Registry

Consolidated list of bugs found during investigation, with root cause, spec section that defines correct behavior, and prescribed fix.

| # | Severity | Symptom | Root Cause | Spec § | Fix |
|---|----------|---------|-----------|--------|-----|
| **1** | CRITICAL | Duplicate alarms, conflicting timings | Two AlarmEngine instances (PIDWorker + AlarmWorker) with independent state | §1 | Remove all AlarmEngine references from PIDWorker and LoopManager. AlarmWorker is the sole evaluator. |
| **2** | CRITICAL | Alarms never trigger in Execute mode | `_row_to_controller()` does not populate `alarm_config` → PIDWorker guard always fails → dead code | §1 | Remove dead code from PIDWorker (consequence of fix #1). No need to populate alarm_config on Controller. |
| **3** | CRITICAL | AlarmPanel doesn't load history or active alarms | `AlarmPanel` constructed without `api_client` (parameter omitted in MainWindow) | §7.1 | Pass `api_client` at construction. Make parameter required. |
| **4** | MAJOR | ACK Selected doesn't work | AlarmPanel looks for `alarm.get("alarm_id")` but the field is `"id"` (from API) and doesn't exist in ZMQ events | §5.3, §7.4 | Use `"id"` for alarms from API. For ZMQ-sourced alarms (no DB `id`), disable ACK until panel refreshes via API. |
| **5** | MAJOR | ACK All doesn't update AlarmPanel or AlarmBar | MainWindow only updates cards after ACK All, ignores panel and bar | §5.4, §8.1 | After ACK All, call `alarm_panel.on_all_acked()`, `alarm_bar.on_all_alarms_acked()`, and `card.on_alarm_ack()` for each affected controller. |
| **6** | MAJOR | AlarmBar shows "?" for controller name | Alarm event from AlarmWorker doesn't include `controller_name` | §3.5 | AlarmWorker enriches event with `controller_name` and `controller_description` from cache. |
| **7** | MODERATE | Timestamp filter silently fails | `datetime.fromisoformat()` with generic `except` masks errors | §7.4 | Normalize timestamps to consistent format. Add logging in except. |
| **8** | MODERATE | Alarms "stuck" with deadband + delay_off | Oscillation at edge keeps resetting the clear timer. Correct ISA-18.2 behavior, but aggravated by bug #11. | §2 | Not a logic bug — but the deadband fix (bug #11) reduces oscillation window. Document as expected behavior. |
| **9** | MODERATE | Silent processing failures in AlarmWorker | `except (UnpackException, KeyError, ValueError): pass` without logging | §3.4 | Add `logger.warning()` in the except block. |
| **10** | MODERATE | No alarms if `Configuracao_Alarmes` is empty | AlarmWorker receives empty dict, silent skip for every controller | §3.2 | `logger.debug` when config doesn't exist (addressed in §3.2). Correct behavior — no config = no alarm. |
| **11** | MODERATE | Zero deadband when limit = 0.0 | `deadband = abs(limit) * percent / 100` → if limit=0, deadband=0, causes chattering | §2.3 | Calculate deadband over instrument span (`pv_range`), with fallback to `abs(limit)`. |
| **12** | INFO | Column names diverge between spec and code | Phase 6 spec uses English, code uses Portuguese | §4 | Revised spec aligns with code (Portuguese). No column refactoring. |

---

## 11. Out of Scope

| Item | Reason | When |
|------|--------|------|
| **Sound/audio for CRITICAL** | Cross-platform audio complexity (Linux/Windows), needs UX definition for repeat/silence | Phase 7+ |
| **Alarm shelving** (ISA-18.2 "Shelved") | Operator temporarily suppresses an alarm. Requires additional state + auto-unshelve timer. YAGNI for MVP. | Phase 7+ |
| **External notifications** (email, SMS, push) | Requires integration with external services, SMTP/gateway configuration | Phase 7+ |
| **Row-level security** | All users see all controllers. Per-controller visibility filter is overkill for 3 fixed roles. | No plan |
| **Alarm rationalization** | Tool to analyze whether alarm limits are well configured (alarm rate/hour, nuisance alarms). | Phase 7+ |
| **Unified event table** | Decision: keep separate tables (§4). Panel aggregates in the UI. | Discarded |
| **Alarms in PIDWorker** | Decision: single evaluation in AlarmWorker (§1). PIDWorker does not evaluate alarms. | Discarded |
