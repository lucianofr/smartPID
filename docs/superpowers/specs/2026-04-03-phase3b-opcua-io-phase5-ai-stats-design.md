# Phase 3b (OPC-UA I/O Worker) + Phase 5 (AI Fuzzy+RL+Statistics) — Design Spec

**Date:** 2026-04-03
**Status:** Approved
**Phases:** 3b and 5 (parallelizable)

---

## Phase 3b — OPC-UA I/O Worker

### Overview

Implement `OPCUAAdapter` as a concrete adapter for the existing hexagonal ports (`TelemetrySource`, `ControlWriter`, `TagBrowser`). Uses `asyncua` (async OPC-UA client) in a daemon thread with its own asyncio event loop, following the same pattern as `SimulatorAdapter`.

### Architecture

```
OPCUAAdapter (adapters/outbound/opcua_adapter.py)
├── implements TelemetrySource
├── implements ControlWriter
├── implements TagBrowser
├── asyncua.Client (internal)
├── ConnectionState enum: OFFLINE | CONNECTING | ONLINE | RECONNECTING
└── daemon thread with dedicated asyncio event loop
```

### Interface

Thread-safe via `SimpleQueue` (same pattern as SimulatorAdapter):

- `read_telemetry(controller_id)` — batch reads NodeIDs from Controller config (node_id_pv, node_id_sp, node_id_co), returns `TelemetryFrame`
- `write_output(controller_id, co)` — writes CO to node_id_co
- `write_parameter(controller_id, param, value)` — writes arbitrary parameter
- `browse_children(node_id)` — lists children of an OPC-UA node
- `search(query)` — searches by DisplayName in the address space

### Connection State Machine

```
OFFLINE ──connect()──► CONNECTING ──success──► ONLINE
   ▲                       │                      │
   │                   failure                 error/timeout
   │                       │                      │
   └───max_retries─── RECONNECTING ◄──────────────┘
                           │
                       exponential backoff
                       (1s, 2s, 4s, ... max 60s)
```

- **Watchdog:** heartbeat every `watchdog_interval_s` (default 5s), reads ServerStatus node
- **Auto-reconnect** with exponential backoff (1s base, 60s max)
- Publishes `CONNECTION_STATE_CHANGED` event on ZMQ bus

### Batch Read Cycle

Each I/O Worker cycle (every `scan_rate_ms` of the controller):

1. Collects all registered NodeIDs for the controller
2. Executes **batch read** via `asyncua.Client.read_values()` — single UA call for N nodes
3. Builds `TelemetryFrame` with PV, SP, CO, timestamp
4. Publishes `TELEMETRY.{id}` on ZMQ bus

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/opcua/status` | ConnectionState + endpoint + latency |
| GET | `/opcua/browse/{node_id}` | List children (NodeId, DisplayName, NodeClass) |
| GET | `/opcua/search?q=...` | Search by DisplayName |
| POST | `/opcua/connect` | Force reconnection |

### AdapterFactory Update

```python
def create_telemetry_source(self) -> TelemetrySource:
    if self._settings.simulator_enabled:
        return self._simulator_adapter
    return self._opcua_adapter

def create_tag_browser(self) -> TagBrowser:
    return self._opcua_adapter  # only available with real OPC-UA
```

### Test Strategy

Embedded `asyncua.Server` as pytest fixture:

- Namespace `urn:smartpid:test` with Float nodes (PV, SP, CO) and Int node (Mode)
- Fixture `opcua_test_server` in `conftest.py` — session-scoped start/stop
- **Test cases:** connect/disconnect, batch read, write CO, reconnect after drop, browse/search, watchdog timeout

---

## Phase 5 — AI (Fuzzy + RL) + Statistics

### Overview

Implement AI-based Ki optimization (Fuzzy logic + Reinforcement Learning) and real-time performance statistics. Domain services are pure logic (zero I/O), workers handle bus integration and threading.

### Architecture

```
Domain Services (pure logic):
├── fuzzy_engine.py     → FuzzyEngine
├── rl_engine.py        → RLEngine
├── stats_calculator.py → StatsCalculator
└── ai_engine.py        → AIEnginePort (Protocol)

Workers (infra/threading):
├── ai_worker.py        → AIWorker (cadence: dead_time_L * 3)
└── stats_worker.py     → StatsWorker (cadence: scan_rate_ms)
```

### AIEnginePort — Common Interface

```python
class AIEnginePort(Protocol):
    def compute_gamma(self, error: float, delta_error: float,
                      context: AIContext) -> AIDecision: ...
    def update(self, reward: float) -> None: ...  # no-op for Fuzzy
```

### AIDecision (Domain Model)

```python
@dataclass(frozen=True)
class AIDecision:
    gamma: float                    # [-1.0, +1.0]
    new_ki: float                   # computed Ki
    reasoning: str                  # human-readable explanation
    membership_values: dict | None  # Fuzzy debug info (None for RL)
```

### FuzzyEngine

**Membership Functions:**
- 7 levels: NB, NM, NS, ZO, PS, PM, PB on universe [-100%, +100%]
- Triangular (center) + trapezoidal (extremes), 50% overlap
- Pure Python implementation (no scikit-fuzzy dependency)

**Rule Matrices:**
- 3 matrices of 7×7 = 49 rules each, one per `ControlObjective`:
  - **SP Tracking:** aggressive response to setpoint changes
  - **Disturbance Rejection:** aggressive near zero error, minimizes offset
  - **Surge Level:** focus on valve stability
- Stored as module-level constants (per spec Module 4.2)

**Pipeline:**
1. Normalize error/delta_error by span → [-100, +100]
2. Fuzzify (compute membership degree for each level)
3. Apply rules (min for AND, max for aggregation)
4. Defuzzify via Center of Gravity (CoG) → gamma
5. `Ki_new = Ki * (1 + gamma * Sv)`, clamped to [ai_limit_min, ai_limit_max]

**Speed Factor (Sv):** SLOW=0.30, MEDIUM=0.15, FAST=0.05

### RLEngine

**Dependency:** `stable-baselines3[extra]` as optional dependency (`pip install smart_pid_core[ai]`)

**Lazy import** — only loads torch/sb3 when `AIEngine.RL` is selected:
```python
def _load_sb3(self):
    from stable_baselines3 import SAC, PPO
```

**Spaces:**
- Observation: `Box(4,)` — `[error_norm, delta_error_norm, co_norm, integral_norm]`
- Action: `Box(low=-1.0, high=1.0, shape=(1,))` — gamma

**Reward Functions (per objective):**
- SP Tracking: `r = -alpha * IAE - beta * TV` (alpha=1.0, beta=0.1)
- Disturbance Rejection: `r = -alpha * ITAE - beta * TV` (alpha=1.0, beta=0.1)
- Surge Level: `r = -alpha * max(0, |error| - deadband) + gamma_s * valve_stability` (alpha=0.5, gamma_s=0.5)

Coefficients are configurable per controller via `AIConfig` extension fields.

**Persistence (hybrid):**
- Weights: `~/.smart_pid/models/{controller_id}/{algorithm}_{timestamp}.zip` (sb3 native format)
- Metadata: `ai_models` SQLite table (controller_id, algorithm, episodes, avg_reward, model_path, created_at)
- Auto-save every N episodes (configurable)

### StatsCalculator (Domain Service)

```python
class StatsCalculator:
    def __init__(self, window_size: int, span: float, setpoint: float): ...
    def add_sample(self, error: float, co: float, dt: float) -> None: ...

    @property
    def iae(self) -> float: ...
    def itae(self) -> float: ...
    def ise(self) -> float: ...
    def mse(self) -> float: ...
    def std_dev(self) -> float: ...
    def total_variation(self) -> float: ...
    def variability_sp(self) -> float: ...    # 2*sigma/SP
    def variability_range(self) -> float: ...  # 2*sigma/Span
```

- Sliding window via `collections.deque(maxlen=window_size)`
- Default window: 1800 samples (~30 min at 1s scan rate)

### StatsWorker

- Runs at `scan_rate_ms` of the controller (same cadence as PID)
- Subscribes to `TELEMETRY.{id}` + `ACTION.CTRL.{id}`
- Feeds StatsCalculator every sample
- Publishes `STATS.{id}` on bus every N samples (configurable, default 60 = 1 min)

### AIWorker

**Cadence:** `T_cycle = dead_time_L * 3` (per controller)

**Cycle:**
1. Receives latest telemetry samples (buffered from bus)
2. Computes normalized error, delta_error
3. Calls `engine.compute_gamma(error, delta_error, context)` (Fuzzy or RL)
4. Publishes `ACTION.AI.{id}` with new Ki → PID Worker applies next cycle
5. Publishes `LOG.AI.{id}` → DB Worker persists to `Log_Sintonia_IA`
6. If RL: computes reward from StatsWorker metrics, calls `engine.update(reward)`

**Engine selection** via `AIConfig.engine`:
- `NONE` → AIWorker does not run for this controller
- `FUZZY` → instantiates FuzzyEngine
- `RL` → instantiates RLEngine (lazy imports sb3)

### New Domain Events

```python
@dataclass(frozen=True)
class AIActionComputed:
    controller_id: str
    gamma: float
    new_ki: float
    engine: AIEngine
    objective: ControlObjective
    reasoning: str
    timestamp: datetime

@dataclass(frozen=True)
class StatsUpdated:
    controller_id: str
    iae: float
    itae: float
    mse: float
    std_dev: float
    total_variation: float
    variability_sp: float
    variability_range: float
    timestamp: datetime
```

### New SQLite Tables

- `ai_models` — id, controller_id, algorithm, episodes, avg_reward, model_path, created_at
- `log_sintonia_ia` — id, controller_id, timestamp, engine, gamma, old_ki, new_ki, reasoning

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/controllers/{id}/stats` | Current metrics from StatsWorker |
| GET | `/controllers/{id}/ai/status` | Active engine, last gamma, current Ki |
| GET | `/controllers/{id}/ai/history` | Tuning history (Log_Sintonia_IA) |
| PUT | `/controllers/{id}/ai/config` | Change engine/objective/speed at runtime |
| POST | `/controllers/{id}/ai/reset` | Reset RL model (restart training) |

### Test Strategy

- **FuzzyEngine:** membership functions, each rule matrix (49 scenarios per objective), normalization, clamp limits
- **RLEngine:** compute_gamma returns valid range, save/load model, reward computation
- **StatsCalculator:** each metric isolated with known series, sliding window eviction
- **AIWorker:** bus integration (receives telemetry, publishes ACTION.AI)
- **StatsWorker:** bus integration (publishes STATS.{id})

---

## Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| OPC-UA library | asyncua (async) | Already a dependency, matches SimulatorAdapter pattern |
| OPC-UA test env | Embedded asyncua.Server | No external OPC-UA server available |
| TagBrowser scope | Backend only (no HMI UI) | UI deferred to Phase 7 |
| AI priority | Fuzzy + RL in parallel | Shared interface (gamma → Ki), both needed |
| Fuzzy implementation | Pure Python | Avoids scikit-fuzzy dependency |
| RL library | stable-baselines3 (optional) | Industry standard, lazy import |
| RL persistence | Hybrid (filesystem + SQLite) | sb3 native .zip for weights, SQL for metadata |
| Statistics worker | Separate from AI Worker | Different cadence (scan_rate vs dead_time*3), useful with AI disabled |
| Stats window | collections.deque | Simple, efficient sliding window |
