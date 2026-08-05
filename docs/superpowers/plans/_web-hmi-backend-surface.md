# Smart PID v2 — Backend API Surface Map (for Web HMI plans)

> Read-only reference. Maps the EXISTING FastAPI/EventBus surface so React/Vite web-HMI plans
> cite real paths, names, models, and topics. No changes proposed. All paths absolute under repo root.

Base import root: `packages/smart_pid_core/src/smart_pid_core/` (core) and
`packages/smart_pid_domain/src/smart_pid_domain/` (domain).

---

## 1. App factory

- File: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
- `create_app(...)` at **app.py:55-118**. Keyword-only signature:
  ```python
  def create_app(*, repo, historian, user_repo, loop_manager, settings,
      simulator_adapter=None, opcua_adapter=None, stats_workers=None, ai_workers=None,
      ai_repo=None, project_service=None, alarm_repo=None, alarm_worker=None,
      audit_repo=None, system_event_repo=None, event_bus=None) -> FastAPI
  ```
- `app = FastAPI(title="Smart PID API", version="2.0.0", lifespan=_lifespan)` at **app.py:75**.
- **Dependency injection model**: every collaborator is stored on `app.state.*` (app.py:78-94),
  e.g. `app.state.event_bus = event_bus` (**app.py:93**), `app.state.loop_manager`, `app.state.repo`,
  `app.state.settings`, `app.state.execution_mode = settings.execution_mode` (app.py:94).
  Routers read these via `dependencies.py` getters (e.g. `get_event_bus`, `get_loop_manager`).
- **Router registration**: `app.include_router(...)` block at **app.py:100-114** (order matters:
  `stats` and `ai` registered BEFORE `controllers` so literal sub-paths aren't swallowed by `/{controller_id}`).
- `_lifespan` async ctx manager at **app.py:49-52** sets `app.state.start_time`; nothing else started here.
- **A WS endpoint + `StaticFiles` (SPA mount) + `CORSMiddleware` would be added here** (around the
  include_router block / after `app = FastAPI(...)`).
- **CURRENT ABSENCE (verified)**: NO `StaticFiles`, NO `mount`, NO `CORSMiddleware` /
  `add_middleware`, NO `websocket`/`WebSocket` anywhere in app.py. This is a pure JSON REST API today;
  the new RealtimeWS + static SPA serving + CORS are all greenfield additions.

---

## 2. Routers inventory

All routers live in `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/`.
Prefixes are applied at registration (app.py); routers declare NO inner `prefix=`.
`cid` = where `controller_id` is: PATH = path param `{controller_id}`; `-` = N/A; BODY = in request body.
Auth = the FastAPI dependency guarding the handler. **⚠ = no `response_model`**.

### auth.py — prefix `/auth`
- `POST /login` → `login` → cid=- → auth=**none (public)** → `TokenResponse`
- `POST /register` → `register` → cid=- → auth=`require_admin` → **⚠ NONE — missing**
- `POST /refresh` → `refresh_token` → cid=- → auth=`get_current_user` → `TokenResponse`

### controllers.py — prefix `/controllers`
- `GET ` → `list_controllers` → cid=- → auth=`require_supervisor` → `list[ControllerResponse]`
- `POST ` → `create_controller` → cid=BODY → auth=`require_supervisor` → `ControllerResponse`
- `GET /{controller_id}` → `get_controller` → cid=PATH → `require_supervisor` → `ControllerResponse`
- `PUT /{controller_id}` → `update_controller` → cid=PATH → `require_supervisor` → `ControllerResponse`
- `DELETE /{controller_id}` → `delete_controller` → cid=PATH → `require_admin` → **⚠ NONE — missing**
- `GET /{controller_id}/alarm-config` → `get_alarm_config` → cid=PATH → `require_operator` → `AlarmConfigResponse`
- `PUT /{controller_id}/alarm-config` → `update_alarm_config` → cid=PATH → `require_supervisor` → `AlarmConfigResponse`

### stats.py — prefix `/controllers`
- `GET /stats` → `get_all_stats` → cid=- → `require_operator` → `list[StatsResponse]`
- `GET /{controller_id}/stats` → `get_stats` → cid=PATH → `require_operator` → `StatsResponse`

### ai.py — prefix `/controllers`
- `GET /{controller_id}/ai/status` → `get_ai_status` → cid=PATH → `require_operator` → `AIStatusResponse`
- `GET /{controller_id}/ai/history` → `get_ai_history` → cid=PATH → `require_operator` → `AIHistoryResponse`
- `POST /{controller_id}/ai/start` → `start_ai` → cid=PATH → `require_operator` → **⚠ NONE — missing**
- `POST /{controller_id}/ai/stop` → `stop_ai` → cid=PATH → `require_operator` → **⚠ NONE — missing**
- `POST /{controller_id}/ai/pause` → `pause_ai` → cid=PATH → `require_operator` → **⚠ NONE — missing**

### commands.py — prefix `/commands`
- `POST /setpoint` → `set_setpoint` → cid=BODY → `require_operator` → `CommandResponse`
- `POST /mode` → `set_mode` → cid=BODY → `require_operator` → `CommandResponse`
- `POST /output` → `set_output` → cid=BODY → `require_operator` → `CommandResponse`
- `POST /tuning` → `write_tuning` → cid=BODY → `require_operator` → `CommandResponse`
- `GET /tuning-recommendations/{controller_id}` → `get_tuning_recommendation` → cid=PATH → `require_operator` → **⚠ NONE — missing**
- `POST /apply-tuning/{controller_id}` → `apply_tuning` → cid=PATH → `require_supervisor` → **⚠ NONE — missing**

### history.py — prefix `/history`
- `GET /{controller_id}` → `query_history` → cid=PATH → `require_operator` → `HistoryResponse`

### alarms.py — prefix `/alarms`
- `GET /active` → `get_active_alarms` → cid=- (optional query) → `require_operator` → **⚠ NONE — missing**
- `GET /history` → `get_alarm_history` → cid=- (optional query) → `require_operator` → **⚠ NONE — missing**
- `GET /ai-history` → `get_ai_log_history` → cid=- (optional query) → `require_operator` → **⚠ NONE — missing**
- `POST /{alarm_id}/ack` → `ack_alarm` → cid=- → `require_operator` → **⚠ NONE — missing**
- `POST /ack-all` → `ack_all_alarms` → cid=- → `require_operator` → **⚠ NONE — missing**

### stats / history / system see above and below. system.py — prefix `/system`
- `GET /status` → `system_status` → cid=- → auth=**none (public)** → `SystemStatusResponse`

### system_events.py — prefix `/system-events`
- `GET ` → `get_system_events` → cid=- → `require_operator` → **⚠ NONE — missing**

### audit.py — prefix `/audit`
- `GET ` → `get_audit_history` → cid=- → `require_supervisor` → **⚠ NONE — missing**

### users.py — prefix `/users`
- `GET ` → `list_users` → cid=- → `require_admin` → **⚠ NONE — missing**
- `POST ` → `create_user` → cid=- → `require_admin` → **⚠ NONE — missing**
- `GET /{user_id}` → `get_user` → cid=- → `require_admin` → **⚠ NONE — missing**
- `PUT /{user_id}` → `update_user` → cid=- → `require_admin` → **⚠ NONE — missing**
- `DELETE /{user_id}` → `deactivate_user` → cid=- → `require_admin` → **⚠ NONE — missing**

### export.py — prefix `/export`
- `POST ` → `create_export` → cid=- → `require_operator` → `ExportJob`
- `GET /{export_id}` → `get_export_status` → cid=- → `require_operator` → `ExportJob`
- `GET /{export_id}/download` → `download_export` → cid=- → `require_operator` → **⚠ NONE — missing** (FileResponse stream)

### project.py — prefix `/project` (NOTE: every endpoint is currently UNAUTHENTICATED)
- `GET /current` → `get_current` → auth=**none** → `ProjectResponse`
- `POST /new` → `new_project` → auth=**none** → `ProjectResponse`
- `POST /open` → `open_project` → auth=**none** → `ProjectResponse`
- `GET /list` → `list_projects` → auth=**none** → `ProjectListResponse`
- `POST /import` → `import_project` (multipart upload) → auth=**none** → `ProjectResponse`
- `GET /download` → `download_project` → auth=**none** → **⚠ NONE — missing** (FileResponse)
- `DELETE /{name}` → `delete_project` → auth=**none** → **⚠ NONE — missing**

### opcua.py — prefix `/opcua`
- `GET /status` → `get_status` → `require_operator` → `OPCUAStatusResponse`
- `GET /browse/{node_id:path}` → `browse_children` → `require_operator` → `OPCUABrowseResponse`
- `GET /search` → `search_tags` → `require_admin` → `OPCUASearchResponse`
- `PUT /endpoint` → `save_endpoint` → `require_admin` → `OPCUAStatusResponse`
- `POST /connect` → `force_connect` → `require_admin` → **⚠ NONE — missing**
- `POST /disconnect` → `force_disconnect` → `require_admin` → **⚠ NONE — missing**

### simulator.py — prefix `/simulator` (all `require_supervisor`)
- `POST /start` → `start_simulator` → `CommandResponse`
- `POST /stop` → `stop_simulator` → `CommandResponse`
- `GET /status` → `get_status` → `SimulatorStatusResponse`
- `GET /opcua/status` → `get_opcua_status` → `OPCUAServerStatus`
- `POST /opcua/start` → `start_opcua_server` → `CommandResponse`
- `POST /opcua/stop` → `stop_opcua_server` → `CommandResponse`
- `POST /preset` → `set_preset` → `CommandResponse`
- `PUT /parameters` → `set_parameters` → `CommandResponse`
- `POST /disturbance` → `inject_disturbance` → cid=BODY → `CommandResponse`
- `DELETE /disturbance/{controller_id}` → `clear_disturbance` → cid=PATH → `CommandResponse`
- `POST /{controller_id}/pid/enable` → `enable_pid` → cid=PATH → `CommandResponse`
- `POST /{controller_id}/pid/params` → `set_pid_params` → cid=PATH → `CommandResponse`
- `POST /{controller_id}/pid/sp` → `set_pid_sp` → cid=PATH → `CommandResponse`
- `POST /{controller_id}/co` → `set_co` → cid=PATH → `CommandResponse`
- `POST /{controller_id}/pid/mode` → `set_pid_mode` → cid=PATH → `CommandResponse`
- `GET /{controller_id}/pid/status` → `get_pid_status` → cid=PATH → `SimulatorPIDStatusResponse`
- `PUT /{controller_id}/auto-sp` → `set_auto_sp` → cid=PATH → `ControllerSimStatus`
- `PUT /{controller_id}/auto-disturbance` → `set_auto_disturbance` → cid=PATH → `ControllerSimStatus`

**Router count: 15 router modules** (auth, controllers, stats, ai, commands, history, alarms, system,
system_events, audit, users, export, project, opcua, simulator).
**Endpoints lacking `response_model` (25):** auth `register`; controllers `delete_controller`;
ai `start/stop/pause`; commands `get_tuning_recommendation`, `apply_tuning`; alarms all 5
(`active`, `history`, `ai-history`, `{alarm_id}/ack`, `ack-all`); system_events `get_system_events`;
audit `get_audit_history`; users all 5; export `download_export`; project `download_project`,
`delete_project`; opcua `force_connect`, `force_disconnect`. (FileResponse/streaming endpoints
legitimately omit it; the JSON ones are genuine gaps a web client should treat as untyped.)

---

## 3. EventBus / pub-sub API

File: `packages/smart_pid_core/src/smart_pid_core/application/event_bus.py`

- **`EventBus`** (event_bus.py:44): XPUB/XSUB proxy in a daemon thread over `inproc://` (default
  `url_prefix="inproc://smartpid"`). Publishers connect to XSUB frontend; subscribers to XPUB backend.
  - `create_publisher() -> BusPublisher` (event_bus.py:93) — a `zmq.PUB` connected to frontend.
  - `create_subscriber(topic_prefix: bytes) -> BusSubscriber` (event_bus.py:99) — a `zmq.SUB`
    connected to backend, `socket.subscribe(topic_prefix)`. **Subscription is by byte-prefix**
    (e.g. `b"STATUS."` matches every `STATUS.{id}`).
- **`BusPublisher`** (event_bus.py:10): `send(topic: bytes, payload: bytes)` →
  `socket.send_multipart([topic, payload])` (event_bus.py:15-16).
- **`BusSubscriber`** (event_bus.py:25): the recv contract the new RealtimeWS must mirror:
  ```python
  def recv(self, timeout_ms: int = 0) -> tuple[bytes, bytes] | None:
      if self._socket.poll(timeout=timeout_ms):       # event_bus.py:31
          parts = self._socket.recv_multipart()
          if len(parts) == 2:
              return (parts[0], parts[1])              # (topic_bytes, payload_bytes)
      return None
  ```
  **BLOCKING-RECV DETAIL:** `recv()` first calls **`self._socket.poll(timeout=timeout_ms)`** then
  `recv_multipart()`. So it is a **poll-gated blocking recv**: `recv(0)` returns immediately
  (non-blocking drain), `recv(10)` blocks up to **10 ms** waiting for a message. It is a synchronous
  ZMQ call — in async code it MUST be wrapped (TelemetryPublisher uses `run_in_executor`, see §4).
  Returns `None` on timeout/non-2-part frames.
- **Serialization:** **msgpack** end to end. Publishers send `msgpack.packb(<dict>)`; subscribers
  `msgpack.unpackb(payload)`. Payloads are plain dicts, NOT the frozen event dataclasses (those are
  only the in-process producer types; the wire format is the dict built at the publish site).

### Exact topic-string formats actually published (cite = publish site)
- `TELEMETRY.{controller_id}` — `io_worker.py:115` (and pid_worker.py:202). Producer: IOWorker.
- `STATUS.{controller_id}` — `pid_worker.py:457` (execute mode) and `monitor_worker.py:84` (monitor
  mode). Payload dict: `pv, sp, co, bkcal_in, bkcal_out` (each a serialized FF signal),
  `mode`, `kp`, `ti`, `td`, `integral_val`, `timestamp` (ISO string).
- `ACTION.CTRL.{controller_id}` — `pid_worker.py:432`. Producer: PIDWorker (CO write intent).
- `ACTION.AI.{controller_id}` — `pid_worker.py:205` and `ai_worker.py:~` (AI Ki adjustment).
- `STATS.{controller_id}` — `stats_worker.py:159`. Payload = `get_current_stats()` dict
  (IAE/ITAE/ISE/MSE/std/TV/variability...).
- `EVENT.SYSTEM` — `system_event_worker.py:43` (**fixed string, no id suffix**).
- `EVENT.ALARM.*` — published by AlarmWorker (`alarm_worker.py`); AlarmWorker subscribes `b"STATUS."`
  at alarm_worker.py:131 and emits alarm events under the `EVENT.ALARM.` prefix.

> The external bridge (§4) re-publishes ONLY these prefixes:
> `STATUS.`, `ACTION.CTRL.`, `ACTION.AI.`, `EVENT.ALARM.`, `EVENT.SYSTEM`
> (`telemetry_publisher.py:18`). Raw `TELEMETRY.{id}` and `STATS.{id}` are internal-only and are
> NOT bridged to the external socket today — a web client gets process values via `STATUS.{id}`.

---

## 4. TelemetryPublisher (structural analog for the new RealtimeWS)

File: `packages/smart_pid_core/src/smart_pid_core/application/telemetry_publisher.py`
Class: `TelemetryPublisher(bus: EventBus, publish_port: int = 5555)`.

- **What it is:** a unidirectional bridge — subscribes to the internal `inproc://` EventBus and
  re-publishes on an external `zmq.PUB` bound to `tcp://0.0.0.0:{publish_port}` (default 5555).
- **Bridged topics:** `_BRIDGE_TOPICS = [b"STATUS.", b"ACTION.CTRL.", b"ACTION.AI.", b"EVENT.ALARM.",
  b"EVENT.SYSTEM"]` (telemetry_publisher.py:18).
- **Threading/loop model (telemetry_publisher.py:32-78):**
  - Runs as a single **asyncio.Task** (`start()` schedules `self._run()`); stopped via `_stop_event`
    + task cancel in `stop()`.
  - `_run()` creates `zmq.asyncio.Context`, a `zmq.PUB` socket, `bind(f"tcp://0.0.0.0:{port}")`,
    then one internal subscriber per prefix via `bus.create_subscriber(topic)`.
  - Main loop (while not stop): for each subscriber, calls the **synchronous** `sub.recv(10)` inside
    `await loop.run_in_executor(None, sub.recv, 10)` — i.e. the blocking poll-gated recv is offloaded
    to a thread-pool executor so the asyncio loop is never blocked. On a 2-tuple result it does
    `await pub_socket.send_multipart([topic_bytes, payload])`. `await asyncio.sleep(0.001)` between sweeps.
- **For the web RealtimeWS:** mirror this exactly — create `EventBus` subscribers for the desired
  prefixes, drain them with `run_in_executor(None, sub.recv, <ms>)`, and forward
  `(topic_bytes, msgpack payload)` to connected WebSocket clients (decode msgpack → JSON for browser).

---

## 5. Auth

Files: `.../api/auth.py` (crypto/JWT) and `.../api/dependencies.py` (FastAPI deps).

`auth.py` (pure functions):
- `hash_password(password) -> str` — bcrypt (auth.py:10).
- `verify_password(password, password_hash) -> bool` — bcrypt (auth.py:15).
- `create_access_token(*, user_id, username, role, secret, expiry_hours=8) -> str` (auth.py:20) —
  HS256 JWT, payload `{sub: str(user_id), username, role, exp}`.
- `decode_access_token(token, *, secret) -> dict` (auth.py:38) — HS256 decode/validate, raises
  `jwt.PyJWTError`; casts `sub` back to int.

`dependencies.py`:
- **Login flow:** `POST /auth/login` handler calls `verify_password` then `create_access_token`
  (secret = `settings.jwt_secret`, expiry = `settings.jwt_expiry_hours`), returns `TokenResponse`.
- `get_current_user(request: Request) -> UserClaims` (dependencies.py:51): reads
  `Authorization: Bearer <token>` header, `decode_access_token(token, secret=settings.jwt_secret)`,
  returns `UserClaims(user_id, username, role=<UPPERCASE>)`. 401 on missing/invalid.
- Role ladder `_ROLE_LEVEL = {"OPERATOR":0,"SUPERVISOR":1,"ADMIN":2}` (dependencies.py:75).
  Each guard is `Depends(get_current_user)` then a min-level check (403 otherwise):
  - `require_operator(user) -> UserClaims` (dependencies.py:78)
  - `require_supervisor(user) -> UserClaims` (dependencies.py:90)
  - `require_admin(user) -> UserClaims` (dependencies.py:102)
- Other DI getters (dependencies.py:31-200): `get_repo`, `get_historian`, `get_user_repo`,
  `get_loop_manager`, `get_settings`, `get_event_bus` (503 if absent, dependencies.py:164),
  `get_alarm_repo`, `get_alarm_worker`, `get_ai_repo`, `get_ai_workers`, `get_stats_workers`,
  `get_execution_mode`, plus `controller_label()` and `audit_and_broadcast()` helpers.
- **users.db location:** `CoreSettings.users_db_path = ~/.smart-pid/users.db` (config.py:37).
  Users are app-level and intentionally separate from the project `.spid` file.

`UserClaims` DTO: `packages/smart_pid_domain/src/smart_pid_domain/dtos/auth.py` (fields
`user_id: int`, `username: str`, `role: str`).

---

## 6. Domain models (what the web serializes)

Wire DTOs (Pydantic v2) live in `packages/smart_pid_domain/src/smart_pid_domain/dtos/*.py`
(e.g. `controllers.py` → `ControllerResponse`, `PIDParamsDTO`; `commands.py` → `CommandResponse`;
`auth.py` → `TokenResponse`, `UserClaims`). The internal domain models (dataclasses) below are the
source the DTOs mirror.

`models/controller.py`:
- **`Controller`** (`@dataclass`, **40 fields**): `id:int, name:str, description:str,
  execution_mode:ExecutionMode, scan_rate_s:float, tss_s:float, process_speed:ProcessSpeed,
  process_type:ProcessType, pid_params:PIDParams, pid_structure:PIDStructure,
  integral_type:IntegralType, pv_scale:ScaleConfig, out_scale:ScaleConfig, tag_bindings:TagBindings,
  control_opts:ControlOpts, io_opts:IOOpts, status_opts:StatusOpts, ai_config:AIConfig,
  tuning_write_mode:TuningWriteMode, max_tuning_change_pct:float, track_opt:TrackOpt,
  permitted_modes:set[ControllerMode], mode_normal:ControllerMode, sp_hi_lim, sp_lo_lim,
  sp_rate_up, sp_rate_dn, out_hi_lim, out_lo_lim, arw_hi_lim, arw_lo_lim, pv_ftime, sp_ftime,
  low_cut (all float), ff_enable:bool, ff_gain:float, shed_opt:ControllerMode, shed_time_s:float,
  trk_in_d:bool, alarm_config:AlarmConfig | None`.
- **`PIDParams`** (controller.py:42): `gain (Kp), reset (Ti), rate (Td), alpha (deriv filter),
  deadband` — all `float`.
- Supporting dataclasses: `ScaleConfig(eu_min, eu_max, unit; .span)`, `AIConfig(engine, objective,
  dead_time_l, limit_min, limit_max, rl_fallback_kp, rl_fallback_kd, rl_learning_rate,
  rl_train_interval)`, `TagBindings` (OPC-UA node ids: node_id_pv/sp/co/integral/bkcal_in/bkcal_out/
  kp/ti/td/mode_target/mode_actual + mode_int_map), `ControlOpts`, `IOOpts`, `StatusOpts`.

`models/telemetry.py` (both frozen):
- **`TelemetryFrame`**: `controller_id:int, pv:FFSignal, sp:FFSignal, co:FFSignal,
  bkcal_in:FFSignal, integral_val:float, timestamp:datetime`.
- **`ControlAction`**: `controller_id:int, co:FFSignal, bkcal_out:FFSignal, integral_val:float,
  timestamp:datetime`.

`models/signal.py` — **`FFSignal`**: `severity:SignalSeverity, limit_bits:LimitBits,
sub_status:InitSubStatus, value:float, status:FFSignalStatus, timestamp:datetime | None`. (This is
what `_serialize_ff_signal` flattens into the `STATUS.{id}` payload's pv/sp/co/bkcal fields.)

`events.py` — frozen event dataclasses (all carry `event_id: UUID = uuid4` default):
- `TelemetryReceived`: `controller_id:int, frame:TelemetryFrame`.
- `ControlActionComputed`: `controller_id:int, co:float, integral_val:float, delta_cv:float, timestamp:datetime`.
- `AIActionComputed`: `controller_id:int, gamma:float, new_ki:float, engine:AIEngine,
  objective:ControlObjective, reasoning:str, timestamp:datetime`.
- `StatsUpdated`: `controller_id:int, iae, itae, ise, mse, std_dev, total_variation,
  variability_sp, variability_range (all float), timestamp:datetime`.
- `SystemStateChanged`: `new_state:ConnectionState, reason:str`.
- `AlarmTriggered`: `controller_id:int, alarm_type:AlarmType, priority:AlarmPriority, value:float,
  limit:float, timestamp:datetime`.
- `AlarmCleared`: `controller_id:int, alarm_type:AlarmType, value:float, timestamp:datetime`.
- `AlarmAcknowledged`: `controller_id:int, alarm_type:AlarmType, user_id:int, username:str, timestamp:datetime`.
- `CascadeHandshakeChanged`: `controller_id:int, old_sub_status:InitSubStatus, new_sub_status:InitSubStatus`.

---

## 7. Enums (UI-relevant) — `packages/smart_pid_domain/src/smart_pid_domain/enums.py`

- **`ControllerMode`** (8 + bypass): `OOS, IMAN, LO, MAN, AUTO, CAS, RCAS, ROUT` (plus `BYPASS`).
- **`ExecutionMode`**: `SUPERVISORY, DDC`.
- **`PIDStructure`**: `ISA, PARALLEL, SERIES`.
- **`IntegralType`**: `GAIN_KI, TIME_TI`.
- **`AIEngine`** (AI strategy per loop): `NONE, FUZZY, RL`.
- **`ControlObjective`**: `SP_TRACKING, DISTURBANCE_REJECTION, SURGE_LEVEL`.
- **`ProcessSpeed`**: `ULTRA_FAST, FAST, MEDIUM, SLOW` (carries stats_window_s / speed_factor /
  ai_period_s / label props).
- **`ConnectionState`**: `OFFLINE, CONNECTING, ONLINE, RECONNECTING`.
- **`OptimizerState`**: `RUN, PAUSE, STOP`.
- **`UserRole`**: `ADMIN, SUPERVISOR, OPERATOR`.
- **`AlarmPriority` (severity)**: `CRITICAL, WARNING, ADVISORY, LOG`.
- **`AlarmType`**: `HIHI, HI, LO, LOLO, DV_HI, DV_LO`.
- **`AlarmState`** (ISA-18.2 ACK workflow): `UNACKNOWLEDGED, ACKNOWLEDGED, CLEARED_UNACK`.
- **`SystemExecutionMode`**: `MONITOR ("monitor"), EXECUTE ("execute")`.
- **`ProcessPresetName`** (simulator): `FLOW, PRESSURE, LEVEL, TEMPERATURE, CUSTOM`.
- **`TuningWriteMode`**: `AUTO_APPLY ("auto_apply"), APPROVAL_REQUIRED ("approval_required"),
  DISABLED ("disabled")`.
- **`TuningRecStatus`**: `PENDING, APPLIED, REJECTED, EXPIRED` (lowercase values).
- **`AuditAction`**: LOGIN, LOGOUT, SP_CHANGE, MODE_CHANGE, OUTPUT_CHANGE, ACK_ALARM, ACK_ALARM_ALL,
  TUNE_PID, CONFIG_AI, CONFIG_ALARM, CREATE/UPDATE/DELETE_CONTROLLER, CREATE/UPDATE/DEACTIVATE_USER,
  SIMULATOR_CONFIG, OPCUA_CONFIG.
- Signal-quality enums (in FFSignal): `SignalSeverity` (GOOD, U…), `LimitBits`
  (NONE, LOW_LIMITED, HIGH_LIMITED, CONSTANT), `InitSubStatus` (NONE, NI, IR, IA, GOOD_CASCADE),
  `ProcessType` (SELF_REGULATING, INTEGRATING), `TrackOpt` (ALWAYS_USE_VALUE, USE_LAST_GOOD, TRACK_IF_BAD).

---

## 8. Config — `packages/smart_pid_core/src/smart_pid_core/config.py`

`CoreSettings(BaseSettings)`, `env_prefix="SPID_"`, `.env` supported. UI/web-relevant fields:

| Field | Default | Env var |
|-------|---------|---------|
| `api_host` | `0.0.0.0` | `SPID_API_HOST` |
| `api_port` | `8000` | `SPID_API_PORT` |
| `zmq_publish_port` | `5555` | `SPID_ZMQ_PUBLISH_PORT` |
| `zmq_internal_url` | `inproc://bus` | `SPID_ZMQ_INTERNAL_URL` |
| `jwt_secret` | **required (no default)** | `SPID_JWT_SECRET` |
| `jwt_expiry_hours` | `8` | `SPID_JWT_EXPIRY_HOURS` |
| `db_path` | `./project.spid` | `SPID_DB_PATH` |
| `users_db_path` | `~/.smart-pid/users.db` | `SPID_USERS_DB_PATH` |
| `projects_dir` | `~/.smart-pid/projects` | `SPID_PROJECTS_DIR` |
| `simulator_enabled` | `False` | `SPID_SIMULATOR_ENABLED` |
| `simulator_port` | `4849` | `SPID_SIMULATOR_PORT` |
| `execution_mode` | `monitor` | `SPID_EXECUTION_MODE` |
| `log_level` | `INFO` | `SPID_LOG_LEVEL` |
