# Project Upload/Download Design

**Date:** 2026-04-06
**Status:** Implemented
**Scope:** Backend project directory management, upload/download via REST, HMI Welcome Dialog and Settings page rework

## Problem

The current project management assumes HMI and backend share the same filesystem. The HMI uses `QFileDialog` to pick local paths and sends absolute paths to the backend. This breaks when HMI and backend run on different machines and makes project portability (sharing `.spid` files between users) awkward.

## Decision Summary

| Decision | Choice |
|----------|--------|
| Backend manages project directory | `SPID_PROJECTS_DIR` env var, default `~/.smart-pid/projects/` |
| New Project flow | User gives name only, backend creates `.spid` |
| Open Project flow | Backend lists available projects, user picks by name |
| Import flow | HMI uploads `.spid` via multipart to backend |
| Save As / Download | Unified: download active `.spid` from backend, save locally |
| Project list source | Backend (`GET /project/list`), not local app state |
| Startup behavior | Auto-open if backend has active project; Welcome Dialog otherwise |
| Upload size limit | None (rely on framework defaults) |

## Architecture

### Backend: Projects Directory

The backend maintains a managed directory for `.spid` files:

- **Location:** `SPID_PROJECTS_DIR` (env var), default `~/.smart-pid/projects/`
- **Created automatically** on daemon startup if it doesn't exist
- **Convention:** each project is `{name}.spid` inside the directory
- **The project name is the filename stem** — no separate metadata DB for project names

Added to `CoreSettings`:

```python
projects_dir: Path = Path.home() / ".smart-pid" / "projects"
```

### REST API Changes

#### New/Changed Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `GET /project/list` | GET | No | List available projects in the directory |
| `POST /project/new` | POST | Operator+ | Create empty project by name |
| `POST /project/open` | POST | Operator+ | Open existing project by name |
| `POST /project/import` | POST | Operator+ | Upload `.spid` file (multipart) |
| `GET /project/download` | GET | No | Download active project as `.spid` stream |
| `DELETE /project/{name}` | DELETE | Admin | Remove project from directory |
| `GET /project/current` | GET | No | Project info (unchanged) |

#### Removed Endpoints

- `POST /project/save-as` — replaced by `GET /project/download`

#### Request/Response Details

**`GET /project/list`** — Response:

```json
{
  "projects": [
    {"name": "elkem", "controller_count": 3, "size_bytes": 73728},
    {"name": "commissioning", "controller_count": 12, "size_bytes": 245760}
  ]
}
```

Implementation: scans `projects_dir/*.spid`, opens each briefly in read-only mode to count controllers via `SELECT COUNT(*) FROM Controladores`.

**`POST /project/new`** — Request:

```json
{"name": "elkem"}
```

Response: `ProjectResponse` (`name`, `path`, `controller_count`).
- Creates `projects_dir/elkem.spid`
- Calls `reopen()` to switch active project
- Returns 409 if name already exists

**`POST /project/open`** — Request:

```json
{"name": "elkem"}
```

Response: `ProjectResponse`.
- Calls `reopen(projects_dir/elkem.spid)`
- Returns 404 if not found

**`POST /project/import`** — Multipart form:
- Field `file`: the `.spid` file
- Field `name` (optional): override name; defaults to uploaded filename stem

Response: `ProjectResponse`.
- Saves uploaded bytes to `projects_dir/{name}.spid`
- Calls `reopen()` to switch to imported project
- Returns 409 if name already exists

**`GET /project/download`** — Response: `FileResponse` streaming the active `.spid` file.
- Content-Disposition: `attachment; filename="{name}.spid"`
- Read-only: does not change active project

**`DELETE /project/{name}`** — Response: 204 No Content.
- Returns 404 if not found
- Returns 409 if trying to delete the active project

### DTO Changes

**`smart_pid_domain/dtos/project.py`:**

```python
class ProjectCreate(BaseModel):
    name: str  # removed: path

class ProjectOpen(BaseModel):
    name: str  # changed from: path

class ProjectListItem(BaseModel):
    name: str
    controller_count: int = 0
    size_bytes: int = 0

class ProjectListResponse(BaseModel):
    projects: list[ProjectListItem]

class ProjectResponse(BaseModel):
    name: str
    path: str  # now relative, e.g. "elkem.spid"
    controller_count: int = 0

# Removed: ProjectSaveAs
```

### ProjectService Changes

```python
class ProjectService:
    def __init__(self, repo, loop_manager, projects_dir, simulator_adapter=None):
        self._projects_dir = projects_dir  # NEW
        ...

    async def list_projects(self) -> list[ProjectListItem]: ...
    async def new_project(self, name: str) -> ProjectResponse: ...
    async def open_project(self, name: str) -> ProjectResponse: ...  # name, not Path
    async def import_project(self, name: str, data: bytes) -> ProjectResponse: ...
    def download_path(self) -> Path: ...  # returns active .spid path
    async def delete_project(self, name: str) -> None: ...

    # Removed: save_as()
```

Key behaviors:
- `new_project`: creates `projects_dir/{name}.spid`, stops loops/simulator, calls `reopen()`
- `open_project`: resolves `projects_dir/{name}.spid`, stops loops/simulator, calls `reopen()`
- `import_project`: writes bytes to `projects_dir/{name}.spid`, stops loops/simulator, calls `reopen()`
- `list_projects`: scans `projects_dir/*.spid`, opens each read-only to get controller count
- `download_path`: returns `self._repo._db_path` (the active `.spid`)
- `delete_project`: verifies not active, removes file

### Backend Startup (`main.py`)

- Create `settings.projects_dir` if it doesn't exist
- Pass `projects_dir` to `ProjectService`
- Default `db_path` (`project.spid`) becomes the "scratch" project on fresh start

## HMI Changes

### APIClient — New/Changed Methods

```python
def list_projects(self) -> list[dict]: ...
def new_project(self, name: str) -> dict: ...      # removed: path param
def open_project(self, name: str) -> dict: ...      # name, not path
def import_project(self, name: str, file_path: str) -> dict: ...  # multipart upload
def download_project(self, save_path: str) -> None: ...           # stream to file
def delete_project(self, name: str) -> None: ...

# Removed: save_as_project()
```

### MockAPIClient

Update `MockAPIClient` with the same interface changes for test/mock mode.

### AppStateManager

```python
class AppStateManager:
    # last_project stores project NAME (not path)
    # recent_projects removed (source of truth is backend)
    # prune() simplified (no local path checks)
```

`app.json` format:

```json
{
  "last_project_name": "elkem",
  "last_theme": "isa101"
}
```

### Welcome Dialog

Shown **after login** when the backend has no meaningful active project (name is default "project" or similar). Receives project list from backend.

```
┌─────────────────────────────────────┐
│    ⚙ Smart PID Edge Optimizer       │
│       Project Management            │
│                                     │
│  [ New Project ]                    │
│  [ Import from File (.spid) ]       │
│                                     │
│  AVAILABLE PROJECTS                 │
│  ┌─────────────────────────────────┐│
│  │ elkem          (3 loops)        ││
│  │ teste-planta   (0 loops)        ││
│  │ commissioning  (12 loops)       ││
│  └─────────────────────────────────┘│
│                                     │
│           [ Delete Selected ]       │
└─────────────────────────────────────┘
```

Changes vs. current:
- Constructor receives `projects: list[dict]` (from backend) instead of `recent_projects`
- "Open Project" (QFileDialog) replaced by "Import from File"
- "Recent Projects" label becomes "Available Projects"
- New "Delete Selected" button
- `result_action` values: `"new"`, `"open"`, `"import"`
- For "import": `result_path` is the local file path to upload
- For "new": `result_name` is the project name (no path)
- For "open": `result_name` is the project name from list

### Settings Page — Project Section

```
┌ Project ────────────────────────┐
│ Name:        elkem              │
│ Path:        elkem.spid         │
│ Controllers: 3                  │
│                                 │
│ [ New ] [ Open ] [ Download ]   │
│         [ Import ]              │
└─────────────────────────────────┘
```

Changes:
- "Save As" button → "Download" button
- New "Import" button
- "New" and "Open" open the Welcome Dialog (reuse)
- "Download" triggers `GET /project/download` + `QFileDialog.getSaveFileName`
- Signals updated: `project_save_as_requested` → `project_download_requested`; new `project_import_requested`

### MainWindow Startup Flow

```
login_success()
  → GET /project/current
  → if backend has a project in projects_dir active (path starts with projects_dir):
      → update Settings, go to Dashboard
  → else (fresh start with default db_path "project.spid" outside projects_dir):
      → GET /project/list
      → show Welcome Dialog with project list
      → handle result (new/open/import)
```

The `_pending_project_*` fields are removed. Project selection always happens post-login via Welcome Dialog or auto-detection.

### MainWindow Project Operations

**New Project (from Welcome Dialog or Settings):**
1. `POST /project/new {"name": "..."}`
2. Update Settings page
3. Load Dashboard

**Open Project (from Welcome Dialog or Settings):**
1. `POST /project/open {"name": "..."}`
2. Update Settings page
3. Load Dashboard

**Import (from Welcome Dialog or Settings):**
1. `QFileDialog.getOpenFileName` → select local `.spid`
2. `POST /project/import` (multipart upload)
3. Update Settings page
4. Load Dashboard

**Download (from Settings):**
1. `GET /project/download` → receive bytes
2. `QFileDialog.getSaveFileName` → save locally
3. No project switch, no Dashboard reload

**Delete (from Welcome Dialog):**
1. `DELETE /project/{name}`
2. Refresh project list in dialog

## Test Impact

### Tests that change:
- `tests/conftest.py` — fixtures adapt `ProjectService` to use `tmp_path` as `projects_dir`
- API integration tests using project endpoints — adapt DTOs and request shapes
- HMI tests for Settings/Welcome Dialog — adapt signals and flows

### New tests:
- `tests/core/unit/test_project_service.py` — list, new, open, import, download, delete, delete-active-rejects
- `tests/core/integration/test_project_api.py` — REST endpoints including multipart upload, download stream, list, delete-409
- `tests/hmi/dialogs/test_welcome_dialog.py` — adapt for backend project list
- `tests/hmi/pages/test_settings_project.py` — download and import flows

### No impact:
- PID engine, workers, historian, alarm/audit repos
- Telemetry publisher, ZMQ bus
- SQLiteRepository internals (`reopen()` unchanged)

## Migration

On first startup with the new version:
1. Backend creates `SPID_PROJECTS_DIR` if it doesn't exist
2. If the current `db_path` (e.g., `./project.spid`) contains real data, it could be copied to `projects_dir/` — but this is optional and can be done manually by the user via import
3. HMI `app_state.json`: old `last_project` (path) is ignored; field renamed to `last_project_name`; `recent_projects` ignored
