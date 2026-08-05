# Fatia 7: Settings + Connection + Projects — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Deliver the Web HMI "admin/config" surface for the mono-user Smart PID v2 system: a **Settings** page (app/operation preferences), an **OPC connection** page (endpoint config + connect/disconnect + tag browse/search; acquisition is continuous, no acquisition start/stop), and `.spid` **project management** (list/new/open/import-upload/download/delete) with a **welcome dialog** shown post-login that lists backend projects. Every restricted route requires the single authenticated admin (**401** without a token; **no** 403-by-role). No user CRUD, no RBAC, no user-management page.

**Architecture:** Frontend-only React feature work plus a thin OpenAPI-types refresh. The page surfaces are added under `src/pages/` and `src/features/fatia7/` of the existing `packages/smart_pid_web/` scaffold (created by Fatia 0+1 — see Global Constraints precondition). All backend calls go through the canonical `api/client.ts` fetch wrapper (injects `Authorization: Bearer`, throws `ApiError` on `!ok`) and TanStack Query v5 hooks. The backend exposes the routes already (`routers/opcua`, `routers/project`, `routers/system`, `routers/auth`); this fatia writes **no new backend feature code**. It assumes the security-hardening branch (auth on all `/project/*`, path sanitization, 413 upload cap) is applied (GAP-7a precondition) and the TD-007 single-admin collapse of role gates is handled outside this plan.

**Tech Stack:** React 18 + Vite 5 + TypeScript 5 (strict); TanStack Query v5 (server state); native `fetch` via `api/client.ts`; Vitest + @testing-library/react (unit/hook/component); Playwright (e2e); `openapi-typescript` for generated types; CSS design tokens (no hardcoded hex). Backend (read-only reference): Python 3.13, FastAPI, pydantic v2.

**Specs:**
- `docs/superpowers/specs/2026-06-18-web-fatia7-settings-users-projects-design.md` (this fatia — NOTE: its RBAC/user-management content is **overridden** to mono-user by the contract below).
- `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md` §10 "Fatia 7" (UI authority).
- `docs/superpowers/specs/2026-06-18-web-hmi-react-migration-design.md` (umbrella).
- `docs/superpowers/plans/_web-hmi-foundation-contract.md` (authoritative contract).
- `docs/superpowers/plans/_web-hmi-backend-surface.md` (real backend surface).

---

## Global Constraints

Inherited verbatim from `_web-hmi-foundation-contract.md` §9 — every task obeys these:

- **Backend:** bind `127.0.0.1` (config `SPID_API_HOST`); serve SPA via `app.mount('/', StaticFiles(directory=dist, html=True))` mounted **after** routers (single-origin → no CORS in prod); dev CORS allowlist `http://127.0.0.1:5173` only; add security headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, basic CSP). Validate `Origin` on `/ws/realtime`. *(No new backend code in this fatia; listed for inheritance.)*
- **RealtimeWS:** it is the **2nd EventBus consumer**, structurally analogous to `TelemetryPublisher`. The bus `recv()` is **blocking ZMQ** — a naive `await sub.recv()` freezes the daemon loop. Use `zmq.asyncio` **or** a single shared consumer in `run_in_executor` (single-flight) that fans out to all clients. **Never** a recv-loop per client; **never** concurrent recv on the same socket. Coalesce last-value only for `status`/`stats`; `alarm`/`ai`/system are **lossless bounded** (on overflow, close the socket so the client re-syncs via REST). `ConnectionManager` with async lock + resilient broadcast. *(WS is non-essential for this config/admin fatia; listed for inheritance.)*
- **TDD (mandatory):** failing test → run it red → minimal impl → run it green → commit. Bite-sized steps (2–5 min each), checkbox `- [ ]` syntax.
- **Branching (inviolable):** this fatia is implemented on a **new dedicated branch from `main`** named **`feat/web-fatia7-settings-connection-projects`**. Never reuse another task's branch, never commit to `main` directly, never touch `feat/windows-installers`. Merge to `main` only with explicit user approval.
- **Subagents:** `model: opus` (project rule).
- **Commits:** conventional (`feat(web): …`, `fix(web): …`); **no attribution trailers**.
- **Python toolchain:** Python 3.13, `uv`. Lint `uv run --with ruff ruff check .` (line-length 100). Types `uv run mypy packages/` (baseline ~540 errors — must not increase). Tests `uv run pytest`. uv fallback in Flatpak: `/home/luciano/.var/app/com.visualstudio.code/bin/uv`.
- **Frontend toolchain:** `npm` inside `packages/smart_pid_web/`. `npm run test` (Vitest), `npm run test:e2e` (Playwright), `npm run build` (Vite), `npm run gen:api`.
- **Known-environmental:** 3 pre-existing failures in `tests/.../test_opcua_endpoint.py::TestProjectServiceOPCUA` (Py3.14 `asyncio.get_event_loop()`) are NOT regressions — do not "fix" them inside a fatia.
- **UI specs upkeep:** any UI change updates `docs/smartPIDv2.md` + the relevant `docs/identidade_visual_*.md`; the design-system spec is the web UI authority.
- **GateGuard:** the first `Write` of each new file may be blocked by a PreToolUse hook — present the facts (no importers yet / no API or schema change / instructed to create) and retry the same Write, or the operator may `export ECC_GATEGUARD=off`.

### Mono-user / no-RBAC override (contract §1 — binding for this fatia)

- **Single admin login. No user CRUD, no role-based UI gating, no `routers/users` in the target system (TD-007 removes it).** Auth is mandatory on every restricted endpoint via a single dependency `require_authenticated_admin`. Wherever the Fatia 7 spec or umbrella mention RBAC / `require_operator|supervisor|admin` / user management, this plan substitutes the single-admin model.
- **Negative auth tests assert 401 when unauthenticated** (NOT 403-by-role). The spec's "negative RBAC tests (assert 403 by role)" become "assert 401 without a JWT vs 200 with the admin token".
- **Dropped entirely:** user-management page, user CRUD (`routers/users` consumption), role-based UI gating.
- **Credential boundary preserved:** admin credentials live in `users.db`, **never** inside `.spid` projects. A test asserts a project export contains no credential tables.

### Preconditions handled OUTSIDE this plan

- **GAP-7a — `/project/*` auth + hardening.** In this worktree's branch `routers/project.py` endpoints are **unauthenticated** (no `Depends`), because the auth fix lives on `fix/backend-security-hardening` (not merged here). This plan **ASSUMES that branch is applied**: every project route gains the single-admin dependency, `_safe_project_path` path-traversal sanitization, and a 50 MB `.spid` upload cap → HTTP 413. This fatia **does not re-implement** any of it. Task 0 records this as a precondition check.
- **TD-007 — single-admin gate collapse.** The role-ladder dependencies (`require_operator`/`require_supervisor`/`require_admin`, `get_current_user`) collapse to one `require_authenticated_admin`. If that collapse is not yet merged when this fatia runs, treat it as a precondition handled outside this plan; the frontend depends only on the binary 401-vs-200 contract, so it is robust to either backend shape.

### Confirmed-from-code facts (do not re-derive; do not invent endpoints)

OPC-UA (`routers/opcua.py`, prefix `/opcua`):
| Method | Path | Body / Query | Returns |
|--------|------|--------------|---------|
| GET | `/opcua/status` | — | `OPCUAStatusResponse {state: ConnectionState, endpoint: str}` |
| PUT | `/opcua/endpoint` | `OPCUAEndpointRequest {endpoint: str}` (must start `opc.tcp://`; else **422**) | `OPCUAStatusResponse` |
| POST | `/opcua/connect` | `OPCUAConnectRequest {endpoint?: str \| null}` (optional) | `OPCUAStatusResponse` |
| POST | `/opcua/disconnect` | — | `OPCUAStatusResponse` |
| GET | `/opcua/browse/{node_id:path}` | path param `node_id` | `OPCUABrowseResponse {parent_node_id, children: OPCUANodeInfo[]}` |
| GET | `/opcua/search` | query `q` (1–200 chars) | `OPCUASearchResponse {query, results: OPCUANodeInfo[]}` |

`OPCUANodeInfo {node_id: str, display_name: str, node_class: str}`. `ConnectionState ∈ {OFFLINE, CONNECTING, ONLINE, RECONNECTING}`. Browse/search may return **503** when OPC adapter is not connected; **404** when running in simulator mode (adapter absent).

Project (`routers/project.py`, prefix `/project`):
| Method | Path | Body / Query | Returns |
|--------|------|--------------|---------|
| GET | `/project/current` | — | `ProjectResponse {name, path, controller_count}` |
| GET | `/project/list` | — | `ProjectListResponse {projects: ProjectListItem[]}` |
| POST | `/project/new` | `ProjectCreate {name: str}` (409 if exists) | `ProjectResponse` |
| POST | `/project/open` | `ProjectOpen {name: str}` (404 if missing) | `ProjectResponse` |
| POST | `/project/import` | multipart: `file` (UploadFile) + `name` (Form, optional) — 409 if exists, **413** if > cap | `ProjectResponse` |
| GET | `/project/download` | — | `FileResponse` (`application/octet-stream`, `.spid`) — **leave un-typed (stream)** |
| DELETE | `/project/{name}` | path param `name` | **204** No Content |

`ProjectListItem {name: str, controller_count: int, size_bytes: int}`. `ProjectResponse {name: str, path: str, controller_count: int}`.

Auth (`routers/auth.py`, prefix `/auth`): `POST /auth/login` (`LoginRequest {username, password}` → `TokenResponse {access_token, token_type}`), `POST /auth/refresh`, `POST /auth/register` (admin-gated). **There is NO `/auth/change-password` endpoint.** Admin password-change UI is therefore **out-of-scope** for this fatia (see Task 1 Step note); revisit if a backend endpoint is added.

System (`routers/system.py`, prefix `/system`): `GET /system/status` → `SystemStatusResponse {status, uptime_s, active_controllers, bus_active, api_version}` — **no auth** (health check).

---

## File Structure

This fatia ADDs the following under the existing `packages/smart_pid_web/` scaffold (Fatia 0+1). It **MUST NOT** redefine canonical files (`api/client.ts`, `auth/AuthContext.tsx`, `components/shell/*`, `realtime/*`, `theme/*`).

```
packages/smart_pid_web/
  src/
    api/
      generated/openapi.ts            # REGENERATED via `npm run gen:api` (Task 0)
    features/
      fatia7/
        useProjects.ts                # TanStack Query hooks: list/current/new/open/import/download/delete
        useOpcua.ts                   # hooks: status/endpoint(save)/connect/disconnect/browse/search
        useSettings.ts                # local app/operation prefs (localStorage-backed)
        projectApi.ts                 # thin typed fns over api/client for /project/*
        opcuaApi.ts                   # thin typed fns over api/client for /opcua/*
        settingsTypes.ts              # AppPreferences type + defaults
    components/
      fatia7/
        SettingsForm.tsx              # two-column preferences form (design-system §10)
        ConnectionPanel.tsx           # endpoint field + Connect/Disconnect + status dot
        TagBrowser.tsx                # browsable tree (GET /browse) + search box (GET /search)
        ProjectList.tsx               # rows/cards: name, loops, size + per-item download/delete
        ProjectImportDropzone.tsx     # multipart upload w/ progress
        WelcomeDialog.tsx             # post-login modal: lists backend projects + New/Import/Open
    pages/
      SettingsPage.tsx                # route /settings — composes SettingsForm
      ConnectionPage.tsx              # route /connection — composes ConnectionPanel + TagBrowser
      ProjectsPage.tsx                # route /projects — composes ProjectList + ProjectImportDropzone
  tests/                              # *.test.ts(x) colocated or here (Vitest)
  e2e/
    fatia7-connection.spec.ts         # configure endpoint + connect + browse/search
    fatia7-projects.spec.ts           # import then open a .spid; create/delete project
    fatia7-auth-negative.spec.ts      # 401 on a protected route when unauthenticated
```

Backend tests this fatia ADDs (consumption/contract level — no feature code):
```
tests/core/integration/test_project_auth_required.py        # 401 without JWT on /project/*
tests/core/integration/test_project_export_no_credentials.py # exported .spid has no user/credential tables
```

---

### Task 0: Branch, precondition check, OpenAPI types refresh

**Files:**
- Create branch `feat/web-fatia7-settings-connection-projects`.
- Modify (generated): `packages/smart_pid_web/src/api/generated/openapi.ts`.

**Interfaces:** Pulls typed request/response shapes for `/opcua/*`, `/project/*`, `/system/*`, `/auth/*` into the generated OpenAPI module so feature hooks import real types.

- [ ] **Step 1: Create the dedicated branch from `main`**

```bash
git -C /tmp/web-hmi-plans-wt fetch origin
git -C /tmp/web-hmi-plans-wt switch -c feat/web-fatia7-settings-connection-projects origin/main
```
Expected: `Switched to a new branch 'feat/web-fatia7-settings-connection-projects'`.

- [ ] **Step 2: Verify GAP-7a precondition (project routes are auth-gated in the running backend)**

This is a read-only confirmation, not an implementation. Confirm the security-hardening branch is applied (project routes carry the single-admin dependency and the 413 cap). Inspect the live router:

```bash
grep -nE "Depends\(|require_authenticated_admin|require_admin|_safe_project_path|413|max_upload_bytes" \
  packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/project.py
```
Expected: at least one auth `Depends(...)` per state-changing route and a reference to the upload cap. **If the output is empty** (hardening not merged in this worktree), record it: the frontend still targets the documented 401-vs-200 contract, and the backend auth integration tests in Task 6 will be `xfail`-marked with a comment pointing at `fix/backend-security-hardening` until merged. Do NOT add auth dependencies here — that is precondition work owned elsewhere.

- [ ] **Step 3: Regenerate OpenAPI types**

With the backend importable (or its `openapi.json` available), run:
```bash
cd packages/smart_pid_web && npm run gen:api
```
Expected: `src/api/generated/openapi.ts` updates to include `paths["/opcua/endpoint"]`, `paths["/project/import"]`, `paths["/project/{name}"]`, `paths["/opcua/browse/{node_id}"]`, and the `OPCUANodeInfo` / `ProjectListItem` / `ProjectResponse` / `OPCUAStatusResponse` component schemas. Verify:
```bash
grep -E "OPCUANodeInfo|ProjectListItem|ProjectResponse|OPCUAStatusResponse|/project/import|/opcua/browse" \
  src/api/generated/openapi.ts | head
```
Expected: non-empty matches for each. (Do not hand-edit the generated file.)

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_web/src/api/generated/openapi.ts
git commit -m "chore(web): regen OpenAPI types for fatia7 (opcua/project/system) + branch setup"
```

---

### Task 1: App preferences model + `useSettings` hook (Settings data layer)

**Files:**
- Create: `packages/smart_pid_web/src/features/fatia7/settingsTypes.ts`
- Create: `packages/smart_pid_web/src/features/fatia7/useSettings.ts`
- Test: `packages/smart_pid_web/src/features/fatia7/useSettings.test.ts`

**Interfaces:**
```ts
export interface AppPreferences {
  trendWindowSeconds: number;   // sliding-window default for trends
  numberDecimals: number;       // tabular number precision
  confirmDestructive: boolean;  // confirm on delete/disconnect
}
export const DEFAULT_PREFERENCES: AppPreferences;
export function useSettings(): {
  preferences: AppPreferences;
  setPreference<K extends keyof AppPreferences>(key: K, value: AppPreferences[K]): void;
  reset(): void;
};
```
Preferences are **app/operation** preferences only. Theme is **out of scope here** (handled in Fatia 8). Admin password change is **out of scope** (no backend endpoint — see Confirmed-from-code facts). Persisted in `localStorage` under key `spid.preferences`; immutable updates (never mutate the stored object).

- [ ] **Step 1: Write the failing test**

```ts
// packages/smart_pid_web/src/features/fatia7/useSettings.test.ts
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DEFAULT_PREFERENCES, useSettings } from "./useSettings";

afterEach(() => localStorage.clear());

describe("useSettings", () => {
  it("returns defaults when nothing is persisted", () => {
    const { result } = renderHook(() => useSettings());
    expect(result.current.preferences).toEqual(DEFAULT_PREFERENCES);
  });

  it("persists a changed preference immutably and reloads it", () => {
    const first = renderHook(() => useSettings());
    const before = first.result.current.preferences;
    act(() => first.result.current.setPreference("numberDecimals", 4));
    expect(first.result.current.preferences.numberDecimals).toBe(4);
    // original object not mutated
    expect(before.numberDecimals).toBe(DEFAULT_PREFERENCES.numberDecimals);
    // survives a remount (read back from localStorage)
    const second = renderHook(() => useSettings());
    expect(second.result.current.preferences.numberDecimals).toBe(4);
  });

  it("reset() restores defaults", () => {
    const { result } = renderHook(() => useSettings());
    act(() => result.current.setPreference("confirmDestructive", false));
    act(() => result.current.reset());
    expect(result.current.preferences).toEqual(DEFAULT_PREFERENCES);
  });
});
```

- [ ] **Step 2: Run it red**

Run: `cd packages/smart_pid_web && npm run test -- useSettings`
Expected: FAIL — `Cannot find module './useSettings'`.

- [ ] **Step 3: Implement `settingsTypes.ts`**

```ts
// packages/smart_pid_web/src/features/fatia7/settingsTypes.ts
export interface AppPreferences {
  trendWindowSeconds: number;
  numberDecimals: number;
  confirmDestructive: boolean;
}

export const DEFAULT_PREFERENCES: AppPreferences = {
  trendWindowSeconds: 120,
  numberDecimals: 2,
  confirmDestructive: true,
};

export const PREFERENCES_KEY = "spid.preferences";
```

- [ ] **Step 4: Implement `useSettings.ts`**

```ts
// packages/smart_pid_web/src/features/fatia7/useSettings.ts
import { useCallback, useState } from "react";
import {
  AppPreferences,
  DEFAULT_PREFERENCES,
  PREFERENCES_KEY,
} from "./settingsTypes";

function load(): AppPreferences {
  try {
    const raw = localStorage.getItem(PREFERENCES_KEY);
    if (!raw) return DEFAULT_PREFERENCES;
    return { ...DEFAULT_PREFERENCES, ...(JSON.parse(raw) as Partial<AppPreferences>) };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function useSettings() {
  const [preferences, setPreferences] = useState<AppPreferences>(load);

  const setPreference = useCallback(
    <K extends keyof AppPreferences>(key: K, value: AppPreferences[K]) => {
      setPreferences((prev) => {
        const next = { ...prev, [key]: value };
        localStorage.setItem(PREFERENCES_KEY, JSON.stringify(next));
        return next;
      });
    },
    [],
  );

  const reset = useCallback(() => {
    localStorage.removeItem(PREFERENCES_KEY);
    setPreferences(DEFAULT_PREFERENCES);
  }, []);

  return { preferences, setPreference, reset };
}

export { DEFAULT_PREFERENCES };
```

- [ ] **Step 5: Run it green**

Run: `cd packages/smart_pid_web && npm run test -- useSettings`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_web/src/features/fatia7/settingsTypes.ts \
        packages/smart_pid_web/src/features/fatia7/useSettings.ts \
        packages/smart_pid_web/src/features/fatia7/useSettings.test.ts
git commit -m "feat(web): app preferences model + useSettings hook (fatia7 settings)"
```

---

### Task 2: SettingsForm + SettingsPage

**Files:**
- Create: `packages/smart_pid_web/src/components/fatia7/SettingsForm.tsx`
- Create: `packages/smart_pid_web/src/pages/SettingsPage.tsx`
- Test: `packages/smart_pid_web/src/components/fatia7/SettingsForm.test.tsx`

**Interfaces:** `SettingsForm` renders a two-column preferences form (design-system §10: section headers with hairline rule, design-system toggles/selects, tabular alignment) bound to `useSettings`. `SettingsPage` composes it inside the app shell content area. No theme control (Fatia 8); no admin password change (no backend endpoint).

- [ ] **Step 1: Write the failing test**

```tsx
// packages/smart_pid_web/src/components/fatia7/SettingsForm.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, afterEach } from "vitest";
import { SettingsForm } from "./SettingsForm";

afterEach(() => localStorage.clear());

describe("SettingsForm", () => {
  it("renders the preference controls", () => {
    render(<SettingsForm />);
    expect(screen.getByLabelText(/number decimals/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/trend window/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm destructive/i)).toBeInTheDocument();
  });

  it("updates a preference when the user edits it", () => {
    render(<SettingsForm />);
    const decimals = screen.getByLabelText(/number decimals/i) as HTMLInputElement;
    fireEvent.change(decimals, { target: { value: "3" } });
    expect(decimals.value).toBe("3");
    expect(JSON.parse(localStorage.getItem("spid.preferences")!).numberDecimals).toBe(3);
  });

  it("does NOT render any admin password or user-management control", () => {
    render(<SettingsForm />);
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/manage users/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it red**

Run: `cd packages/smart_pid_web && npm run test -- SettingsForm`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `SettingsForm.tsx`**

```tsx
// packages/smart_pid_web/src/components/fatia7/SettingsForm.tsx
import { useSettings } from "../../features/fatia7/useSettings";

export function SettingsForm() {
  const { preferences, setPreference, reset } = useSettings();
  return (
    <form className="settings-form" aria-label="Application preferences">
      <section className="settings-section">
        <h2 className="settings-section__title">Display</h2>
        <div className="settings-row">
          <label htmlFor="numberDecimals">Number decimals</label>
          <input
            id="numberDecimals"
            type="number"
            min={0}
            max={6}
            value={preferences.numberDecimals}
            onChange={(e) => setPreference("numberDecimals", Number(e.target.value))}
          />
        </div>
        <div className="settings-row">
          <label htmlFor="trendWindow">Trend window (seconds)</label>
          <input
            id="trendWindow"
            type="number"
            min={10}
            max={3600}
            value={preferences.trendWindowSeconds}
            onChange={(e) => setPreference("trendWindowSeconds", Number(e.target.value))}
          />
        </div>
      </section>
      <section className="settings-section">
        <h2 className="settings-section__title">Operation</h2>
        <div className="settings-row">
          <label htmlFor="confirmDestructive">Confirm destructive actions</label>
          <input
            id="confirmDestructive"
            type="checkbox"
            checked={preferences.confirmDestructive}
            onChange={(e) => setPreference("confirmDestructive", e.target.checked)}
          />
        </div>
      </section>
      <button type="button" className="btn-secondary" onClick={reset}>
        Reset to defaults
      </button>
    </form>
  );
}
```

- [ ] **Step 4: Implement `SettingsPage.tsx`**

```tsx
// packages/smart_pid_web/src/pages/SettingsPage.tsx
import { SettingsForm } from "../components/fatia7/SettingsForm";

export default function SettingsPage() {
  return (
    <div className="page page--settings">
      <header className="page__header">
        <h1>Settings</h1>
      </header>
      <SettingsForm />
    </div>
  );
}
```

- [ ] **Step 5: Run it green**

Run: `cd packages/smart_pid_web && npm run test -- SettingsForm`
Expected: PASS (3 tests).

- [ ] **Step 6: Register the `/settings` route**

Add to the route table in `src/App.tsx` (canonical file — append a `<Route>`, do not restructure):
```tsx
// inside <RequireAuth> route group
<Route path="/settings" element={<SettingsPage />} />
```
with `const SettingsPage = lazy(() => import("./pages/SettingsPage"));` (match the file's existing lazy-import style).

- [ ] **Step 7: Verify build + commit**

Run: `cd packages/smart_pid_web && npm run build`
Expected: build succeeds, no TS errors.
```bash
git add packages/smart_pid_web/src/components/fatia7/SettingsForm.tsx \
        packages/smart_pid_web/src/components/fatia7/SettingsForm.test.tsx \
        packages/smart_pid_web/src/pages/SettingsPage.tsx \
        packages/smart_pid_web/src/App.tsx
git commit -m "feat(web): settings page with app/operation preferences (fatia7)"
```

---

### Task 3: OPC connection data layer — `opcuaApi.ts` + `useOpcua.ts`

**Files:**
- Create: `packages/smart_pid_web/src/features/fatia7/opcuaApi.ts`
- Create: `packages/smart_pid_web/src/features/fatia7/useOpcua.ts`
- Test: `packages/smart_pid_web/src/features/fatia7/opcuaApi.test.ts`

**Interfaces:**
```ts
export interface OpcuaStatus { state: string; endpoint: string; }   // ConnectionState string
export interface OpcuaNode { node_id: string; display_name: string; node_class: string; }
export const opcuaApi: {
  getStatus(): Promise<OpcuaStatus>;
  saveEndpoint(endpoint: string): Promise<OpcuaStatus>;     // PUT /opcua/endpoint
  connect(endpoint?: string): Promise<OpcuaStatus>;         // POST /opcua/connect
  disconnect(): Promise<OpcuaStatus>;                       // POST /opcua/disconnect
  browse(nodeId: string): Promise<{ parent_node_id: string; children: OpcuaNode[] }>;
  search(q: string): Promise<{ query: string; results: OpcuaNode[] }>;
};
// TanStack Query hooks
export function useOpcuaStatus(): UseQueryResult<OpcuaStatus>;
export function useSaveEndpoint(): UseMutationResult<OpcuaStatus, ApiError, string>;
export function useConnect(): UseMutationResult<OpcuaStatus, ApiError, string | undefined>;
export function useDisconnect(): UseMutationResult<OpcuaStatus, ApiError, void>;
export function useBrowse(nodeId: string | null): UseQueryResult<{ children: OpcuaNode[] }>;
export function useSearch(q: string): UseQueryResult<{ results: OpcuaNode[] }>;
```
`browse` URL-encodes `nodeId` into the `{node_id:path}` segment. **No acquisition start/stop** — acquisition is continuous; this layer only configures the endpoint and connect/disconnect the OPC client. All calls go through `api/client.ts` (auto Bearer + `ApiError`).

- [ ] **Step 1: Write the failing test (mock `api/client`)**

```ts
// packages/smart_pid_web/src/features/fatia7/opcuaApi.test.ts
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiGet = vi.fn();
const apiPut = vi.fn();
const apiPost = vi.fn();
vi.mock("../../api/client", () => ({
  api: { get: apiGet, put: apiPut, post: apiPost },
  ApiError: class ApiError extends Error {},
}));

import { opcuaApi } from "./opcuaApi";

beforeEach(() => {
  apiGet.mockReset();
  apiPut.mockReset();
  apiPost.mockReset();
});

describe("opcuaApi", () => {
  it("getStatus calls GET /opcua/status", async () => {
    apiGet.mockResolvedValue({ state: "ONLINE", endpoint: "opc.tcp://x:4840" });
    const r = await opcuaApi.getStatus();
    expect(apiGet).toHaveBeenCalledWith("/opcua/status");
    expect(r.state).toBe("ONLINE");
  });

  it("saveEndpoint PUTs the endpoint body", async () => {
    apiPut.mockResolvedValue({ state: "OFFLINE", endpoint: "opc.tcp://y:4840" });
    await opcuaApi.saveEndpoint("opc.tcp://y:4840");
    expect(apiPut).toHaveBeenCalledWith("/opcua/endpoint", { endpoint: "opc.tcp://y:4840" });
  });

  it("connect POSTs an optional endpoint", async () => {
    apiPost.mockResolvedValue({ state: "ONLINE", endpoint: "opc.tcp://z:4840" });
    await opcuaApi.connect("opc.tcp://z:4840");
    expect(apiPost).toHaveBeenCalledWith("/opcua/connect", { endpoint: "opc.tcp://z:4840" });
    await opcuaApi.disconnect();
    expect(apiPost).toHaveBeenCalledWith("/opcua/disconnect");
  });

  it("browse URL-encodes the node id into the path", async () => {
    apiGet.mockResolvedValue({ parent_node_id: "ns=2;s=Demo", children: [] });
    await opcuaApi.browse("ns=2;s=Demo");
    expect(apiGet).toHaveBeenCalledWith(`/opcua/browse/${encodeURIComponent("ns=2;s=Demo")}`);
  });

  it("search passes q as a query param", async () => {
    apiGet.mockResolvedValue({ query: "flow", results: [] });
    await opcuaApi.search("flow");
    expect(apiGet).toHaveBeenCalledWith(`/opcua/search?q=${encodeURIComponent("flow")}`);
  });
});
```

- [ ] **Step 2: Run it red**

Run: `cd packages/smart_pid_web && npm run test -- opcuaApi`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `opcuaApi.ts`**

```ts
// packages/smart_pid_web/src/features/fatia7/opcuaApi.ts
import { api } from "../../api/client";

export interface OpcuaStatus { state: string; endpoint: string; }
export interface OpcuaNode { node_id: string; display_name: string; node_class: string; }

export const opcuaApi = {
  getStatus: (): Promise<OpcuaStatus> => api.get("/opcua/status"),
  saveEndpoint: (endpoint: string): Promise<OpcuaStatus> =>
    api.put("/opcua/endpoint", { endpoint }),
  connect: (endpoint?: string): Promise<OpcuaStatus> =>
    api.post("/opcua/connect", endpoint ? { endpoint } : undefined),
  disconnect: (): Promise<OpcuaStatus> => api.post("/opcua/disconnect"),
  browse: (nodeId: string): Promise<{ parent_node_id: string; children: OpcuaNode[] }> =>
    api.get(`/opcua/browse/${encodeURIComponent(nodeId)}`),
  search: (q: string): Promise<{ query: string; results: OpcuaNode[] }> =>
    api.get(`/opcua/search?q=${encodeURIComponent(q)}`),
};
```
> If `api.post(path)` does not accept a single-arg call in the scaffold, pass `undefined` explicitly: `api.post("/opcua/disconnect", undefined)`. Match the real `api/client.ts` signature (do not change it).

- [ ] **Step 4: Implement `useOpcua.ts`**

```ts
// packages/smart_pid_web/src/features/fatia7/useOpcua.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { opcuaApi } from "./opcuaApi";

const STATUS_KEY = ["opcua", "status"] as const;

export function useOpcuaStatus() {
  return useQuery({ queryKey: STATUS_KEY, queryFn: opcuaApi.getStatus });
}

export function useSaveEndpoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (endpoint: string) => opcuaApi.saveEndpoint(endpoint),
    onSuccess: (data) => qc.setQueryData(STATUS_KEY, data),
  });
}

export function useConnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (endpoint?: string) => opcuaApi.connect(endpoint),
    onSuccess: (data) => qc.setQueryData(STATUS_KEY, data),
  });
}

export function useDisconnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => opcuaApi.disconnect(),
    onSuccess: (data) => qc.setQueryData(STATUS_KEY, data),
  });
}

export function useBrowse(nodeId: string | null) {
  return useQuery({
    queryKey: ["opcua", "browse", nodeId],
    queryFn: () => opcuaApi.browse(nodeId as string),
    enabled: nodeId !== null,
  });
}

export function useSearch(q: string) {
  return useQuery({
    queryKey: ["opcua", "search", q],
    queryFn: () => opcuaApi.search(q),
    enabled: q.trim().length > 0,
  });
}
```

- [ ] **Step 5: Run it green**

Run: `cd packages/smart_pid_web && npm run test -- opcuaApi`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_web/src/features/fatia7/opcuaApi.ts \
        packages/smart_pid_web/src/features/fatia7/useOpcua.ts \
        packages/smart_pid_web/src/features/fatia7/opcuaApi.test.ts
git commit -m "feat(web): OPC-UA api client + query hooks (fatia7 connection)"
```

---

### Task 4: ConnectionPanel + TagBrowser + ConnectionPage

**Files:**
- Create: `packages/smart_pid_web/src/components/fatia7/ConnectionPanel.tsx`
- Create: `packages/smart_pid_web/src/components/fatia7/TagBrowser.tsx`
- Create: `packages/smart_pid_web/src/pages/ConnectionPage.tsx`
- Test: `packages/smart_pid_web/src/components/fatia7/ConnectionPanel.test.tsx`
- Test: `packages/smart_pid_web/src/components/fatia7/TagBrowser.test.tsx`

**Interfaces:** `ConnectionPanel` = endpoint text field + `[Connect | Disconnect]` + a `StatusIndicator` dot reflecting `ConnectionState`; **no acquisition start/stop**. `TagBrowser` = indented browsable tree (lazy `GET /browse/{node}` on expand, node icons by `node_class`) + a search box (`GET /search?q=`). Both consume the Task 3 hooks. Render inside a TanStack `QueryClientProvider` in tests.

- [ ] **Step 1: Write the failing ConnectionPanel test**

```tsx
// packages/smart_pid_web/src/components/fatia7/ConnectionPanel.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const connect = vi.fn().mockResolvedValue({ state: "ONLINE", endpoint: "opc.tcp://x:4840" });
const disconnect = vi.fn().mockResolvedValue({ state: "OFFLINE", endpoint: "opc.tcp://x:4840" });
const save = vi.fn().mockResolvedValue({ state: "OFFLINE", endpoint: "opc.tcp://x:4840" });
vi.mock("../../features/fatia7/useOpcua", () => ({
  useOpcuaStatus: () => ({ data: { state: "OFFLINE", endpoint: "opc.tcp://x:4840" } }),
  useConnect: () => ({ mutateAsync: connect, isPending: false }),
  useDisconnect: () => ({ mutateAsync: disconnect, isPending: false }),
  useSaveEndpoint: () => ({ mutateAsync: save, isPending: false }),
}));

import { ConnectionPanel } from "./ConnectionPanel";

function wrap(ui: React.ReactNode) {
  return <QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>;
}

describe("ConnectionPanel", () => {
  it("shows the current endpoint and state, with Connect/Disconnect (no acquisition controls)", () => {
    render(wrap(<ConnectionPanel />));
    expect(screen.getByLabelText(/endpoint/i)).toHaveValue("opc.tcp://x:4840");
    expect(screen.getByText(/OFFLINE/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /connect/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start acquisition|stop acquisition/i })).not.toBeInTheDocument();
  });

  it("saves the endpoint then connects", async () => {
    render(wrap(<ConnectionPanel />));
    fireEvent.change(screen.getByLabelText(/endpoint/i), { target: { value: "opc.tcp://y:4840" } });
    fireEvent.click(screen.getByRole("button", { name: /^connect$/i }));
    await waitFor(() => expect(save).toHaveBeenCalledWith("opc.tcp://y:4840"));
    expect(connect).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run it red**

Run: `cd packages/smart_pid_web && npm run test -- ConnectionPanel`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `ConnectionPanel.tsx`**

```tsx
// packages/smart_pid_web/src/components/fatia7/ConnectionPanel.tsx
import { useState } from "react";
import {
  useConnect,
  useDisconnect,
  useOpcuaStatus,
  useSaveEndpoint,
} from "../../features/fatia7/useOpcua";

export function ConnectionPanel() {
  const status = useOpcuaStatus();
  const save = useSaveEndpoint();
  const connect = useConnect();
  const disconnect = useDisconnect();
  const [endpoint, setEndpoint] = useState(status.data?.endpoint ?? "");

  const current = status.data?.endpoint ?? "";
  const value = endpoint || current;
  const state = status.data?.state ?? "OFFLINE";
  const online = state === "ONLINE";

  async function handleConnect() {
    if (value && value !== current) await save.mutateAsync(value);
    await connect.mutateAsync(value || undefined);
  }

  return (
    <section className="connection-panel" aria-label="OPC-UA connection">
      <div className="connection-panel__row">
        <label htmlFor="opc-endpoint">Endpoint</label>
        <input
          id="opc-endpoint"
          type="text"
          placeholder="opc.tcp://host:4840"
          value={value}
          onChange={(e) => setEndpoint(e.target.value)}
        />
        <span className="status-dot" data-state={state} aria-live="polite">
          {state}
        </span>
      </div>
      <div className="connection-panel__actions">
        <button type="button" onClick={handleConnect} disabled={connect.isPending}>
          Connect
        </button>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => disconnect.mutateAsync()}
          disabled={!online || disconnect.isPending}
        >
          Disconnect
        </button>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Run ConnectionPanel green**

Run: `cd packages/smart_pid_web && npm run test -- ConnectionPanel`
Expected: PASS (2 tests).

- [ ] **Step 5: Write the failing TagBrowser test**

```tsx
// packages/smart_pid_web/src/components/fatia7/TagBrowser.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../features/fatia7/useOpcua", () => ({
  useBrowse: () => ({
    data: {
      parent_node_id: "i=85",
      children: [
        { node_id: "ns=2;s=FT-101", display_name: "FT-101", node_class: "Variable" },
        { node_id: "ns=2;s=Folder", display_name: "Folder", node_class: "Object" },
      ],
    },
    isLoading: false,
  }),
  useSearch: () => ({ data: { query: "", results: [] }, isLoading: false }),
}));

import { TagBrowser } from "./TagBrowser";

describe("TagBrowser", () => {
  it("renders browse children as a tree with a search box", () => {
    render(<TagBrowser onSelect={vi.fn()} />);
    expect(screen.getByRole("searchbox")).toBeInTheDocument();
    expect(screen.getByText("FT-101")).toBeInTheDocument();
    expect(screen.getByText("Folder")).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: Run it red**

Run: `cd packages/smart_pid_web && npm run test -- TagBrowser`
Expected: FAIL — module not found.

- [ ] **Step 7: Implement `TagBrowser.tsx`**

```tsx
// packages/smart_pid_web/src/components/fatia7/TagBrowser.tsx
import { useState } from "react";
import { OpcuaNode } from "../../features/fatia7/opcuaApi";
import { useBrowse, useSearch } from "../../features/fatia7/useOpcua";

const ROOT_NODE = "i=85"; // OPC-UA Objects folder

function nodeIcon(nodeClass: string): string {
  return nodeClass === "Variable" ? "tag" : "folder";
}

export function TagBrowser({ onSelect }: { onSelect: (node: OpcuaNode) => void }) {
  const [query, setQuery] = useState("");
  const browse = useBrowse(query ? null : ROOT_NODE);
  const search = useSearch(query);

  const nodes: OpcuaNode[] = query
    ? search.data?.results ?? []
    : browse.data?.children ?? [];

  return (
    <div className="tag-browser" aria-label="OPC-UA tag browser">
      <input
        type="search"
        role="searchbox"
        placeholder="Search tags…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <ul className="tag-browser__tree">
        {nodes.map((n) => (
          <li key={n.node_id} className="tag-browser__node" data-icon={nodeIcon(n.node_class)}>
            <button type="button" onClick={() => onSelect(n)}>
              {n.display_name}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 8: Run TagBrowser green**

Run: `cd packages/smart_pid_web && npm run test -- TagBrowser`
Expected: PASS (1 test).

- [ ] **Step 9: Implement `ConnectionPage.tsx` + register route**

```tsx
// packages/smart_pid_web/src/pages/ConnectionPage.tsx
import { useState } from "react";
import { ConnectionPanel } from "../components/fatia7/ConnectionPanel";
import { TagBrowser } from "../components/fatia7/TagBrowser";
import { OpcuaNode } from "../features/fatia7/opcuaApi";

export default function ConnectionPage() {
  const [selected, setSelected] = useState<OpcuaNode | null>(null);
  return (
    <div className="page page--connection">
      <header className="page__header">
        <h1>OPC Connection</h1>
      </header>
      <ConnectionPanel />
      <TagBrowser onSelect={setSelected} />
      {selected && (
        <p className="tag-browser__selected">
          Selected: <code>{selected.node_id}</code>
        </p>
      )}
    </div>
  );
}
```
Add to `src/App.tsx` route table (append):
```tsx
<Route path="/connection" element={<ConnectionPage />} />
```
with a matching `lazy(() => import("./pages/ConnectionPage"))`.

- [ ] **Step 10: Build + commit**

Run: `cd packages/smart_pid_web && npm run build`
Expected: build succeeds.
```bash
git add packages/smart_pid_web/src/components/fatia7/ConnectionPanel.tsx \
        packages/smart_pid_web/src/components/fatia7/ConnectionPanel.test.tsx \
        packages/smart_pid_web/src/components/fatia7/TagBrowser.tsx \
        packages/smart_pid_web/src/components/fatia7/TagBrowser.test.tsx \
        packages/smart_pid_web/src/pages/ConnectionPage.tsx \
        packages/smart_pid_web/src/App.tsx
git commit -m "feat(web): OPC connection page with endpoint config + tag browser (fatia7)"
```

---

### Task 5: Project data layer — `projectApi.ts` + `useProjects.ts`

**Files:**
- Create: `packages/smart_pid_web/src/features/fatia7/projectApi.ts`
- Create: `packages/smart_pid_web/src/features/fatia7/useProjects.ts`
- Test: `packages/smart_pid_web/src/features/fatia7/projectApi.test.ts`

**Interfaces:**
```ts
export interface ProjectItem { name: string; controller_count: number; size_bytes: number; }
export interface ProjectMeta { name: string; path: string; controller_count: number; }
export const projectApi: {
  list(): Promise<{ projects: ProjectItem[] }>;
  current(): Promise<ProjectMeta>;
  create(name: string): Promise<ProjectMeta>;            // POST /project/new
  open(name: string): Promise<ProjectMeta>;              // POST /project/open
  import(file: File, name?: string): Promise<ProjectMeta>; // multipart POST /project/import
  download(): Promise<Blob>;                             // GET /project/download
  remove(name: string): Promise<void>;                  // DELETE /project/{name}
};
export function useProjectList(): UseQueryResult<{ projects: ProjectItem[] }>;
export function useCurrentProject(): UseQueryResult<ProjectMeta>;
export function useCreateProject(): UseMutationResult<ProjectMeta, ApiError, string>;
export function useOpenProject(): UseMutationResult<ProjectMeta, ApiError, string>;
export function useImportProject(): UseMutationResult<ProjectMeta, ApiError, { file: File; name?: string }>;
export function useDeleteProject(): UseMutationResult<void, ApiError, string>;
```
`import` builds a `FormData` with `file` and optional `name` (matches the backend `UploadFile` + `Form` signature). `download` requests a Blob and the caller triggers a browser download. `remove` expects **204** (no body). Backend errors mapped through `ApiError`: 409 (exists), 404 (open missing), 413 (upload too large), 401 (no auth).

- [ ] **Step 1: Write the failing test**

```ts
// packages/smart_pid_web/src/features/fatia7/projectApi.test.ts
import { beforeEach, describe, expect, it, vi } from "vitest";

const apiGet = vi.fn();
const apiPost = vi.fn();
const apiDelete = vi.fn();
const apiPostForm = vi.fn();
const apiGetBlob = vi.fn();
vi.mock("../../api/client", () => ({
  api: { get: apiGet, post: apiPost, delete: apiDelete, postForm: apiPostForm, getBlob: apiGetBlob },
  ApiError: class ApiError extends Error {},
}));

import { projectApi } from "./projectApi";

beforeEach(() => {
  apiGet.mockReset(); apiPost.mockReset(); apiDelete.mockReset();
  apiPostForm.mockReset(); apiGetBlob.mockReset();
});

describe("projectApi", () => {
  it("list calls GET /project/list", async () => {
    apiGet.mockResolvedValue({ projects: [] });
    await projectApi.list();
    expect(apiGet).toHaveBeenCalledWith("/project/list");
  });

  it("create POSTs the name to /project/new", async () => {
    apiPost.mockResolvedValue({ name: "p1", path: "/x/p1.spid", controller_count: 0 });
    await projectApi.create("p1");
    expect(apiPost).toHaveBeenCalledWith("/project/new", { name: "p1" });
  });

  it("open POSTs the name to /project/open", async () => {
    apiPost.mockResolvedValue({ name: "p1", path: "/x/p1.spid", controller_count: 2 });
    await projectApi.open("p1");
    expect(apiPost).toHaveBeenCalledWith("/project/open", { name: "p1" });
  });

  it("import sends multipart FormData with file and name", async () => {
    apiPostForm.mockResolvedValue({ name: "imp", path: "/x/imp.spid", controller_count: 1 });
    const file = new File([new Uint8Array([1, 2, 3])], "imp.spid");
    await projectApi.import(file, "imp");
    const [path, form] = apiPostForm.mock.calls[0];
    expect(path).toBe("/project/import");
    expect(form).toBeInstanceOf(FormData);
    expect((form as FormData).get("name")).toBe("imp");
    expect((form as FormData).get("file")).toBeInstanceOf(File);
  });

  it("remove issues DELETE /project/{name}", async () => {
    apiDelete.mockResolvedValue(undefined);
    await projectApi.remove("p1");
    expect(apiDelete).toHaveBeenCalledWith(`/project/${encodeURIComponent("p1")}`);
  });

  it("download requests a blob from /project/download", async () => {
    apiGetBlob.mockResolvedValue(new Blob([new Uint8Array([1])]));
    const blob = await projectApi.download();
    expect(apiGetBlob).toHaveBeenCalledWith("/project/download");
    expect(blob).toBeInstanceOf(Blob);
  });
});
```
> The mocked client method names (`postForm`, `getBlob`) must match the real `api/client.ts` surface from Fatia 0+1. If the scaffold exposes multipart/blob differently (e.g. a single `request()` with options), adapt the test + impl to the real signature in Step 3 — do NOT modify `api/client.ts`.

- [ ] **Step 2: Run it red**

Run: `cd packages/smart_pid_web && npm run test -- projectApi`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `projectApi.ts`**

```ts
// packages/smart_pid_web/src/features/fatia7/projectApi.ts
import { api } from "../../api/client";

export interface ProjectItem { name: string; controller_count: number; size_bytes: number; }
export interface ProjectMeta { name: string; path: string; controller_count: number; }

export const projectApi = {
  list: (): Promise<{ projects: ProjectItem[] }> => api.get("/project/list"),
  current: (): Promise<ProjectMeta> => api.get("/project/current"),
  create: (name: string): Promise<ProjectMeta> => api.post("/project/new", { name }),
  open: (name: string): Promise<ProjectMeta> => api.post("/project/open", { name }),
  import: (file: File, name?: string): Promise<ProjectMeta> => {
    const form = new FormData();
    form.append("file", file);
    if (name) form.append("name", name);
    return api.postForm("/project/import", form);
  },
  download: (): Promise<Blob> => api.getBlob("/project/download"),
  remove: (name: string): Promise<void> => api.delete(`/project/${encodeURIComponent(name)}`),
};
```

- [ ] **Step 4: Implement `useProjects.ts`**

```ts
// packages/smart_pid_web/src/features/fatia7/useProjects.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { projectApi } from "./projectApi";

const LIST_KEY = ["projects", "list"] as const;
const CURRENT_KEY = ["projects", "current"] as const;

export function useProjectList() {
  return useQuery({ queryKey: LIST_KEY, queryFn: projectApi.list });
}
export function useCurrentProject() {
  return useQuery({ queryKey: CURRENT_KEY, queryFn: projectApi.current });
}

function invalidating(qc: ReturnType<typeof useQueryClient>) {
  return () => {
    void qc.invalidateQueries({ queryKey: LIST_KEY });
    void qc.invalidateQueries({ queryKey: CURRENT_KEY });
  };
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (name: string) => projectApi.create(name), onSuccess: invalidating(qc) });
}
export function useOpenProject() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (name: string) => projectApi.open(name), onSuccess: invalidating(qc) });
}
export function useImportProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, name }: { file: File; name?: string }) => projectApi.import(file, name),
    onSuccess: invalidating(qc),
  });
}
export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (name: string) => projectApi.remove(name), onSuccess: invalidating(qc) });
}
```

- [ ] **Step 5: Run it green**

Run: `cd packages/smart_pid_web && npm run test -- projectApi`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_web/src/features/fatia7/projectApi.ts \
        packages/smart_pid_web/src/features/fatia7/useProjects.ts \
        packages/smart_pid_web/src/features/fatia7/projectApi.test.ts
git commit -m "feat(web): project api client + query hooks (fatia7 projects)"
```

---

### Task 6: Backend contract tests — auth required + credential boundary

**Files:**
- Create: `tests/core/integration/test_project_auth_required.py`
- Create: `tests/core/integration/test_project_export_no_credentials.py`

**Interfaces:** Two integration tests over the FastAPI app (httpx `ASGITransport`/`TestClient`) asserting the mono-user contract: (1) protected project routes return **401** without a JWT; (2) an exported `.spid` contains **no** credential/user tables (credential boundary). These are contract tests over existing behavior — no feature code.

- [ ] **Step 1: Write the auth-required test**

```python
# tests/core/integration/test_project_auth_required.py
"""Project routes require the authenticated admin (mono-user contract).

GAP-7a: assumes fix/backend-security-hardening is applied (auth on /project/*).
If that branch is not merged in this worktree, mark xfail with a TODO pointing
at fix/backend-security-hardening (do NOT add auth here — precondition is owned
outside this plan).
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/project/list"),
        ("get", "/project/current"),
        ("post", "/project/new"),
        ("post", "/project/open"),
        ("get", "/project/download"),
        ("delete", "/project/sample"),
    ],
)
async def test_project_routes_require_auth(async_client, method, path) -> None:
    # No Authorization header -> 401 (NOT 403-by-role; mono-user model).
    resp = await getattr(async_client, method)(path)
    assert resp.status_code == 401, (
        f"{method.upper()} {path} should be 401 without a JWT, got {resp.status_code}"
    )
```
> Reuse the existing `async_client` (unauthenticated) fixture from the core test suite. If it injects a token by default, add a token-free client fixture instead.

- [ ] **Step 2: Run it red/confirm**

Run: `uv run pytest tests/core/integration/test_project_auth_required.py -v`
Expected (hardening applied): PASS (all routes 401). Expected (hardening NOT in worktree): FAIL with 200/204 — convert to `xfail(reason="needs fix/backend-security-hardening")` and re-run to confirm xfail, per Task 0 Step 2.

- [ ] **Step 3: Write the credential-boundary test**

```python
# tests/core/integration/test_project_export_no_credentials.py
"""An exported .spid must NOT contain user/credential tables.

Credential boundary (contract §1): admin credentials live in users.db, never in
.spid projects. Asserts the SQLite schema of a project file has no user table.
"""
from __future__ import annotations

import sqlite3

import pytest


@pytest.mark.asyncio
async def test_exported_spid_has_no_credential_tables(project_service, tmp_path) -> None:
    meta = await project_service.new_project("boundary-check")
    export_path = project_service.download_path()  # active .spid on disk

    con = sqlite3.connect(export_path)
    try:
        names = {
            row[0].lower()
            for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        con.close()

    forbidden = {"users", "usuarios", "credentials", "passwords"}
    leaked = names & forbidden
    assert not leaked, f".spid export leaked credential tables: {leaked}"
    assert meta.name == "boundary-check"
```
> Use the existing `project_service` fixture; if absent, construct `ProjectService` against a `tmp_path` projects dir. `download_path()` is the active project path (from `routers/project.download_project`).

- [ ] **Step 4: Run it green**

Run: `uv run pytest tests/core/integration/test_project_export_no_credentials.py -v`
Expected: PASS — no forbidden tables in the `.spid` schema.

- [ ] **Step 5: Lint + commit**

Run: `uv run --with ruff ruff check tests/core/integration/test_project_auth_required.py tests/core/integration/test_project_export_no_credentials.py`
Expected: no errors.
```bash
git add tests/core/integration/test_project_auth_required.py \
        tests/core/integration/test_project_export_no_credentials.py
git commit -m "test(core): project auth-required + credential-boundary contract tests (fatia7)"
```

---

### Task 7: ProjectList + ProjectImportDropzone + ProjectsPage

**Files:**
- Create: `packages/smart_pid_web/src/components/fatia7/ProjectList.tsx`
- Create: `packages/smart_pid_web/src/components/fatia7/ProjectImportDropzone.tsx`
- Create: `packages/smart_pid_web/src/pages/ProjectsPage.tsx`
- Test: `packages/smart_pid_web/src/components/fatia7/ProjectList.test.tsx`
- Test: `packages/smart_pid_web/src/components/fatia7/ProjectImportDropzone.test.tsx`

**Interfaces:** `ProjectList` renders rows/cards (name, loop count, size) with per-item **Open / Download / Delete** actions; delete is confirmed when `confirmDestructive` is on. `ProjectImportDropzone` = dropzone + file input + progress, calling `useImportProject`. `ProjectsPage` composes both + a "New project" form. **Never render credentials** anywhere.

- [ ] **Step 1: Write the failing ProjectList test**

```tsx
// packages/smart_pid_web/src/components/fatia7/ProjectList.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const remove = vi.fn().mockResolvedValue(undefined);
const open = vi.fn().mockResolvedValue({ name: "p1", path: "x", controller_count: 0 });
vi.mock("../../features/fatia7/useProjects", () => ({
  useProjectList: () => ({
    data: { projects: [{ name: "p1", controller_count: 3, size_bytes: 2048 }] },
    isLoading: false,
  }),
  useDeleteProject: () => ({ mutateAsync: remove, isPending: false }),
  useOpenProject: () => ({ mutateAsync: open, isPending: false }),
}));
vi.mock("../../features/fatia7/useSettings", () => ({
  useSettings: () => ({ preferences: { confirmDestructive: false } }),
}));

import { ProjectList } from "./ProjectList";

describe("ProjectList", () => {
  it("lists projects with loop count and size", () => {
    render(<ProjectList />);
    expect(screen.getByText("p1")).toBeInTheDocument();
    expect(screen.getByText(/3/)).toBeInTheDocument();
  });

  it("deletes a project (no confirm when confirmDestructive is off)", async () => {
    render(<ProjectList />);
    fireEvent.click(screen.getByRole("button", { name: /delete/i }));
    expect(remove).toHaveBeenCalledWith("p1");
  });

  it("opens a project", async () => {
    render(<ProjectList />);
    fireEvent.click(screen.getByRole("button", { name: /^open$/i }));
    expect(open).toHaveBeenCalledWith("p1");
  });
});
```

- [ ] **Step 2: Run it red**

Run: `cd packages/smart_pid_web && npm run test -- ProjectList`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `ProjectList.tsx`**

```tsx
// packages/smart_pid_web/src/components/fatia7/ProjectList.tsx
import { projectApi } from "../../features/fatia7/projectApi";
import { useDeleteProject, useOpenProject, useProjectList } from "../../features/fatia7/useProjects";
import { useSettings } from "../../features/fatia7/useSettings";

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ProjectList() {
  const list = useProjectList();
  const del = useDeleteProject();
  const open = useOpenProject();
  const { preferences } = useSettings();

  async function handleDelete(name: string) {
    if (preferences.confirmDestructive && !window.confirm(`Delete project "${name}"?`)) return;
    await del.mutateAsync(name);
  }

  async function handleDownload() {
    const blob = await projectApi.download();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "project.spid";
    a.click();
    URL.revokeObjectURL(url);
  }

  if (list.isLoading) return <p>Loading projects…</p>;
  const projects = list.data?.projects ?? [];

  return (
    <table className="project-list" aria-label="Projects">
      <thead>
        <tr><th>Name</th><th>Loops</th><th>Size</th><th>Actions</th></tr>
      </thead>
      <tbody>
        {projects.map((p) => (
          <tr key={p.name}>
            <td>{p.name}</td>
            <td className="tnum">{p.controller_count}</td>
            <td className="tnum">{formatSize(p.size_bytes)}</td>
            <td className="project-list__actions">
              <button type="button" onClick={() => open.mutateAsync(p.name)}>Open</button>
              <button type="button" className="btn-secondary" onClick={handleDownload}>Download</button>
              <button type="button" className="btn-danger" onClick={() => handleDelete(p.name)}>Delete</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```
> `GET /project/download` streams the **active** project; the per-row Download opens then downloads the active project. If the spec later requires per-name download, that needs a new backend endpoint — note as a GAP, do not invent it.

- [ ] **Step 4: Run ProjectList green**

Run: `cd packages/smart_pid_web && npm run test -- ProjectList`
Expected: PASS (3 tests).

- [ ] **Step 5: Write the failing ProjectImportDropzone test**

```tsx
// packages/smart_pid_web/src/components/fatia7/ProjectImportDropzone.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const importMut = vi.fn().mockResolvedValue({ name: "imp", path: "x", controller_count: 1 });
vi.mock("../../features/fatia7/useProjects", () => ({
  useImportProject: () => ({ mutateAsync: importMut, isPending: false }),
}));

import { ProjectImportDropzone } from "./ProjectImportDropzone";

describe("ProjectImportDropzone", () => {
  it("imports a selected .spid file", async () => {
    render(<ProjectImportDropzone />);
    const file = new File([new Uint8Array([1, 2])], "imp.spid");
    const input = screen.getByLabelText(/import .spid/i) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(importMut).toHaveBeenCalled());
    expect(importMut.mock.calls[0][0].file.name).toBe("imp.spid");
  });
});
```

- [ ] **Step 6: Run it red**

Run: `cd packages/smart_pid_web && npm run test -- ProjectImportDropzone`
Expected: FAIL — module not found.

- [ ] **Step 7: Implement `ProjectImportDropzone.tsx`**

```tsx
// packages/smart_pid_web/src/components/fatia7/ProjectImportDropzone.tsx
import { useImportProject } from "../../features/fatia7/useProjects";

export function ProjectImportDropzone() {
  const importProject = useImportProject();

  async function handleFile(file: File | undefined) {
    if (!file) return;
    const name = file.name.replace(/\.spid$/i, "");
    await importProject.mutateAsync({ file, name });
  }

  return (
    <div className="import-dropzone" aria-label="Import project">
      <label htmlFor="import-input">Import .spid</label>
      <input
        id="import-input"
        type="file"
        accept=".spid"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
      {importProject.isPending && <progress aria-label="Uploading" />}
      {importProject.isError && (
        <p className="import-dropzone__error" role="alert">
          Upload failed: {(importProject.error as Error).message}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 8: Run ProjectImportDropzone green**

Run: `cd packages/smart_pid_web && npm run test -- ProjectImportDropzone`
Expected: PASS (1 test).

- [ ] **Step 9: Implement `ProjectsPage.tsx` + register route**

```tsx
// packages/smart_pid_web/src/pages/ProjectsPage.tsx
import { useState } from "react";
import { ProjectImportDropzone } from "../components/fatia7/ProjectImportDropzone";
import { ProjectList } from "../components/fatia7/ProjectList";
import { useCreateProject } from "../features/fatia7/useProjects";

export default function ProjectsPage() {
  const create = useCreateProject();
  const [name, setName] = useState("");

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    await create.mutateAsync(name.trim());
    setName("");
  }

  return (
    <div className="page page--projects">
      <header className="page__header">
        <h1>Projects</h1>
      </header>
      <form className="project-new" onSubmit={handleCreate}>
        <label htmlFor="new-name">New project name</label>
        <input id="new-name" value={name} onChange={(e) => setName(e.target.value)} />
        <button type="submit" disabled={create.isPending}>Create</button>
      </form>
      <ProjectImportDropzone />
      <ProjectList />
    </div>
  );
}
```
Add to `src/App.tsx` route table (append):
```tsx
<Route path="/projects" element={<ProjectsPage />} />
```
with a matching `lazy(() => import("./pages/ProjectsPage"))`.

- [ ] **Step 10: Build + commit**

Run: `cd packages/smart_pid_web && npm run build`
Expected: build succeeds.
```bash
git add packages/smart_pid_web/src/components/fatia7/ProjectList.tsx \
        packages/smart_pid_web/src/components/fatia7/ProjectList.test.tsx \
        packages/smart_pid_web/src/components/fatia7/ProjectImportDropzone.tsx \
        packages/smart_pid_web/src/components/fatia7/ProjectImportDropzone.test.tsx \
        packages/smart_pid_web/src/pages/ProjectsPage.tsx \
        packages/smart_pid_web/src/App.tsx
git commit -m "feat(web): projects page — list, import upload, create, delete (fatia7)"
```

---

### Task 8: WelcomeDialog (post-login project picker)

**Files:**
- Create: `packages/smart_pid_web/src/components/fatia7/WelcomeDialog.tsx`
- Test: `packages/smart_pid_web/src/components/fatia7/WelcomeDialog.test.tsx`
- Modify: `packages/smart_pid_web/src/App.tsx` (mount the dialog after auth)

**Interfaces:**
```ts
export function WelcomeDialog(props: { open: boolean; onDismiss: () => void }): JSX.Element | null;
```
Shown once after login (needs auth to list backend projects — `GET /project/list`). Lists projects in cards/rows (name, loop count, size) with `[New] [Import] [Open]`; selecting Open calls `useOpenProject` then dismisses. Never displays credentials.

- [ ] **Step 1: Write the failing test**

```tsx
// packages/smart_pid_web/src/components/fatia7/WelcomeDialog.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const open = vi.fn().mockResolvedValue({ name: "p1", path: "x", controller_count: 0 });
vi.mock("../../features/fatia7/useProjects", () => ({
  useProjectList: () => ({ data: { projects: [{ name: "p1", controller_count: 2, size_bytes: 1024 }] }, isLoading: false }),
  useOpenProject: () => ({ mutateAsync: open, isPending: false }),
}));

import { WelcomeDialog } from "./WelcomeDialog";

describe("WelcomeDialog", () => {
  it("renders backend projects when open", () => {
    render(<WelcomeDialog open onDismiss={vi.fn()} />);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("p1")).toBeInTheDocument();
  });

  it("renders nothing when closed", () => {
    const { container } = render(<WelcomeDialog open={false} onDismiss={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("opens a project then dismisses", async () => {
    const onDismiss = vi.fn();
    render(<WelcomeDialog open onDismiss={onDismiss} />);
    fireEvent.click(screen.getByRole("button", { name: /^open$/i }));
    expect(open).toHaveBeenCalledWith("p1");
  });
});
```

- [ ] **Step 2: Run it red**

Run: `cd packages/smart_pid_web && npm run test -- WelcomeDialog`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `WelcomeDialog.tsx`**

```tsx
// packages/smart_pid_web/src/components/fatia7/WelcomeDialog.tsx
import { useNavigate } from "react-router-dom";
import { useOpenProject, useProjectList } from "../../features/fatia7/useProjects";

export function WelcomeDialog({ open, onDismiss }: { open: boolean; onDismiss: () => void }) {
  const list = useProjectList();
  const openProject = useOpenProject();
  const navigate = useNavigate();
  if (!open) return null;

  const projects = list.data?.projects ?? [];

  async function handleOpen(name: string) {
    await openProject.mutateAsync(name);
    onDismiss();
  }

  return (
    <div className="welcome-overlay" role="dialog" aria-modal="true" aria-label="Welcome — choose a project">
      <div className="welcome-dialog">
        <header className="welcome-dialog__header">
          <h2>Open a project</h2>
        </header>
        <ul className="welcome-dialog__list">
          {list.isLoading && <li>Loading…</li>}
          {projects.map((p) => (
            <li key={p.name} className="welcome-dialog__item">
              <span className="welcome-dialog__name">{p.name}</span>
              <span className="tnum">{p.controller_count} loops</span>
              <button type="button" onClick={() => handleOpen(p.name)}>Open</button>
            </li>
          ))}
        </ul>
        <footer className="welcome-dialog__actions">
          <button type="button" onClick={() => { onDismiss(); navigate("/projects"); }}>New</button>
          <button type="button" onClick={() => { onDismiss(); navigate("/projects"); }}>Import</button>
          <button type="button" className="btn-secondary" onClick={onDismiss}>Close</button>
        </footer>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run it green**

Run: `cd packages/smart_pid_web && npm run test -- WelcomeDialog`
Expected: PASS (3 tests).

- [ ] **Step 5: Mount the dialog post-login in `App.tsx`**

In `src/App.tsx`, inside the authenticated layout, render `<WelcomeDialog open={showWelcome} onDismiss={() => setShowWelcome(false)} />`, where `showWelcome` initializes `true` once per session after login (e.g. a `useState(true)` reset on the auth user changing, or a `sessionStorage` "welcome-seen" guard). Keep the change minimal — append the dialog + the small state hook; do not restructure routing.

- [ ] **Step 6: Build + commit**

Run: `cd packages/smart_pid_web && npm run build`
Expected: build succeeds.
```bash
git add packages/smart_pid_web/src/components/fatia7/WelcomeDialog.tsx \
        packages/smart_pid_web/src/components/fatia7/WelcomeDialog.test.tsx \
        packages/smart_pid_web/src/App.tsx
git commit -m "feat(web): post-login welcome dialog lists backend projects (fatia7)"
```

---

### Task 9: End-to-end (Playwright) — connection, projects, negative auth

**Files:**
- Create: `packages/smart_pid_web/e2e/fatia7-connection.spec.ts`
- Create: `packages/smart_pid_web/e2e/fatia7-projects.spec.ts`
- Create: `packages/smart_pid_web/e2e/fatia7-auth-negative.spec.ts`

**Interfaces:** Three deterministic Playwright specs against a running backend + built SPA. Reuse the Fatia 0+1 login helper. Avoid timeout-based assertions; wait on selectors / responses.

- [ ] **Step 1: Connection e2e — configure endpoint + connect + browse/search**

```ts
// packages/smart_pid_web/e2e/fatia7-connection.spec.ts
import { expect, test } from "@playwright/test";
import { login } from "./helpers/login"; // from Fatia 0+1

test("configure OPC endpoint, connect, and browse/search tags", async ({ page }) => {
  await login(page);
  await page.goto("/connection");
  await page.getByLabel(/endpoint/i).fill("opc.tcp://127.0.0.1:4840");
  await page.getByRole("button", { name: /^connect$/i }).click();
  await expect(page.locator(".status-dot")).toHaveAttribute("data-state", /ONLINE|CONNECTING/);
  // tag browse renders a tree; search filters
  await expect(page.getByRole("searchbox")).toBeVisible();
  await page.getByRole("searchbox").fill("FT");
  // results list updates (either nodes or an empty state) without error
  await expect(page.locator(".tag-browser__tree")).toBeVisible();
});
```

- [ ] **Step 2: Projects e2e — import then open; create then delete**

```ts
// packages/smart_pid_web/e2e/fatia7-projects.spec.ts
import { expect, test } from "@playwright/test";
import path from "node:path";
import { login } from "./helpers/login";

test("import a .spid then open it; create then delete a project", async ({ page }) => {
  await login(page);
  await page.goto("/projects");

  // create
  await page.getByLabel(/new project name/i).fill("e2e-temp");
  await page.getByRole("button", { name: /^create$/i }).click();
  await expect(page.getByRole("cell", { name: "e2e-temp" })).toBeVisible();

  // import (a fixture .spid shipped under e2e/fixtures/)
  await page.getByLabel(/import .spid/i).setInputFiles(path.join(__dirname, "fixtures", "sample.spid"));
  await expect(page.getByRole("cell", { name: /sample/i })).toBeVisible();

  // open the imported project
  const row = page.getByRole("row", { name: /sample/i });
  await row.getByRole("button", { name: /^open$/i }).click();

  // delete the temp project
  page.on("dialog", (d) => d.accept());
  const tempRow = page.getByRole("row", { name: /e2e-temp/i });
  await tempRow.getByRole("button", { name: /delete/i }).click();
  await expect(page.getByRole("cell", { name: "e2e-temp" })).toHaveCount(0);
});
```
> Ship a minimal valid `e2e/fixtures/sample.spid` (a small SQLite project file with no user table). If generating it inline is simpler, create it in a `beforeAll` via the backend `POST /project/new` + `GET /project/download`.

- [ ] **Step 3: Negative-auth e2e — 401 on a protected route without a token**

```ts
// packages/smart_pid_web/e2e/fatia7-auth-negative.spec.ts
import { expect, test } from "@playwright/test";

test("protected project route returns 401 without a JWT (mono-user, not 403-by-role)", async ({ request }) => {
  // No Authorization header.
  const resp = await request.get("/api/project/list");
  expect(resp.status()).toBe(401);
});

test("unauthenticated UI is redirected to /login", async ({ page }) => {
  await page.goto("/projects");
  await expect(page).toHaveURL(/\/login/);
});
```

- [ ] **Step 4: Run the e2e suite**

Run: `cd packages/smart_pid_web && npm run test:e2e -- fatia7-`
Expected: all 4 e2e tests PASS (connection, projects, both auth-negative). If the backend hardening (GAP-7a) is not merged, the `401` API test will fail with 200 — gate it with a skip + TODO referencing `fix/backend-security-hardening`, consistent with Task 0/Task 6.

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_web/e2e/fatia7-connection.spec.ts \
        packages/smart_pid_web/e2e/fatia7-projects.spec.ts \
        packages/smart_pid_web/e2e/fatia7-auth-negative.spec.ts \
        packages/smart_pid_web/e2e/fixtures/sample.spid
git commit -m "test(web): e2e — OPC connect+browse, project import/open/delete, 401 negative-auth (fatia7)"
```

---

### Task 10: Specs upkeep + final verification

**Files:**
- Modify: `docs/smartPIDv2.md` (add the Web HMI Settings/Connection/Projects surface).
- Modify: the relevant `docs/identidade_visual_*.md` (note the new admin/config pages follow the design-system grid/typography).

- [ ] **Step 1: Update UI specs**

In `docs/smartPIDv2.md`, document the three new Web HMI pages (`/settings`, `/connection`, `/projects`) and the post-login welcome dialog, including the mono-user note (single admin, no user CRUD, no role gating; auth = 401 vs 200) and the credential boundary (credentials in `users.db`, never in `.spid`). Mirror the design-system §10 "Fatia 7" guidance into the relevant `docs/identidade_visual_*.md` (two-column settings form with hairline section headers; connection panel + tag tree; project rows with download/delete; never render credentials).

- [ ] **Step 2: Full frontend verification**

Run:
```bash
cd packages/smart_pid_web
npm run test
npm run build
npm run test:e2e -- fatia7-
```
Expected: all Vitest suites green; Vite build succeeds; the 4 fatia7 e2e specs pass (or are explicitly skipped pending GAP-7a, per Task 9 Step 4).

- [ ] **Step 3: Backend verification**

Run:
```bash
uv run pytest tests/core/integration/test_project_auth_required.py tests/core/integration/test_project_export_no_credentials.py -v
uv run --with ruff ruff check tests/
uv run mypy packages/   # baseline ~540 errors must NOT increase
```
Expected: contract tests pass (or xfail per GAP-7a); ruff clean; mypy error count unchanged.

- [ ] **Step 4: Commit**

```bash
git add docs/smartPIDv2.md docs/identidade_visual_*.md
git commit -m "docs: document web settings/connection/projects pages + welcome dialog (fatia7)"
```

---

## Self-Review

Before declaring Fatia 7 complete, verify (evidence before assertions — run the commands, read the output):

- [ ] **Mono-user contract honored.** No user-management page, no user CRUD, no `routers/users` consumption, no role-based UI gating anywhere in the added code. (`grep -rniE "users|rbac|operator|supervisor|require_admin|role" packages/smart_pid_web/src/features/fatia7 packages/smart_pid_web/src/components/fatia7 packages/smart_pid_web/src/pages/{Settings,Connection,Projects}Page.tsx` returns no role/user-management UI.)
- [ ] **Negative auth is 401, not 403.** Both the backend contract test (`test_project_auth_required.py`) and the e2e API test assert **401** without a JWT.
- [ ] **No invented endpoints.** Every call maps to a real route from the backend surface: `/opcua/{status,endpoint,connect,disconnect,browse/{node_id},search}`, `/project/{current,list,new,open,import,download,{name}}`, `/system/status`, `/auth/login`. Admin password-change UI is **absent** (no `/auth/change-password` exists).
- [ ] **Acquisition is continuous.** No start/stop-of-acquisition control exists in `ConnectionPanel`/`ConnectionPage` (only endpoint config + connect/disconnect).
- [ ] **Credential boundary enforced + tested.** `test_project_export_no_credentials.py` passes; no UI surface renders credentials.
- [ ] **GAP-7a referenced, not re-implemented.** Project-route auth + path sanitization + 413 cap are treated as a precondition (`fix/backend-security-hardening`); this plan added no auth dependencies to `routers/project.py`.
- [ ] **Canonical files untouched.** `api/client.ts`, `auth/*`, `components/shell/*`, `realtime/*`, `theme/*` are not redefined; only `App.tsx` is appended to (routes + welcome mount) and `api/generated/openapi.ts` regenerated.
- [ ] **Acceptance criteria met:** OPC connection configurable + tag browse/search works; projects manageable incl. upload/download; welcome lists projects; auth mandatory (401 without token).
- [ ] **TDD respected:** every component/hook has a failing-first test, minimal impl, green, then commit. Conventional commits, no attribution trailers, all on `feat/web-fatia7-settings-connection-projects`.
- [ ] **Toolchain green:** `npm run test`, `npm run build`, `npm run test:e2e -- fatia7-`, `uv run pytest` (new tests), `ruff check`, and `mypy` (no increase) all pass.
