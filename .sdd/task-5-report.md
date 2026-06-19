# Task 5 Report — Wire /ws/realtime + bridge lifespan + SPA mount + config

## Status
DONE. Committed `298c6fb` on `feat/web-fatia01-foundation-dashboard`.

## Binding override honored
P4 had already added security headers (inline `_security_headers` middleware),
`CORSMiddleware`, `TrustedHostMiddleware`, and `api_host="127.0.0.1"`. I did NOT
create `middleware.py`, did NOT add any `SecurityHeadersMiddleware`/CORS/TrustedHost
(brief Steps 1,3,4 + Step 6 middleware adds + Step 5 host change = VOID), and did NOT
write a security_headers test. Only the trimmed task was implemented.

## Changes (3 files, +94/-1)

### `packages/smart_pid_core/src/smart_pid_core/config.py`
Added two real fields near the network-hardening settings (env prefix `SPID_`):
```python
web_dist_dir: str | None = None
allowed_ws_origins: tuple[str, ...] = ("http://127.0.0.1:5173",)
```
→ env vars `SPID_WEB_DIST_DIR`, `SPID_ALLOWED_WS_ORIGINS`. Host default left as
the pre-existing `127.0.0.1`. Task 4's endpoint reads `settings.allowed_ws_origins`
via a getattr fallback; this makes it a first-class field.

### `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
- New imports: `os`, `fastapi.staticfiles.StaticFiles`, and
  `ConnectionManager, RealtimeBridge, register_realtime_ws` from `...api.ws.realtime`
  (import block reordered by `ruff --fix`).
- After `app.state.event_bus = event_bus` (+ execution_mode): added
  `app.state.realtime_manager = ConnectionManager()` and
  `app.state.realtime_bridge = RealtimeBridge(event_bus, app.state.realtime_manager) if event_bus is not None else None`.
- `_lifespan` extended: starts bridge if present, `try/yield/finally` stops it.
- `register_realtime_ws(app)` called AFTER the `include_router(...)` block.
- SPA mounted LAST (after routers, WS route, error handlers), guarded:
  `if settings.web_dist_dir and os.path.isdir(settings.web_dist_dir): app.mount("/", StaticFiles(directory=..., html=True), name="spa")`.

### `tests/core/api/test_ws_realtime.py`
Appended `test_create_app_registers_ws_route_and_openapi` (async). Reuses the
`create_app` kwargs pattern from `tests/core/integration/test_security_middleware.py`
(real SQLiteRepository/SQLiteHistorian/UserRepository/EventBus/LoopManager,
`CoreSettings(_env_file=None, jwt_secret=...)`). Asserts `"/ws/realtime"` in
`{r.path for r in app.routes}`, `app.state.realtime_bridge is not None`, and
`TestClient(app, base_url="http://127.0.0.1").get("/openapi.json").status_code == 200`.
(`base_url` set to a trusted host because the pre-existing TrustedHostMiddleware
rejects the TestClient default `testserver` host with 400 — not a regression.)

## Real signatures verified in realtime.py (Task 3/4 code)
- `RealtimeBridge.__init__(self, bus: EventBus, manager: ConnectionManager)` —
  positional `(event_bus, manager)`, matches the wiring.
- Bridge methods are `async def start(self)` and `async def stop(self)` (the
  literal names `start`/`stop`, not custom names). `stop()` is idempotent.
- `register_realtime_ws(app)` registers `GET /ws/realtime` and reads
  `settings.allowed_ws_origins` / `settings.jwt_secret` at handshake time.

## TDD
RED first: `pytest -k create_app` → `AssertionError: '/ws/realtime' not in {...}`.
Wired create_app → GREEN.

## Test output (verbatim, key lines)
```
# RED
1 failed, 21 deselected in 0.29s   (assert '/ws/realtime' in ... AssertionError)

# After wiring (intermediate): 1 failed (openapi 400 from TrustedHost) → fixed base_url
# GREEN — full WS file
22 passed, 3 warnings in 0.58s

# Full api dir
3 failed, 28 passed, 3 warnings in 0.75s
#   3 failures = pre-existing TestProjectServiceOPCUA (Py3.14, known/unchanged):
#     test_open_project_auto_connects_with_saved_endpoint
#     test_open_project_no_endpoint_stops_adapter
#     test_new_project_stops_opcua_adapter
```
Full `pytest tests/` not run (environmental SIGABRT exit 134 on Py3.14+aiosqlite,
per instructions).

## Lint / mypy
- `ruff check packages/.../api/` → initially 1 import-sort error, `ruff --fix`
  applied, re-run: `All checks passed!`.
- `mypy packages/` → mypy not installed in base venv (`Failed to spawn: mypy`).
  Ran via `uv run --with mypy mypy app.py config.py` →
  `Success: no issues found in 2 source files`.

## Self-review
- No duplicate/reordered middleware; pre-existing CORS/TrustedHost/security-headers
  untouched.
- Bridge wired positionally per the real `__init__`; lifespan uses real start/stop.
- WS registered after routers; SPA mounted last and double-guarded (config + dir).
- No magic values (CSP/headers already centralized in P4; origins from settings).
- Only 3 in-scope files staged; `.sdd/` and caches not committed.

## Concerns
1. The smoke test exercises full DB/EventBus startup (heavier than a pure stub),
   matching the existing security-middleware fixture; acceptable but not minimal.
2. mypy could not run repo-wide (not installed); verified only the 2 changed
   modules via `--with mypy`. Repo baseline not re-measured.
3. SPA mount and `web_dist_dir` are config-gated and untested here (no dist dir in
   CI); covered only by the "configured + exists" guard logic, not an asserted path.
