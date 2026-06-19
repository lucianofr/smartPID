# TD-007 — single-admin / remove RBAC — VERIFIED EDIT PLAN

Analysis already complete (prior agent). Apply mechanically with TDD, then commit. All
paths relative to this worktree `.worktrees/main-web-hmi`.

## Code edits
1. **`dependencies.py`**: remove `_ROLE_LEVEL` + `require_operator` / `require_supervisor` /
   `require_admin`. Add a single `require_authenticated_admin(user = Depends(get_current_user)) -> UserClaims`
   that just returns `user`. KEEP `get_current_user` (it is the 401 path).
2. **Routers** — swap every `Depends(require_operator|require_supervisor|require_admin)` →
   `Depends(require_authenticated_admin)` and collapse the now-single import in:
   `ai.py, alarms.py, audit.py, controllers.py, export.py, history.py, opcua.py, simulator.py,
   stats.py, system_events.py, project.py, commands.py`. (Grep to confirm none missed.)
3. **`auth.py`**: delete `POST /register` and the imports it alone uses (`require_admin`,
   `UserCreate`, `hash_password`). KEEP `login` + `refresh`. Fix the docstring. Run ruff for orphans.
4. **`routers/users.py`**: delete the file. Remove its import + `include_router(... "/users" ...)`
   line in `app.py`.
5. **Admin bootstrap stays:** `main.py:335-346` seeds the admin independently of `/register`;
   leave it working. `UserRepository` + `test_user_repo.py` untouched. Update the `main.py:344-345`
   log string that references the removed "/users API" and the non-existent `SPID_ADMIN_PASSWORD`.

## Test edits (TDD: change contract first → red → implement → green)
- Delete `tests/core/integration/test_user_api.py`.
- Rewrite `test_rbac.py` to exercise `require_authenticated_admin` (authenticated → ok, no-auth → 401).
- `test_api_auth.py`: delete `TestRegister`; keep login/refresh.
- Convert every `assert ... == 403` to authenticated-success (or remove) in:
  `test_api_controllers.py, test_audit_api.py, test_alarm_config_crud.py, test_api_commands.py,
  test_api_project.py`. ALL "401 when unauthenticated" assertions STAY.
- `test_system_events_api.py`: tighten `(401, 403)` → `401`.
- Add a 401-no-auth test for `/audit` (it lacked one).
- conftest `admin/user/supervisor_headers` fixtures all become "authenticated" and must still pass.

## Out of scope (note as concern, do NOT invent)
- No standalone change-password endpoint exists (only the deleted `PUT /users/{id}`). Recommend a
  follow-up `POST /auth/change-password` gated by `require_authenticated_admin`; do NOT add it now.

## Verify
- NOT the full suite (Py3.14 aiosqlite SIGABRT). Run targeted touched files:
  `SPID_JWT_SECRET=test-secret uv run pytest <touched test files> -q --tb=short -p no:cacheprovider`
- aiosqlite "Event loop is closed" warnings are harmless; only failed/error counts matter.
- `uv run --with ruff ruff check .` on changes.
