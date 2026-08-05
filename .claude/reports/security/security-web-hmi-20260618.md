# Security Review — Web HMI (React/Vite) over Smart PID v2 Backend

**Date:** 2026-06-18
**Reviewer:** security-reviewer agent
**Scope:** Planned React/Vite web HMI consuming the existing FastAPI backend (JWT/bcrypt/RBAC) plus a NEW WebSocket bridge `/ws/realtime`. Industrial PID platform that writes tuning/MV to live DCS/PLC controllers via OPC-UA.
**Status:** Design/spec review (no `/ws/realtime` code exists yet) grounded in current backend source.

**Documents reviewed:**
- `docs/superpowers/specs/2026-06-18-web-hmi-react-migration-design.md`
- `docs/superpowers/specs/2026-06-18-web-fatia01..08-*.md` (fatia 7 read in full)

**Backend code reviewed:**
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/auth.py`
- `.../api/dependencies.py`, `.../api/app.py`
- `.../api/routers/{auth,commands,opcua,project,users,system,controllers,ai,simulator}.py`
- `.../application/project_service.py`, `.../config.py`, `.../main.py`

---

## Severity summary

| # | Finding | Severity |
|---|---------|----------|
| 1 | Project router has ZERO authentication/authorization on all endpoints (write/destructive to live config) | **CRITICAL** |
| 2 | Path traversal in project name (import/new/open/delete) escapes `projects_dir` | **CRITICAL** |
| 3 | No CORS policy defined for the browser client (spec relies on dev proxy; prod undefined) | **HIGH** |
| 4 | WS JWT via `?token=` query param — token leakage in logs/history/Referer | **HIGH** |
| 5 | `/commands/tuning` writes raw Kp/Ti/Td to DCS bypassing guardrails (operator role) | **HIGH** |
| 6 | No request/upload size limit on `.spid` import (`await file.read()` full body in memory) | **HIGH** |
| 7 | No security headers, no CSP for the served web app | **MEDIUM** |
| 8 | JWT secret has no minimum-strength validation; HS256 symmetric; no token revocation | **MEDIUM** |
| 9 | Browser token storage strategy undefined in spec (localStorage XSS exposure) | **MEDIUM** |
| 10 | `.spid` import does not validate it is a well-formed SQLite/.spid; `Usuarios` migration legacy path | **MEDIUM** |
| 11 | Write actions to live controllers lack explicit confirmation requirement in contract (audit OK) | **MEDIUM** |
| 12 | No rate limiting on `/auth/login` (brute force) and other endpoints | **LOW** |
| 13 | Generic `except Exception` swallows errors in project listing / migration | **LOW** |

---

## CRITICAL findings

### 1. Project router has NO authentication or authorization — CRITICAL

`adapters/inbound/api/routers/project.py` defines `new`, `open`, `import`, `download`, `delete`, `current`, `list` and **none of them depend on `get_current_user` or any `require_*` role gate.** Every other write router in the codebase (`commands`, `controllers`, `ai`, `simulator`, `users`, `opcua`) correctly enforces `require_operator` / `require_supervisor` / `require_admin`. Project is the outlier.

Impact in a browser-reachable deployment:
- `POST /project/open` and `POST /project/import` are **state-changing on the live plant**: they call `loop_manager.stop_all()`, swap the active SQLite project, restart control loops, and re-connect OPC-UA (`project_service.open_project` / `import_project`). An unauthenticated request can **stop all running PID loops and reconfigure which controllers the platform drives on a live DCS.**
- `DELETE /project/{name}` deletes project files unauthenticated.
- `GET /project/download` exfiltrates the active `.spid` (full controller config, tuning, audit logs, AI models) with no auth.

This is a safety-relevant control-plane operation exposed without authentication. Fatia 7 spec claims "Nenhuma mudança — reusa routers" and "CRUD respeita RBAC", but the underlying router does not enforce it, so the spec's RBAC claim is **false for project management** as written.

**Fix:** Add role dependencies to every project route. Recommended: `list`/`current` → `require_operator`; `new`/`open`/`import`/`download` → `require_supervisor`; `delete` → `require_admin`. Mirror the `commands.py`/`controllers.py` pattern. Add audit logging (`audit_and_broadcast`) on open/import/delete as those are operationally significant.

```python
@router.post("/open", response_model=ProjectResponse)
async def open_project(
    body: ProjectOpen,
    request: Request,
    user: Annotated[UserClaims, Depends(require_supervisor)],
) -> ProjectResponse:
    ...
```

### 2. Path traversal via project `name` — CRITICAL

`project_service.py` builds destinations directly from the caller-supplied name with no sanitization:

```python
dest = self._projects_dir / f"{name}.spid"        # new_project / import_project
path = self._projects_dir / f"{name}.spid"        # open_project / delete_project
```

`name` comes straight from the request body (`ProjectCreate.name`, `ProjectOpen.name`) or, for import, from `Form` / `UploadFile.filename` (`file.filename.removesuffix(".spid")`). `Path("/dir") / "../../etc/cron.d/x"` resolves outside `projects_dir`.

Impact (compounded by finding #1 being unauthenticated):
- `POST /project/import` with `name="../../../home/luciano/.smart-pid/users"` writes attacker-controlled bytes to `users.db.spid`, or with a crafted relative path **overwrites arbitrary files** the daemon user can write (arbitrary file write → potential RCE via overwriting startup scripts/configs).
- `DELETE /project/{name}` with a traversal payload **deletes arbitrary files**. The only guard is `if path == self._repo._db_path` (active-project check), which does not constrain the directory.
- `open_project` / `import_project` can be pointed at any readable SQLite file to load it as the active project.

**Fix:** Validate and normalize the name before any filesystem use. Reject names containing path separators, `..`, null bytes, or non-portable characters; then confirm the resolved path stays within `projects_dir`:

```python
import re
def _safe_project_path(self, name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9._\- ]{1,128}", name) or name in {".", ".."}:
        raise ValueError("invalid project name")
    dest = (self._projects_dir / f"{name}.spid").resolve()
    if dest.parent != self._projects_dir.resolve():
        raise ValueError("path escapes projects directory")
    return dest
```

Apply in `new_project`, `open_project`, `import_project`, `delete_project`. For import, do NOT derive the name from `file.filename` without the same validation.

---

## HIGH findings

### 3. No CORS policy for the browser client — HIGH

`app.py` registers no `CORSMiddleware` and no `TrustedHostMiddleware` (verified: no `add_middleware`/`allow_origins`/`CORSMiddleware` anywhere in `packages/smart_pid_core/src/`). The spec leans on a Vite dev proxy (`/api`, `/ws` → `:8000`) and "prod = user opens localhost". Two problems:

- If a CORS policy is later added carelessly (e.g. `allow_origins=["*"]` with `allow_credentials=True`), any website the operator visits could issue authenticated requests to `127.0.0.1:8000` (DNS-rebinding / drive-by against a workstation that runs the daemon). Because the API binds `0.0.0.0` by default (`config.py api_host="0.0.0.0"`), it is reachable beyond loopback.
- WebSocket handshakes are NOT subject to CORS; the `Origin` header must be validated explicitly in the new `/ws/realtime` endpoint or any web page can open the socket.

**Fix:**
- Define an explicit allow-list (`http://127.0.0.1:5173`, `http://localhost:5173`, plus the prod origin). Never `*` with credentials.
- Bind the API to `127.0.0.1` by default for the browser-only deployment; require explicit opt-in for `0.0.0.0`.
- In `/ws/realtime`, validate the `Origin` header against the same allow-list and reject mismatches before accept.
- Add `TrustedHostMiddleware` to blunt DNS-rebinding.

### 4. WS JWT via `?token=` query param — HIGH

§2.3 of the umbrella spec: "token via query param `?token=` ou primeira mensagem". Query-string tokens leak into:
- ASGI/uvicorn access logs and any reverse-proxy logs.
- Browser history and the `Referer` header on subsequent navigations.
- Crash/telemetry tooling that captures full URLs.

Since the WS shares the same JWT as REST (8h expiry, no revocation — see #8), a leaked URL token is a long-lived bearer credential to the control plane.

**Recommended pattern (in order of preference):**
1. **Short-lived WS ticket:** add `POST /auth/ws-ticket` (requires valid bearer) that returns a single-use, ~30s-TTL ticket bound to the user; the client passes the ticket as `?ticket=` (or subprotocol) and the server exchanges/invalidates it on accept. Keeps the long-lived JWT out of URLs entirely.
2. **First-message auth:** accept the socket, require an `{type:"auth", token}` frame within N seconds, validate, else close `4401`. Token stays in the WS payload, not the URL. (Spec already allows this — make it the default, not the query param.)
3. **Subprotocol header:** pass the token via `Sec-WebSocket-Protocol` (browser `new WebSocket(url, ["bearer", token])`). Not logged like query strings; echo back the chosen subprotocol.

Reject missing/invalid/expired with close code `4401` (already specified). Reuse `decode_access_token`/`get_current_user` logic. Do NOT log the token on rejection.

### 5. `/commands/tuning` writes raw Kp/Ti/Td to DCS bypassing guardrails — HIGH

`commands.py:write_tuning` (`POST /commands/tuning`) writes operator-supplied `kp/ti/td` straight to OPC-UA via `opcua.write_pid_params(...)` with **no `clamp_tuning_params` guardrail** and **only `require_operator`**. By contrast `apply-tuning/{id}` applies `clamp_tuning_params(... max_pct=ctrl.max_tuning_change_pct)` and requires `require_supervisor`. So the lower-privilege endpoint is the *less* safe one — an operator can push arbitrary gains to a live controller, defeating the platform's core guardrail design.

The body is also an untyped `dict` (`body: dict`), so values are unvalidated (`kp = body.get("kp")` could be wrong type / out of range). The audit `f"{val:.4f}"` formatting will raise if a non-numeric slips through (also a robustness bug).

**Fix:**
- Apply `clamp_tuning_params` against the controller's current values and `max_tuning_change_pct` here too.
- Raise the gate to `require_supervisor` to match `apply-tuning`.
- Replace `body: dict` with a typed Pydantic model (`controller_id: int`, `kp/ti/td: float | None` with range validation).
- Verify external PID is in AUTO before write-back (as `apply-tuning` does).

### 6. No size limit on `.spid` import upload — HIGH

`project.py:import_project` does `data = await file.read()` — the entire upload is buffered in memory with no cap, then written to disk. Combined with the missing auth (#1), this is a trivial memory-exhaustion / disk-fill DoS against the daemon. Even authenticated, a multi-GB upload can OOM the single asyncio process that also drives the live control loops — a safety concern, not just availability.

**Fix:** Enforce a max upload size (e.g. 50 MB) by checking `Content-Length` and/or streaming to a temp file with a running byte cap; reject oversize early with 413. Validate the uploaded bytes are a valid SQLite/`.spid` (magic header `SQLite format 3\0` + open + expected tables) before activating it.

---

## MEDIUM findings

### 7. No security headers / CSP — MEDIUM
No `X-Content-Type-Options`, `X-Frame-Options`/`frame-ancestors`, `Referrer-Policy`, `Permissions-Policy`, or CSP are configured for the API or the served web bundle. For a browser app that holds a control-plane token, ship a strict CSP (`default-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'`, no `unsafe-inline` scripts) on the static host, plus `nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` disabling camera/mic/geo. This directly reduces the blast radius of #4/#9.

### 8. JWT secret strength / algorithm / revocation — MEDIUM
- `config.py` declares `jwt_secret: str` (required, good) but enforces **no minimum length/entropy**. A weak `SPID_JWT_SECRET` makes HS256 tokens forgeable offline.
- HS256 (symmetric) means the verification secret is also the signing secret; anyone who can read backend config/env can mint admin tokens. Acceptable for a single-process edge daemon, but document the threat.
- 8h expiry with **no revocation/blacklist** and a `/auth/refresh` that re-issues without re-checking the user is still active/role unchanged. A token leaked via #4 is valid for up to 8h and survives a user being disabled.

**Fix:** Validate secret length (≥32 bytes) at startup; consider `jti` + a small revocation set for logout/disable; on `/auth/refresh` re-load the user and reject if inactive/role-changed.

### 9. Browser token storage undefined — MEDIUM
Spec says "token JWT no header `Authorization`" but does not state where the SPA stores it. `localStorage`/`sessionStorage` is readable by any XSS, exfiltrating a control-plane bearer. Options and tradeoffs:
- **In-memory only** (lost on reload; pair with #4 ws-ticket and a short-lived refresh) — best XSS posture.
- **`httpOnly`, `Secure`, `SameSite=Strict` cookie** — immune to JS read, but requires CSRF protection on state-changing routes (currently none) and a cookie-aware WS handshake. Pick one and specify it.
Decide explicitly in the Fatia 0+1 plan; do not default to `localStorage`.

### 10. `.spid` import validation & legacy `Usuarios` migration — MEDIUM
- Credential boundary is correctly held at the data layer: the `.spid` schema (`sqlite_repo.py`) contains `Controladores`, `Configuracao_Alarmes`, `Log_*`, `Modelos_IA`, `Projeto_Meta`, `Configuracao_Simulador` — **no users/passwords table**. `UserRepository` uses a separate `users_db_path` (`~/.smart-pid/users.db`). Fatia 7's rule ("auth/users fora dos metadados do projeto") is satisfied for runtime.
- Residual: `main.py:_migrate_users_if_needed` reads a `Usuarios` table from a `.spid` and seeds `users.db` — but only when `users.db` does not yet exist and only against `settings.db_path` at startup, NOT via the web import path. So web import cannot inject users. Still, a legacy `.spid` containing attacker-chosen password hashes placed at `settings.db_path` before first boot would seed credentials. Low likelihood (needs FS access pre-boot), worth a guard: log/ignore `Usuarios` tables in any uploaded/imported `.spid`, and only migrate from a trusted, explicitly-configured legacy path.
- Import does not currently verify the upload is a valid SQLite/`.spid` before `reopen` (see #6 fix).

### 11. Live-write confirmation in the contract — MEDIUM
Backend audits every control write (`audit_and_broadcast` on SP/mode/CO/tuning) — good. But "explicit confirmation" for writing tuning/MV to a live plant is a **UI** control that must be backed server-side where it matters: keep guardrails (#5), keep `apply-tuning` at supervisor, and consider requiring a confirmation token/`X-Confirm` header (or a two-step prepare/commit) for `apply-tuning`, `/commands/tuning`, `/commands/output`, `/commands/mode` so a browser CSRF/clickjacking cannot one-shot a plant write. Server-side authz is the real control; UI gating in the fatia specs is cosmetic only — ensure the plan states this explicitly.

---

## LOW findings

### 12. No rate limiting — LOW
No `slowapi`/equivalent on `/auth/login` (credential brute force) or on the command endpoints. Add per-IP/per-user limits, especially on login.

### 13. Broad `except Exception` — LOW
`project_service.list_projects` and `_migrate_users_if_needed` use bare `except Exception: pass`, hiding corruption/permission errors. Narrow and log.

---

## Positive observations
- bcrypt for password hashing (`auth.py`), parameterized SQL throughout (no string-concat queries observed).
- Consistent RBAC on commands/controllers/ai/simulator/users/opcua via `require_operator/supervisor/admin`.
- Tuning guardrails (`clamp_tuning_params`, `max_tuning_change_pct`) and external-mode AUTO check on `apply-tuning`.
- Full audit trail + live system-event broadcast on control actions.
- Credential boundary held: no users table in `.spid`; users in separate `users.db`.

---

## Top recommendations (priority order)
1. **Add authz to every `project.py` route** and **sanitize project names** in `project_service.py` (closes the two CRITICALs together).
2. **Do not use `?token=` for WS** — use a short-lived ws-ticket or first-message auth; validate `Origin` on the WS handshake.
3. **Define an explicit CORS allow-list, bind API to `127.0.0.1` by default**, add `TrustedHostMiddleware` and security headers/CSP.
4. **Bring `/commands/tuning` up to the safety bar of `apply-tuning`** (guardrails + supervisor + typed body) and **cap `.spid` upload size + validate format**.
5. Specify browser token storage (avoid `localStorage`); add login rate limiting; validate `jwt_secret` strength and tighten `/auth/refresh`.
