# TD-004 / P4 — Network Hardening (CORS, TrustedHost, Security Headers, loopback bind)

## STATUS: DONE

Branch: `fix/td-004-cors-headers` (worktree `main-web-hmi`). No branch switches; main untouched.

## What changed

### `packages/smart_pid_core/src/smart_pid_core/config.py`
- `api_host` default `0.0.0.0` -> `127.0.0.1`. `SPID_API_HOST=0.0.0.0` still works as
  an explicit off-host opt-in.
- New `cors_allow_origins: list[str]` = `["http://127.0.0.1:5173", "http://localhost:5173"]`
  (env `SPID_CORS_ALLOW_ORIGINS`).
- New `trusted_hosts: list[str]` = `["127.0.0.1", "localhost"]` (env `SPID_TRUSTED_HOSTS`).
- pydantic-settings parses list-typed env vars as JSON arrays
  (e.g. `SPID_CORS_ALLOW_ORIGINS='["http://127.0.0.1:5173"]'`). There were no
  pre-existing list-typed settings to mirror; documented the JSON-array shape inline.

### `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`
Registered inside `create_app`, reading from the existing `settings` arg:
- `@app.middleware("http")` security-headers layer setting on every response:
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`,
  `Permissions-Policy: camera=(), microphone=(), geolocation=()`,
  `Content-Security-Policy: default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'`.
  Uses `setdefault` so it never clobbers a header a route deliberately set.
- `CORSMiddleware(allow_origins=settings.cors_allow_origins, allow_credentials=True,
  allow_methods=[GET,POST,PUT,PATCH,DELETE,OPTIONS], allow_headers=[Authorization,Content-Type])`.
  Never `allow_origins=["*"]` with credentials.
- `TrustedHostMiddleware(allowed_hosts=settings.trusted_hosts)`.
- Ordering: TrustedHost added last -> outermost layer -> bad `Host` rejected (400)
  before CORS / routing / handlers run.

### Bind (requirement 3)
`main.py:487` already binds `host=settings.api_host`; no hardcoded `0.0.0.0` on the
HTTP path. (The remaining `0.0.0.0` hits in the repo are OPC-UA server + ZMQ
publisher transports — out of scope.) No change needed.

## Out of scope (left for Fatia 0+1, as instructed)
- WebSocket `/ws/realtime` Origin validation (endpoint does not exist yet).
- SPA static mount + bundle-specific CSP nonce.

## Tests — TDD red -> green
New `tests/core/integration/test_security_middleware.py` (8 tests):
- security headers present on a normal GET (`/system/status`).
- CORS preflight from allowed origin echoes it; disallowed origin not echoed;
  no credentialed wildcard.
- TrustedHost: bad `Host` -> 400; allowed host -> 200.
- config default `api_host == "127.0.0.1"`.

RED first run: config fields missing + default `0.0.0.0` -> 7 failing/erroring as
expected. After implementation: all 8 green.

### Cross-cutting test-infra fix (necessary, scoped)
TrustedHostMiddleware rejected the test clients' default Host headers
(`test` / `testserver`), which broke existing endpoint tests. Fixed the client
base URLs to a trusted host (`http://127.0.0.1`) everywhere a test drives an app
built by `create_app`:
- `tests/conftest.py` (`client`, `client_with_simulator` fixtures)
- `tests/core/integration/test_api_opcua.py`, `test_api_stats.py`,
  `test_audit_api.py` (TestClient base_url), `test_simulator_auto_endpoints.py`
  (TestClient base_url)
- `tests/core/unit/test_commands_monitor_mode.py`, `test_get_tuning_recommendations.py`
- `tests/core/unit/test_config.py` default-host assertion updated to `127.0.0.1`

Files that build bare `FastAPI()` apps (no `create_app`, no middleware) were left
alone: `test_opcua_endpoint.py`, `test_export_router.py`, and all `tests/hmi/*`
(they use the HMI's own `APIClient`, unaffected).

### Verification (targeted; full suite avoided per instructions — Py3.14 SIGABRT)
`test_security_middleware.py + test_api_auth.py + test_config.py +
test_api_opcua.py + test_api_stats.py + test_commands_monitor_mode.py +
test_get_tuning_recommendations.py + test_audit_api.py +
test_simulator_auto_endpoints.py + test_api_controllers.py +
test_api_commands.py + test_api_project.py` -> **99 passed**.
Earlier wider batch (controllers/commands/project/history/system/alarm/audit/simulator)
also green after fixes.

Lint/type: `ruff check` clean on all touched files; `mypy` (via `uv run --with mypy`)
clean on `app.py` + `config.py` after annotating the middleware closure
(`call_next: Callable[[Request], Awaitable[Response]] -> Response`).

## Commit
- `8556c66` fix(core): network hardening for control-plane daemon (TD-004)

## Concerns
- none (functional). Note: the loopback default means existing deployments relying
  on remote reachability must now set `SPID_API_HOST=0.0.0.0` explicitly — this is
  the intended hardening, not a regression.
