# TD-007 — single-admin / remove RBAC — IMPLEMENTATION REPORT

Branch: `fix/td-007-single-admin` (worktree `.worktrees/main-web-hmi`).
Product decision applied: single-user, one admin, NO RBAC. Auth stays mandatory
(401 when unauthenticated). All role-tier 403s removed — there are no role-based
403 responses after this change.

## Commits (oldest -> newest)
1. `876e492` refactor(api): collapse RBAC role tiers into single-admin auth gate
2. `28d2a6c` test(api): update auth tests to single-admin contract

## Source changes (commit 1)

- **dependencies.py**: removed `_ROLE_LEVEL` and `require_operator` /
  `require_supervisor` / `require_admin`. Added one
  `require_authenticated_admin(user = Depends(get_current_user)) -> UserClaims`
  that just returns the user. `get_current_user` (the 401 path) kept unchanged.
- **12 routers** (`ai, alarms, audit, controllers, export, history, opcua,
  simulator, stats, system_events, project, commands`): every
  `Depends(require_operator|supervisor|admin)` -> `Depends(require_authenticated_admin)`,
  and the multi-line / single-line dependency imports collapsed to the single
  symbol. `history.py` single-line import expanded to parenthesized form
  (the longer name pushed it past the 100-char ruff limit).
- **auth.py**: deleted `POST /register` and the imports only it used
  (`require_admin`, `UserCreate`, `hash_password`). Kept `login` + `refresh`.
  Updated module docstring.
- **routers/users.py**: deleted. Removed its import and
  `include_router(..., prefix="/users", ...)` from `app.py`.
- **main.py**: admin bootstrap (seed `admin`/`admin`) left working; updated the
  `seeded_default_admin` log message that referenced the removed `/users API`
  and the non-existent `SPID_ADMIN_PASSWORD` env var.

`routers/__init__.py` is empty — no `users` export to remove there.
`UserRepository`, `UserCreate` DTO, and `test_user_repo.py` untouched as planned.

## Test changes (commit 2)

- **test_rbac.py**: rewritten to exercise `require_authenticated_admin`
  (authenticated -> returns same user). The old 403-by-role cases removed.
- **test_user_api.py**: deleted.
- **test_api_auth.py**: removed `TestRegister`; kept `TestLogin` /
  `TestJWTValidation` (401 paths intact).
- **403 -> authenticated-success conversions** (all "401 when unauthenticated"
  assertions kept):
  - `test_api_controllers.py`: `test_create_non_admin_forbidden` ->
    `test_create_any_authenticated_user_allowed` (201).
  - `test_audit_api.py`: `test_get_audit_operator_forbidden` ->
    `..._any_authenticated_user_allowed` (200); **added** `test_get_audit_requires_auth`
    (no header -> 401), the 401 case `/audit` previously lacked.
  - `test_alarm_config_crud.py`: `..._requires_supervisor` ->
    `..._any_authenticated_user_allowed` (200).
  - `test_api_commands.py`: `test_operator_forbidden` ->
    `test_any_authenticated_user_allowed` (200; added `app` fixture +
    `_FakeOPCUA` to reach the success path, mirroring the existing clamp test).
  - `test_api_project.py`: updated module docstring; 5 conversions —
    new (200), open (404 reaching handler), import (200 with a real .spid via
    aiosqlite, mirroring the import success test), download (200 after creating
    a project), delete (404 reaching handler).
  - `test_system_events_api.py`: tightened `in (401, 403)` -> `== 401`.
- **Extra files the plan's list missed** (both reference the deleted symbols in
  `dependency_overrides`; would `ImportError` otherwise):
  - `test_export_router.py`: override key `require_operator` ->
    `require_authenticated_admin`.
  - `test_opcua_endpoint.py`: `_mock_admin_user` import/return `require_admin`
    -> `require_authenticated_admin`.

## conftest fixtures
`admin_headers` / `user_headers` / `supervisor_headers` already mint valid
authenticated JWTs differing only in the (now-ignored) role string. Since no
endpoint gates on role, all three now succeed everywhere and all touched tests
pass with them unchanged. Left as-is (surgical: renaming would ripple across
many untouched files); they are effectively "authenticated" headers as required.

## Verification

Ruff (line-length 100) on all touched source + test files: **All checks passed!**

Targeted test runs (`SPID_JWT_SECRET=test-secret uv run pytest <files> -q
--tb=short -p no:cacheprovider`):

- `test_rbac.py test_export_router.py test_opcua_endpoint.py test_api_auth.py`
  -> **18 passed, 3 failed**. The 3 failures are in
  `test_opcua_endpoint.py::TestProjectServiceOPCUA::*`, which call
  `asyncio.get_event_loop().run_until_complete(...)` — a Python 3.14
  "no current event loop" RuntimeError, unrelated to auth. Verified pre-existing:
  stashing my edit and rerunning that class reproduces the same 3 failures. My
  only change to that file (`_mock_admin_user`, used by the passing
  `TestPutOPCUAEndpoint`) is green.
- `test_api_controllers.py test_audit_api.py test_alarm_config_crud.py
  test_api_commands.py test_api_project.py test_system_events_api.py`
  -> **69 passed**.
- `test_dtos.py` (UserCreate DTO still present) -> **14 passed**.
- App route assertion script: no `/users*` routes, no `/auth/register`;
  `/auth/login` + `/auth/refresh` present.

Did NOT run the full suite (Py3.14 + aiosqlite teardown SIGABRT, environmental).

## Concerns / follow-ups
- No standalone change-password endpoint exists (the only password mutation was
  the deleted `PUT /users/{id}`). Recommend a follow-up
  `POST /auth/change-password` gated by `require_authenticated_admin`. Not added
  here (out of scope per plan).
- `test_opcua_endpoint.py::TestProjectServiceOPCUA` has 3 pre-existing failures
  (Py3.14 `get_event_loop`); not in scope for TD-007 but worth a separate fix.
- conftest role-specific fixtures (`user_headers`, `supervisor_headers`) are now
  semantically just "authenticated"; kept for minimal blast radius. A later
  cleanup could collapse them to a single `auth_headers`.
