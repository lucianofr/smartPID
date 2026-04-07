# OPC-UA Settings Persistence & Auto-Connect

**Date:** 2026-04-06
**Branch:** `fix/settings-opcua-connect-disconnect`
**Status:** Design

## Problem

1. Every time the HMI starts, the OPC-UA client shows as disconnected — the HMI doesn't query backend status on startup.
2. The OPC-UA endpoint URL is hardcoded in the settings page and not persisted per project.
3. The OPC-UA connection should survive HMI restarts — the backend is the autonomous daemon, the HMI is just a viewer.

## Architectural Principle

**The backend is the autonomous daemon. The HMI is a read-only viewer + command sender.**

The backend runs independently — monitoring loops, executing PID, optimizing, simulating — regardless of whether any HMI is connected. The HMI:
1. **Queries** the backend on startup to sync UI with reality
2. **Sends commands** (connect, disconnect, apply settings)
3. **Reflects** what the backend reports

The HMI closing does NOT trigger any disconnect or state change in the backend.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Storage | `Projeto_Meta` key-value (existing) | Reuses existing infra, stays inside `.spid` for import/export |
| Auto-connect on project open | Yes, always | Backend should monitor continuously; opening a project with a saved endpoint means the user intends to use it |
| Endpoint persistence trigger | Apply button (Apply/Cancel pattern) | Consistent with existing settings page UX |
| Connect button behavior | Uses current field value, even if not Applied | Connect is an immediate action; endpoint is not persisted until Apply |

## Metadata Keys

Stored in `Projeto_Meta` table (SQLite key-value):

| Key | Value | Example |
|-----|-------|---------|
| `opcua_endpoint` | OPC-UA server URL | `opc.tcp://10.0.0.1:4840` |

## API Changes

### `PUT /opcua/endpoint`  (new)

Save endpoint to project metadata and configure adapter (without connecting).

**Request:**
```json
{"endpoint": "opc.tcp://10.0.0.1:4840"}
```

**Response:** `OPCUAStatusResponse` — current state + updated endpoint.

**Logic:**
1. Validate `opc.tcp://` prefix
2. Save to `Projeto_Meta` via `repo.set_meta("opcua_endpoint", url)`
3. Call `adapter.set_endpoint(url)` (stop + reconfigure, no reconnect)
4. Return current adapter state

### `POST /opcua/connect`  (modified)

Accept optional endpoint in body. If provided, configure adapter before connecting.

**Request (body optional):**
```json
{"endpoint": "opc.tcp://10.0.0.1:4840"}
```
or empty body `{}` to connect with current endpoint.

**Logic:**
1. If `endpoint` provided: call `adapter.set_endpoint(url)` (does NOT persist — Apply does that)
2. `adapter.stop()` → `adapter.start()` → `adapter.wait_connected(5s)`
3. Return `OPCUAStatusResponse`

### `GET /opcua/status`  (unchanged)

Returns `{state, endpoint}` — already exists and sufficient.

## Backend Changes

### `OPCUAAdapter.set_endpoint(url: str)`  (new method)

```
def set_endpoint(self, url: str) -> None:
    self.stop()
    self._endpoint = url
```

Stops the adapter and updates the endpoint. Does NOT reconnect — caller decides.

### `ProjectService` (modified)

**Constructor:** Receives `opcua_adapter: OPCUAAdapter | None` parameter (similar to `simulator_adapter`).

**`open_project()`:** After `reopen()` and `_load_simulator_configs()`:
1. Read `opcua_endpoint` from `Projeto_Meta`
2. If found and different from current: `adapter.set_endpoint(url)` + `adapter.start()` (auto-connect)
3. If found and same as current + already connected: no-op (keep existing connection)
4. If not found: `adapter.stop()` (disconnect from any previous project's endpoint)

**`new_project()`:** After `reopen()`:
1. `adapter.stop()` (new project has no endpoint)

### `routers/opcua.py` (modified)

- `PUT /opcua/endpoint` — new route, requires admin, saves metadata + configures adapter
- `POST /opcua/connect` — accept optional `OPCUAConnectRequest` body with `endpoint` field

### `dependencies.py` / `main.py` (core)

- Pass `opcua_adapter` to `ProjectService` constructor
- Ensure `project_service` can access both `repo` and `opcua_adapter`

## DTOs (new)

### `OPCUAConnectRequest`
```python
class OPCUAConnectRequest(BaseModel):
    endpoint: str | None = None
```

### `OPCUAEndpointRequest`
```python
class OPCUAEndpointRequest(BaseModel):
    endpoint: str  # must start with opc.tcp://
```

## HMI Changes

### `main.py` — `_sync_opcua_status()` (new method)

Called after `_check_active_project` in the login flow:

1. `GET /opcua/status` → `{state, endpoint}`
2. Update `settings_page`:
   - Set endpoint field to the saved endpoint
   - Set connection status (Connected/Disconnected)
   - Enable/disable Connect/Disconnect buttons
3. If already connected: start watchdog timer

### `main.py` — `_on_opcua_connect` (modified)

Pass endpoint from settings page field to `POST /opcua/connect`:

```python
result = self._api_client.opcua_client_connect(endpoint=url)
```

### `main.py` — Apply flow (modified)

When Apply is clicked and endpoint changed, call `PUT /opcua/endpoint` to persist.

### `settings_page.py` (modified)

- New signal: `opcua_endpoint_save_requested = Signal(str)` — emitted from `_on_apply` when endpoint changed
- `set_opcua_endpoint_and_status(url, connected)` — bulk update for initial sync

### `api_client.py` (modified)

- `opcua_client_connect(endpoint: str | None = None)` — pass endpoint in body if provided
- `save_opcua_endpoint(url: str)` → `PUT /opcua/endpoint`

### `ports.py` + `mock_service.py` (modified)

- Add `save_opcua_endpoint(url: str) -> dict` to `APIClientPort`
- Update `opcua_client_connect` signature
- Implement in `MockAPIClient`

### HMI close behavior

**No action on close.** The HMI simply exits. No disconnect signal, no cleanup of OPC-UA state. The backend continues operating autonomously.

## Flows

### Flow 1: First use (new project)
1. User creates project → no `opcua_endpoint` in metadata
2. Settings → type endpoint → **Apply** → `PUT /opcua/endpoint` saves to Projeto_Meta
3. **Connect** → `POST /opcua/connect` starts adapter
4. Backend monitors via OPC-UA independently

### Flow 2: HMI restarts with backend running
1. Login → `_check_active_project` → `_sync_opcua_status()`
2. `GET /opcua/status` → `{state: "ONLINE", endpoint: "opc.tcp://..."}`
3. Settings page shows saved endpoint, "Connected", watchdog starts
4. No reconnection needed — backend never disconnected

### Flow 3: Switch project
1. User opens different project
2. `ProjectService.open_project()` reads `opcua_endpoint` from new project
3. If different endpoint: `adapter.set_endpoint(new)` + `adapter.start()`
4. If no endpoint saved: `adapter.stop()`
5. HMI receives response, updates UI

### Flow 4: Change endpoint without Apply
1. User edits endpoint, clicks **Connect** (no Apply)
2. Backend connects to new endpoint temporarily
3. HMI shows "Connected" — but endpoint NOT persisted
4. If backend restarts or project reopened → reverts to saved endpoint

## Error Handling

- Auto-connect fails on project open: adapter enters backoff retry loop (existing behavior). HMI shows "Disconnected" when it queries status.
- `PUT /opcua/endpoint` with invalid URL: return 422 with validation error. Must start with `opc.tcp://`.
- Backend unreachable during `_sync_opcua_status()`: HMI shows "Disconnected", no crash.

## Test Plan

### Backend tests
- `test_opcua_endpoint_save`: `PUT /opcua/endpoint` saves to Projeto_Meta and configures adapter
- `test_opcua_connect_with_endpoint`: `POST /opcua/connect` with endpoint body configures adapter before connecting
- `test_project_open_auto_connect`: Opening a project with saved endpoint triggers adapter start
- `test_project_new_stops_adapter`: Creating new project stops OPC-UA adapter

### HMI tests
- `test_sync_opcua_on_login`: After login, settings page reflects backend OPC-UA status
- `test_apply_saves_endpoint`: Apply with changed endpoint calls `PUT /opcua/endpoint`
- `test_connect_uses_field_value`: Connect passes current field text to backend
- `test_cancel_reverts_endpoint`: Cancel reverts endpoint field to committed value

## Files Modified

### Backend
- `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/opcua_adapter.py` — `set_endpoint()`
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/opcua.py` — `PUT /opcua/endpoint`, modify `POST /opcua/connect`
- `packages/smart_pid_core/src/smart_pid_core/application/project_service.py` — receive adapter, auto-connect on open
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py` — wire adapter to project_service
- `packages/smart_pid_core/src/smart_pid_core/main.py` — pass adapter to ProjectService

### DTOs
- `packages/smart_pid_domain/src/smart_pid_domain/dtos/opcua.py` — `OPCUAConnectRequest`, `OPCUAEndpointRequest`

### HMI
- `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` — `_sync_opcua_status()`, modify Apply/Connect flows
- `packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py` — new signal, sync method
- `packages/smart_pid_hmi/src/smart_pid_hmi/services/api_client.py` — new/modified methods
- `packages/smart_pid_hmi/src/smart_pid_hmi/services/ports.py` — protocol update
- `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py` — mock update

### Tests
- `tests/hmi/pages/test_settings_page.py` — sync and apply tests
- `tests/hmi/test_settings_apply_cancel.py` — endpoint apply/cancel tests
