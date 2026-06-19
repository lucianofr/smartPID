# TD-007 Review — Collapse RBAC role tiers into single-admin auth gate

Range reviewed: `903f7a6..28d2a6c` (2 commits)
- `876e492` refactor(api): collapse RBAC role tiers into single-admin auth gate
- `28d2a6c` test(api): update auth tests to single-admin contract

Verification combined the diff with live-tree `grep`/AST-style route enumeration and an
actual test run (`SPID_JWT_SECRET=... uv run pytest ...`). Read-only; nothing modified.

---

## Verdict

- **SPEC: PASS** — every binding requirement met.
- **QUALITY: Approved** — no Critical/Important issues; two Minor notes.

---

## Spec compliance (item by item)

1. **Single auth gate.** `require_authenticated_admin` defined in `dependencies.py`; it depends
   on `get_current_user` and returns the user unchanged. `require_operator` /
   `require_supervisor` / `require_admin` / `_ROLE_LEVEL` are **gone from the entire `packages/`
   tree** (grep: 0 hits). 84 added `require_authenticated_admin` references replace 107 removed
   old-role references across all routers. PASS

2. **Auth mandatory; 401 path intact; no 403-by-role.**
   - `get_current_user` still raises `HTTP_401_UNAUTHORIZED` on missing/invalid token
     (dependencies.py, two raise sites). PASS
   - No `_ROLE_LEVEL`, no role comparison, no `HTTP_403_FORBIDDEN` in any router. The only
     `status_code=403` in the codebase is `error_handlers.py:34`, a global handler for the
     domain exception `AuthorizationError`. That exception is **defined and registered but never
     raised anywhere** (grep across `packages/`), so no 403-by-role response can be produced.
     It is dead-but-harmless infra. PASS
   - The only `403` strings left in tests are explanatory comments (`# never a role-based 403.`),
     not assertions. PASS

3. **`routers/users.py` removed + de-registered.** File absent; `app.py` no longer imports or
   `include_router`s `users`. `tests/core/integration/test_user_api.py` (208 lines) deleted. PASS

4. **`POST /register` removed; login/refresh preserved.** `register` handler and its
   `hash_password`/`UserCreate`/`require_admin` imports removed from `auth.py`. `POST /auth/login`
   (public, issues token) and `POST /auth/refresh` (depends on `get_current_user`) both intact.
   No `/register` route anywhere in `packages/`. PASS

5. **Admin seed intact + `UserRepository` kept.** `main.py` L335-346 still seeds the admin via
   `user_repo.create("admin", admin_hash, "ADMIN")` when no users exist — fully independent of the
   deleted `/register`. The only code change in `main.py` is a one-line log-message cleanup
   (dropped the now-stale "via the /users API or set SPID_ADMIN_PASSWORD env var" text).
   `UserRepository` and `UserCreate` DTO still present. PASS

6. **Hexagonal + ruff.** No new domain→adapter imports introduced (refactor only swaps a
   dependency symbol). `ruff check` on the changed API package: **All checks passed** (line-length
   100 respected). PASS

---

## Security-critical: no route silently lost its gate

Enumerated all 66 route handlers across `routers/*.py`. Every handler has either
`require_authenticated_admin` or `get_current_user` in its signature, **except two**, both
correct and intended:

- `auth.py  POST /login` — must be public (token issuance). Correct.
- `system.py  GET /status` — explicitly `"Health check — no auth required"`, **not touched by
  this diff** (0 occurrences in the diff), was never role-gated. No regression.

=> All 64 previously role-gated endpoints now carry `require_authenticated_admin`. **Zero
mutation/sensitive routes dropped to no-dependency.** This is the biggest risk in a swap-the-dep
refactor and it is clean.

---

## Test contract

- `test_rbac.py` rewritten to assert `require_authenticated_admin` returns the authenticated user
  (and `is` the same object). No role/403 assertions remain.
- Former 403-by-role tests converted to `test_any_authenticated_user_allowed` (assert handler is
  reached -> 404 for missing resource, never 403), e.g. `test_api_project.py:123` and `:329`.
- 401-when-unauthenticated assertions preserved (test_api_auth, test_api_commands,
  test_api_controllers, test_api_project, test_rbac).
- `test_opcua_endpoint.py` auth override correctly retargeted from `require_admin` to
  `require_authenticated_admin` — no stale/wrong-dependency override.

**Test run (Python 3.14.6):** `70 passed, 3 failed`.
The 3 failures are all `TestProjectServiceOPCUA::*` failing on
`asyncio.get_event_loop()` -> `RuntimeError: There is no current event loop` (removed-default
behavior in Py3.14). Adjudication: **confirmed pre-existing/environmental** — those tests are not
touched by this diff (0 hits for `TestProjectServiceOPCUA`/`get_event_loop`/`new_project` in the
diff), call `ProjectService` directly, and have nothing to do with auth/RBAC. Claim is true.

---

## Adjudication of implementer-accepted items

- 3 OPC-UA failures environmental (Py3.14 `get_event_loop`): **TRUE** — verified not in diff,
  reproduced as the sole failures, root cause is the deprecated API not the refactor.
- conftest `user_headers`/`supervisor_headers` left unchanged: **TRUE** — conftest not in diff;
  now semantically just "an authenticated user". Acceptable.
- No standalone change-password endpoint (only deleted `PUT /users/{id}` mutated passwords),
  deferred: **TRUE** — no password-mutation route remains. See Minor #2.

---

## Minor notes (non-blocking)

- **Minor 1 — dead authz infra.** `AuthorizationError` + its 403 handler in `error_handlers.py`
  are now unreachable (never raised). Harmless, but could be removed for tidiness, or kept as a
  forward hook. No action required for TD-007.
- **Minor 2 — admin password operability gap.** Seed log now says "Change it immediately." but the
  only password-mutation path (`PUT /users/{id}`) was deleted and no replacement exists. With the
  default password `admin` and no change mechanism, the deployed admin credential is effectively
  fixed unless changed out-of-band (direct DB / re-seed). Accepted as deferred-by-design per the
  brief, but flagging it as an operational follow-up for the web-HMI work.

