# OpenAPI/Swagger Surface — Default-Off Toggle

**Date:** 2026-08-05
**Scope:** Finding F3 (`security-vps-exposure-20260805.md`) — `/docs`, `/redoc`,
`/openapi.json` served unauthenticated by default. Adds a single global toggle,
default off, opt-in for local dev / the TestSprite MCP workflow.

---

## 1. File:line diff

### `packages/smart_pid_core/src/smart_pid_core/config.py:21-29`

Added `expose_openapi: bool = False` to `CoreSettings`, mapped from
`SPID_API_EXPOSE_OPENAPI` by the existing `env_prefix="SPID_"` config
(`config.py:10`) — no new plumbing needed, same pattern as every other bool
setting in the class (e.g. `simulator_enabled`).

```python
    # FastAPI
    api_port: int = 8000
    # Loopback by default: a control-plane daemon should not be reachable off-host
    # unless explicitly opted in via SPID_API_HOST=0.0.0.0.
    api_host: str = "127.0.0.1"
    # OpenAPI schema and docs UI (/docs, /redoc, /openapi.json) are disabled by
    # default: unauthenticated recon surface with no reason to be public on a
    # production deployment. Opt in for local dev / TestSprite MCP workflows.
    expose_openapi: bool = False
```

### `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py:107-114`

The `FastAPI(...)` constructor call in `create_app()` now conditions the three
schema/docs routes on `settings.expose_openapi`. Before:

```python
app = FastAPI(title="Smart PID API", version="2.0.0", lifespan=_lifespan)
```

After:

```python
app = FastAPI(
    title="Smart PID API",
    version="2.0.0",
    lifespan=_lifespan,
    docs_url="/docs" if settings.expose_openapi else None,
    redoc_url="/redoc" if settings.expose_openapi else None,
    openapi_url="/openapi.json" if settings.expose_openapi else None,
)
```

`docs_url`/`redoc_url`/`openapi_url=None` makes FastAPI skip registering those
routes entirely at `__init__`/`setup()` time (not just hide them from a menu),
so a request to any of the three paths falls through to Starlette's normal
404 — verified by the new test below.

### Unrelated coordination fix in the same file (Agent B ownership, requested by `LoginHardening`)

`app.py:130-131` — added `app.state.login_rate_limiter = auth.LoginRateLimiter()`
next to the other `app.state.*` assignments. `routers/auth.py` (owned by the
login-hardening task) reads `request.app.state.login_rate_limiter` and every
`/auth/login`-touching test 500'd without this line; `app.py`'s FastAPI-init
kwargs are this task's ownership per the cross-task split, so I made the one-line
addition rather than block a sibling task. No behavior of the openapi toggle is
affected; `auth` was already imported at `app.py:19`.

### `tests/core/api/test_ws_realtime.py:440-444`

`test_create_app_registers_ws_route_and_openapi` previously relied on the old
default (schema always on) and asserted `client.get("/openapi.json").status_code
== 200` against `CoreSettings` built with no override. With the default now
`False`, that assertion would 404. Since the test's own name and purpose is
"assert `create_app` wires the openapi route when asked", the fix is to make the
opt-in explicit rather than weaken the assertion:

```python
    settings = CoreSettings(
        _env_file=None,
        jwt_secret="test-secret-key-minimum-32-bytes!",
        expose_openapi=True,
    )  # type: ignore[call-arg]
```

No other test in the tree touched `/openapi.json`, `/docs`, or `/redoc`
(grep-verified across `tests/`). `scripts/dump_openapi.py` (backing
`test_openapi_dump.py`) calls `app.openapi()` directly to build the schema
dict — that method computes the schema independent of whether the
`openapi_url` *route* is registered, so the codegen dump is unaffected by the
new default.

### New: `tests/core/unit/test_app_openapi.py`

New file. Builds `create_app()` twice via an `expose_openapi` toggle and
asserts `/openapi.json`, `/docs`, `/redoc` are 404 when off (default) and 200
(with a JSON body containing the expected title) when on. Deterministic,
in-process `TestClient`, no live daemon.

---

## 2. Test result

```
$ uv run pytest tests/core/unit/test_app_openapi.py -q
..
2 passed in 0.85s
```

Also re-ran the touched/adjacent files for regressions:

```
$ uv run pytest tests/core/api/test_ws_realtime.py tests/core/unit/test_openapi_dump.py tests/core/unit/test_config.py -q
33 passed
$ uv run pytest tests/core/api tests/core/integration -q
633 passed, 1 failed
```

The one failure (`test_user_role_migration.py::TestSeedDefaultAdmin::test_generated_password_is_not_admin_and_is_logged`)
is in `main.py`'s bootstrap-admin path, owned and being actively worked by the
`BootstrapAdminFix` sibling task (F1/TD-011), not touched by this change —
confirmed by content (asserts on a `bootstrap_admin_password` log event this
task never writes) and file ownership (`main.py`, explicitly out of this
task's scope). Re-ran before and after this task's edits landed; failure is
present either way.

---

## Proposed tech debt

- **The exposure toggle is a single global knob, not a per-route policy.**
  `SPID_API_EXPOSE_OPENAPI` turns `/docs`, `/redoc`, and `/openapi.json` on or
  off together for the whole process. There is no way to express "this route
  should never require auth" (`/system/status`) versus "this route should not
  exist at all in production" (`/docs`) as distinct policies — today that
  distinction is implicit in which routers get `Depends(require_user)` versus
  which routes FastAPI auto-registers at `__init__` time. Fine for the current
  single-toggle need; would need a real route-classification layer (allow-list
  of unauthenticated paths + a separate dev-only-routes registry) if the
  surface grows past three hardcoded paths.
