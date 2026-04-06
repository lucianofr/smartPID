# Project Management — Design Spec

**Date:** 2026-04-06
**Status:** Approved
**Scope:** Backend REST API + HMI Settings page + Welcome dialog + app-level user DB

## Overview

Add project lifecycle management (New / Open / Save As) to Smart PID Edge Optimizer. The `.spid` SQLite file is the project file — it contains controllers, alarms, logs, simulator config, and AI models. Users and authentication belong to the application (not the project) and are stored in a separate database.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Backend-Centric | Backend orchestrates project transitions (stop loops, close DB, reopen). Safer for industrial use. |
| UI location | Settings page, "Project" group box at top | Simple, no toolbar/menu changes needed |
| Welcome dialog | Modal on startup when no last project found | First-run experience + recovery when last project file missing |
| Save vs Save As | No "Save" — only "Save As" | SQLite auto-persists all changes. "Save" would be redundant. |
| App state storage | `~/.config/smart-pid/app.json` | Explicit, portable, debuggable. Not QSettings, not env vars. |
| User DB location | Separate SQLite, app-level | Users belong to the application, not the project. Switching projects doesn't affect auth. |
| Simulator persistence | Partial — preset + model params only | Disturbance state is ephemeral, resets on project load |
| First-run behavior | Welcome dialog with New/Open + recent list | No auto-created "Untitled" project |
| Project switch confirmation | Explicit: "This will stop all running loops. Continue?" | Industrial safety — no silent shutdowns |
| Recent projects limit | 5 (FIFO) | Compact list, sufficient for typical usage |
| Settings save/cancel | Explicit Apply/Cancel buttons for editable fields | Industrial apps require deliberate confirmation — no auto-apply |

## 1. UI — Settings Page

### 1.1 Apply/Cancel Pattern for Editable Fields

Currently, settings fields (theme, refresh rate, OPC-UA endpoint) apply changes immediately on edit. This is changed to an **explicit save/cancel** pattern:

- All editable fields are buffered — changes are held locally until the user clicks **Apply** or **Cancel**
- **Apply** — persists all pending changes (emits signals, calls APIs as needed)
- **Cancel** — reverts all fields to their last-applied values
- Buttons are shown at the bottom of the Settings page, right-aligned
- Both buttons are **disabled** when there are no pending changes (clean state)
- When there are unsaved changes and the user navigates away from Settings, show a confirmation: *"You have unsaved changes. Discard?"*

```
┌─ Project ──────────────────────────────────────────────┐
│  (... project controls ...)                            │
└────────────────────────────────────────────────────────┘
┌─ Appearance ───────────────────────────────────────────┐
│  Theme:  [isa101 ▼]                                    │
└────────────────────────────────────────────────────────┘
┌─ Connection ───────────────────────────────────────────┐
│  Server URL:  http://localhost:8000   (read-only)      │
│  ZMQ URL:     tcp://localhost:5555    (read-only)      │
└────────────────────────────────────────────────────────┘
┌─ Performance ──────────────────────────────────────────┐
│  Refresh Rate:  [33 ▲▼] ms                             │
└────────────────────────────────────────────────────────┘
┌─ OPC-UA Server ────────────────────────────────────────┐
│  Endpoint URL:  [opc.tcp://localhost:4840]              │
│  Status: ● Connected    [ Reconnect ]                  │
└────────────────────────────────────────────────────────┘
                              [ Cancel ]  [ Apply ]
```

**Scope of Apply/Cancel:**
- **Settings page**: Appearance (theme), Performance (refresh rate), OPC-UA (endpoint URL). Project buttons (New/Open/Save As) and Reconnect are **immediate actions** — not affected by Apply/Cancel.
- **Simulator page**: Process model parameters (gain, tau1, tau2, dead_time), preset selection, Internal PID parameters (Kp, Ti, Td), PID enable, PID mode. Disturbance buttons (Inject Step, Inject Noise, Clear All) are **immediate actions** — not affected by Apply/Cancel. The existing "Apply Parameters" and "Apply PID Parameters" buttons are replaced by the unified Apply/Cancel at the bottom of the page.

For both pages, the pattern is the same: fields are buffered, Apply commits all pending changes, Cancel reverts, navigating away with unsaved changes prompts confirmation.

### 1.2 Project Group Box

New group box **"Project"** at the top of `SettingsPage`, above "Appearance".

### Layout

```
┌─ Project ──────────────────────────────────────────────┐
│  Name:         Planta Compressores                     │
│  Path:         /home/luciano/projects/compressores.spid│
│  Controllers:  4                                       │
│  ──────────────────────────────────────────────────     │
│  [ New ]  [ Open ]  [ Save As ]                        │
└────────────────────────────────────────────────────────┘
```

### Fields

- **Name** — read-only QLabel, project name from `Projeto_Meta` table
- **Path** — read-only QLabel, full filesystem path of active `.spid`
- **Controllers** — read-only QLabel, count from `GET /project/current`

### Buttons

- **New** — opens QInputDialog (project name) then QFileDialog (save path). Calls `POST /project/new`.
- **Open** — opens QFileDialog (filter `*.spid`). Calls `POST /project/open`.
- **Save As** — opens QFileDialog (save path). Calls `POST /project/save-as`.

### Behavior

- **New / Open**: show QMessageBox confirmation: *"This will stop all running loops. Continue?"* before calling the API.
- **Save As**: no confirmation needed — does not interrupt operation.
- After successful New/Open/Save As: update labels (name, path, controllers), update `app.json`.
- On API error: show QMessageBox with error detail from backend response.

### Signals

- `project_changed(name: str, path: str)` — emitted after successful project switch. MainWindow listens to update title bar or other UI elements.

## 2. Welcome Dialog

Modal `QDialog` shown on startup when no valid last project is found.

### When it appears

1. HMI reads `~/.config/smart-pid/app.json`
2. If `last_project` exists AND the `.spid` file exists on disk → skip dialog, open project directly
3. If `last_project` is missing, empty, or file doesn't exist → show welcome dialog
4. If `app.json` doesn't exist (first run) → show welcome dialog with empty recent list

### Layout

```
┌──────────────────────────────────────────┐
│       ⚙ Smart PID Edge Optimizer         │
│          Project Management              │
│                                          │
│        ┌────────────────────┐            │
│        │   📄 New Project   │            │
│        └────────────────────┘            │
│        ┌────────────────────┐            │
│        │   📂 Open Project  │            │
│        └────────────────────┘            │
│                                          │
│  RECENT PROJECTS                         │
│  ┌──────────────────────────────────┐    │
│  │ Planta Compressores    4 loops   │    │
│  │ /home/.../compressores.spid      │    │
│  ├──────────────────────────────────┤    │
│  │ Teste Bancada          2 loops   │    │
│  │ /home/.../bancada.spid           │    │
│  └──────────────────────────────────┘    │
│                                   v2.0.0 │
└──────────────────────────────────────────┘
```

### Behavior

- **New Project** → same flow as Settings New button (name input + file dialog)
- **Open Project** → same flow as Settings Open button (file dialog)
- **Click recent project** → equivalent to Open (calls `POST /project/open`)
- Dialog is **modal** — blocks main window until a project is selected
- Recent projects that no longer exist on disk are filtered out (and removed from `app.json`)
- Controller count for recent projects is stored in `app.json` (cached from last open)

## 3. Backend: ProjectService and API Routes

### ProjectService

New service in `smart_pid_core/application/project_service.py`.

Orchestrates project transitions:

```
stop_all_loops → stop_simulator → close_db → create_or_open_spid → reopen_db → return_info
```

#### Methods

- `get_current() -> ProjectResponse` — returns name (from `Projeto_Meta`), path, controller count
- `new_project(name: str, path: Path) -> ProjectResponse`:
  1. Validate path (writable, doesn't already exist or confirm overwrite)
  2. `LoopManager.stop_all()`
  3. `SimulatorAdapter.stop()` (if running)
  4. `SQLiteRepository.close()`
  5. Create new `.spid` file at path
  6. Open new file, execute DDL (all tables)
  7. Insert `Projeto_Meta` rows: `("nome", name)`, `("criado_em", timestamp)`
  8. Update `CoreSettings.db_path`
  9. Return `ProjectResponse`
- `open_project(path: Path) -> ProjectResponse`:
  1. Validate path exists and is a valid `.spid` (check for expected tables)
  2. Steps 2-4 same as new_project
  3. Open existing `.spid`
  4. Load simulator config from `Configuracao_Simulador` if present
  5. Update `CoreSettings.db_path`
  6. Return `ProjectResponse`
- `save_as(path: Path) -> ProjectResponse`:
  1. Validate target path (writable, not same as current)
  2. Pause historian batch writes
  3. `shutil.copy2(current_path, new_path)`
  4. Close current DB, open copy at new path
  5. Resume historian
  6. Update `CoreSettings.db_path`
  7. Return `ProjectResponse`

#### Error Handling

- Invalid path / no permissions → raise `SmartPIDInfraError` → 400
- Corrupted/incompatible `.spid` on Open → raise `SmartPIDInfraError` → 422
- Failure mid-transition → attempt to reopen previous project as fallback, log error

### API Routes

New router in `smart_pid_core/adapters/inbound/api/routers/project.py`.

| Method | Route | Request DTO | Response DTO | Description |
|--------|-------|-------------|--------------|-------------|
| `GET` | `/project/current` | — | `ProjectResponse` | Info about active project |
| `POST` | `/project/new` | `ProjectCreate` | `ProjectResponse` | Create and switch to new project |
| `POST` | `/project/open` | `ProjectOpen` | `ProjectResponse` | Open existing .spid |
| `POST` | `/project/save-as` | `ProjectSaveAs` | `ProjectResponse` | Copy current project to new path |

All routes require authentication (JWT).

### Existing DTOs (already in domain)

```python
# smart_pid_domain/dtos/project.py — already exists
class ProjectCreate(BaseModel):
    name: str
    path: str

class ProjectOpen(BaseModel):
    path: str

class ProjectSaveAs(BaseModel):
    path: str

class ProjectResponse(BaseModel):
    name: str
    path: str
    controller_count: int
```

## 4. Database Changes

### New table: `Projeto_Meta`

Stores project-level metadata inside the `.spid` file.

```sql
CREATE TABLE IF NOT EXISTS Projeto_Meta (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
```

Initial rows on project creation:
- `("nome", "<project name>")`
- `("criado_em", "<ISO timestamp>")`

### New table: `Configuracao_Simulador`

Persists simulator process model configuration per controller.

```sql
CREATE TABLE IF NOT EXISTS Configuracao_Simulador (
    controlador_id INTEGER PRIMARY KEY REFERENCES Controladores(id) ON DELETE CASCADE,
    preset TEXT NOT NULL DEFAULT 'fopdt_default',
    gain REAL NOT NULL,
    tau1 REAL NOT NULL,
    tau2 REAL NOT NULL,
    dead_time REAL NOT NULL,
    pid_enabled INTEGER NOT NULL DEFAULT 0,
    pid_kp REAL NOT NULL DEFAULT 1.0,
    pid_ti REAL NOT NULL DEFAULT 10.0,
    pid_td REAL NOT NULL DEFAULT 0.0,
    pid_mode INTEGER NOT NULL DEFAULT 0
);
```

- Saved when simulator params are changed via API
- Loaded on project open (populates `SimulatorAdapter` in-memory state)
- Internal PID parameters (Kp, Ti, Td), enable flag, and mode are persisted — restored on project open
- Disturbance state (step/noise) and auto-excitation state are NOT persisted — always start clean

### User DB separation

`Usuarios` table moves OUT of the `.spid` file into a dedicated app-level SQLite:

- **Path**: configurable via `CoreSettings.users_db_path`, default `~/.config/smart-pid/users.db`
- **Schema**: same `Usuarios` DDL, same `UserRepository` — only the DB connection changes
- **Auth flow unchanged**: JWT secret remains in `CoreSettings`, login/token endpoints unchanged
- **Migration**: on backend startup, if `users.db` doesn't exist but the active `.spid` has a `Usuarios` table, copy all rows to the new `users.db`. The `Usuarios` table remains in old `.spid` files (not deleted) but is ignored by new code. No migration prompt — fully automatic and idempotent.
- **Impact**: switching projects no longer affects authentication. No re-login needed.

## 5. App State: `~/.config/smart-pid/app.json`

Managed entirely by the HMI. The backend has no knowledge of this file.

### Schema

```json
{
  "last_project": "/absolute/path/to/project.spid",
  "recent_projects": [
    {
      "name": "Planta Compressores",
      "path": "/absolute/path/to/compressores.spid",
      "controller_count": 4
    }
  ]
}
```

### Rules

- Maximum **5** entries in `recent_projects` (FIFO — oldest removed when full)
- Updated on every successful New/Open/Save As
- `last_project` always points to the currently active project
- On startup, entries pointing to non-existent files are pruned
- `controller_count` is cached from the last `ProjectResponse` — used to display in welcome dialog without querying backend
- File created automatically on first successful project operation
- HMI reads/writes via a simple `AppStateManager` class (JSON load/save with `pathlib`)

### HMISettings changes

New optional field:
- `app_state_path: Path = ~/.config/smart-pid/app.json` — allows override for testing

## 6. CoreSettings Changes

New fields in `CoreSettings`:

```python
users_db_path: Path = Path("~/.config/smart-pid/users.db").expanduser()
```

The existing `db_path` field becomes mutable at runtime (updated by `ProjectService` on project switch).

## 7. Startup Sequence (revised)

```
1. Backend starts
   ├── CoreSettings loaded (env vars)
   ├── UserRepository opens users_db_path (app-level, always)
   ├── SQLiteRepository opens db_path (may be default or overridden)
   └── API server starts, awaits connections

2. HMI starts
   ├── HMISettings loaded
   ├── AppStateManager reads app.json
   ├── If last_project exists on disk:
   │   ├── POST /project/open {path: last_project}
   │   ├── On success → proceed to login (ConnectionPage)
   │   └── On failure → show welcome dialog
   └── If no last_project:
       └── Show welcome dialog (modal)
           ├── New → QInputDialog + QFileDialog → POST /project/new
           ├── Open → QFileDialog → POST /project/open
           └── Recent click → POST /project/open

3. After project loaded
   ├── User logs in (ConnectionPage)
   ├── MainWindow shows with project info
   └── Normal operation
```

## 8. File Structure (new/modified files)

### New files
- `packages/smart_pid_core/src/smart_pid_core/application/project_service.py` — ProjectService
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/project.py` — API routes
- `packages/smart_pid_hmi/src/smart_pid_hmi/services/app_state.py` — AppStateManager
- `packages/smart_pid_hmi/src/smart_pid_hmi/dialogs/welcome_dialog.py` — WelcomeDialog

### Modified files
- `packages/smart_pid_core/src/smart_pid_core/config.py` — add `users_db_path`
- `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py` — add DDL for `Projeto_Meta` + `Configuracao_Simulador`, add `close()` and `reopen(path)` methods
- `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py` — use separate DB connection (from `users_db_path`)
- `packages/smart_pid_core/src/smart_pid_core/main.py` — wire ProjectService, register project router
- `packages/smart_pid_hmi/src/smart_pid_hmi/config.py` — add `app_state_path`
- `packages/smart_pid_hmi/src/smart_pid_hmi/pages/settings_page.py` — add Project group box
- `packages/smart_pid_hmi/src/smart_pid_hmi/main.py` — integrate welcome dialog, app state, project signals

## 9. Testing Strategy

- **Unit tests**: ProjectService (mock LoopManager, SQLiteRepo, SimulatorAdapter)
- **Integration tests**: API routes for `/project/*` (create temp `.spid` files, verify transitions)
- **HMI tests**: AppStateManager (JSON read/write/prune), WelcomeDialog (widget tests)
- **Edge cases**: open corrupted file, open while loops running, save-as to read-only path, concurrent access
