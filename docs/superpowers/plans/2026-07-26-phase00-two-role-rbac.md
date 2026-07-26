# Phase 0 — Backend Two-Role Model (RBAC) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the two-role authorization model (`admin` / `user`) on the existing raw-aiosqlite backend: split the single `require_authenticated_admin` gate into `require_user`/`require_admin`, classify all 63 gated call sites, add the admin-gated `/users` router and `GET /auth/me`, migrate legacy role values in `users.db`, reject legacy JWT role claims with 401, and prove it all with a parametrised 403-per-route contract test.

**Architecture:** Pure additive/authorization work on the FastAPI daemon (`packages/smart_pid_core`). The domain `UserRole` enum collapses to two lowercase values; `get_current_user` becomes strict (any invalid/legacy claim → 401); two new dependencies express the gate; every router call site is re-pointed per the normative classification in Appendix A. Data access stays raw `aiosqlite` (SQLAlchemy is phase 1). The only persistence changes are a spec-sanctioned DDL default (`'OPERATOR'` → `'user'`) and an idempotent startup `UPDATE` that rewrites legacy role values.

**Tech Stack:** Python 3.13, FastAPI, aiosqlite, PyJWT + bcrypt, pydantic v2, pytest (`asyncio_mode = "auto"`, httpx `ASGITransport`), uv workspace.

## Global Constraints

- Roles are exactly `admin` and `user`, lowercase (spec §4 "Locked decisions", §9). Never reintroduce `SUPERVISOR`/`OPERATOR`/uppercase.
- Legacy JWT role claims (`"ADMIN"`, `"SUPERVISOR"`, `"OPERATOR"`) are **rejected with 401** — a single forced re-login. They are never mapped (spec §9.5).
- Role-value data migration is mandatory: `ADMIN → admin`, `SUPERVISOR → admin`, `OPERATOR → user`; DDL default changes `'OPERATOR'` → `'user'` (spec §9.4). No other schema change of any kind.
- Data layer stays raw `aiosqlite`. SQLAlchemy 2.0 is phase 1 — do not import it anywhere in this plan (spec §13).
- Existing REST routes and the WS envelope are unchanged. Additive surface only: `/users` router, `GET /auth/me`, 403 responses (spec §3, §9).
- Simulator endpoints are admin-only **except** twin `POST /simulator/{id}/pid/sp`, `POST /simulator/{id}/pid/mode`, `POST /simulator/{id}/co` (spec §9.2 — normative; Appendix A is the complete table).
- 401 = not authenticated / invalid token. 403 = authenticated but not admin, body `{"detail": "Admin privileges required"}`. Never confuse the two.
- Backend-only phase: nothing under `packages/smart_pid_web` changes. `packages/smart_pid_hmi` stays frozen **except** two pydantic-coupled mock/test files that would break the suite when the shared enum changes (Task 1 Step 9 — enumerated, justified, nothing else).
- OpenAPI regeneration/codegen is sequenced *after* phase 0 and belongs to phase 2 (spec §7). Do not add codegen here.
- All commands below run from the repo root (the `web-frontend-rewrite` worktree). Python via `uv run …`; pytest is configured with `asyncio_mode = "auto"`, `testpaths = ["tests"]` (root `pyproject.toml:31-34`).
- Commits use conventional-commit style: `feat(core): …`, `test: …`.
- API `detail` strings are English (matches `"Invalid credentials"`, `"Simulator not enabled"` in the existing code). UI copy/pt-BR rules are frontend-phase concerns.

---

## Verified baseline (read before starting)

Facts below were verified against the worktree on 2026-07-26; task steps rely on them.

| Fact | Where |
|---|---|
| Single gate `require_authenticated_admin` returns the user with **no role check** | `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py:75-84` |
| `get_current_user` **uppercases** the role claim (`payload["role"].upper()`) | `dependencies.py:68-72` |
| **63 call sites** of `require_authenticated_admin` across **12 of the 14 router modules** (`auth.py` and `system.py` carry none — spec §1 says "14 routers"; the verified count is 63 sites in 12 files) | Appendix B |
| Simulator has **18** gated endpoints, not the 17 the spec cites (verified route-by-route; the classification rule is unambiguous regardless) | Appendix A/B |
| `UserRole` is `ADMIN/SUPERVISOR/OPERATOR` uppercase | `packages/smart_pid_domain/src/smart_pid_domain/enums.py:137-140` |
| The "dead `RegisterRequest`" of spec §9.3 is named **`UserCreate`** in code (never had another name); it is exported but consumed by no router | `packages/smart_pid_domain/src/smart_pid_domain/dtos/auth.py:19-22`, `dtos/__init__.py:10` |
| `UserResponse`/`UserUpdate` DTOs already exist (used only by the frozen HMI's dead `/users` client calls) | `packages/smart_pid_domain/src/smart_pid_domain/dtos/users.py` |
| `AuditAction` already has `CREATE_USER`, `UPDATE_USER`, `DEACTIVATE_USER` | `enums.py:178-180` |
| `UserRepository` already implements `create/get_by_username/list_all/get_by_id/update/deactivate`; DDL default is `'OPERATOR'`; `get_by_username` filters `ativo = 1` | `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py` |
| Seed block creates `admin`/`admin` with role `"ADMIN"` when `users.db` is empty | `packages/smart_pid_core/src/smart_pid_core/main.py:335-346` |
| `.spid → users.db` copy (`_migrate_users_if_needed`) runs once at startup, **only if `users.db` does not exist**, and copies `perfil` verbatim (uppercase inflow) | `main.py:120-157, 332-333` |
| WS `/ws/realtime` first-message auth only calls `decode_access_token` — no role vocabulary check | `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py:219-223` |
| Test harness: `api_deps`/`app`/`client` fixtures + `admin_headers`(role `ADMIN`), `user_headers`(role `OPERATOR`), `supervisor_headers`(role `SUPERVISOR`) | `tests/conftest.py:29-147` |
| Sim harness seeds `"ADMIN"` too; sim API tests already use `admin_headers` | `tests/conftest.py:150-216`, `tests/core/integration/test_api_simulator.py` |
| WS tests mint `_good_token()` with role `"ADMIN"` | `tests/core/api/test_ws_realtime.py:256-259` |
| Error-handler convention: `{"detail": str}` bodies; dependencies raise `HTTPException` directly | `api/error_handlers.py`, `dependencies.py:51-72` |
| Router prefixes: stats+ai under `/controllers`, others one prefix each, users must be added after `export` | `api/app.py:157-174` |
| FastAPI resolves `Depends(...)` **before** body validation, so 403 wins over 422; the existing suite already relies on the equivalent property for 401 (`tests/core/integration/test_project_auth_required.py:30-31`) | behavior used by Task 6's contract test |

### File structure (created / modified)

```
packages/smart_pid_domain/src/smart_pid_domain/enums.py            modify  (UserRole)
packages/smart_pid_domain/src/smart_pid_domain/dtos/auth.py        modify  (UserCreate rework)
packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/
  dependencies.py                                                  modify  (strict claims, require_user, require_admin; later: delete old gate)
  routers/auth.py                                                  modify  (GET /me, refresh gate)
  routers/users.py                                                 CREATE  (admin-gated user management)
  routers/{ai,alarms,audit,commands,controllers,export,history,
           opcua,project,simulator,stats,system_events}.py         modify  (63 call-site swaps, Task 6)
  app.py                                                           modify  (include users router)
  ws/realtime.py                                                   modify  (legacy-claim rejection)
packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py  modify (DDL default)
packages/smart_pid_core/src/smart_pid_core/main.py                 modify  (role migration + seed helper)
packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py  modify  (pydantic-coupled role literals only)
tests/conftest.py                                                  modify  (fixture vocabulary)
tests/domain/test_models.py, tests/domain/test_dtos.py             modify
tests/core/unit/test_role_dependencies.py                          CREATE
tests/core/integration/test_api_users.py                           CREATE
tests/core/integration/test_user_role_migration.py                 CREATE
tests/core/integration/test_role_contract.py                       CREATE
tests/core/integration/test_api_auth.py                            modify  (legacy-claim 401, /auth/me)
tests/core/api/test_ws_realtime.py                                 modify  (_good_token + legacy-reject test)
tests/hmi/services/test_api_client_users.py                        modify  (role literals)
tests/core/integration/{test_ai_control_endpoints,test_alarm_config_crud,
  test_api_commands,test_api_controllers,test_api_optimization_toggle,
  test_api_project,test_project_auth_required}.py                  modify  (Task 6 adaptation)
```

---

### Task 1: Two-role vocabulary cutover (enum, claims, dependencies, test harness)

The enum value change, strict claim validation, the two new dependencies, and the test-harness token flip are **one atomic commit**: flipping the enum alone would 500 every API test (old fixtures mint `"OPERATOR"` tokens, `get_current_user` calls `.upper()`, and `UserRole("ADMIN")` no longer exists). Steps inside are small cycles; the suite is green again at the end of the task, with `require_authenticated_admin` still in place (removed in Task 6).

**Files:**
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/enums.py:137-140`
- Modify: `packages/smart_pid_domain/src/smart_pid_domain/dtos/auth.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py:51-84`
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py:341` (seed literal only)
- Modify: `tests/domain/test_models.py:90-93`, `tests/domain/test_dtos.py:35-40`
- Modify: `tests/conftest.py:51-53,110-127,140-147,169-170`
- Modify: `tests/core/api/test_ws_realtime.py:256-259`
- Modify: `packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py:171-197`, `tests/hmi/services/test_api_client_users.py`
- Test (new): `tests/core/unit/test_role_dependencies.py`
- Test (extend): `tests/core/integration/test_api_auth.py`

**Interfaces:**
- Consumes: `decode_access_token(token, *, secret) -> dict` and `create_access_token(*, user_id, username, role, secret, expiry_hours=8) -> str` (`api/auth.py`, unchanged).
- Produces (all later tasks rely on these):
  - `UserRole.ADMIN == "admin"`, `UserRole.USER == "user"` (`smart_pid_domain.enums.UserRole`, only two members).
  - `UserClaims(user_id: int, username: str, role: UserRole)` — unchanged shape, stricter runtime behavior.
  - `UserCreate(username: str, password: str, role: UserRole = UserRole.USER)` (spec §9.3's "RegisterRequest", reworked in place — the symbol keeps its real name).
  - `require_user(user: Annotated[UserClaims, Depends(get_current_user)]) -> UserClaims` — any authenticated principal.
  - `require_admin(user: Annotated[UserClaims, Depends(get_current_user)]) -> UserClaims` — 403 `{"detail": "Admin privileges required"}` unless `role == UserRole.ADMIN`.
  - `get_current_user` → 401 for **any** invalid claim set, including legacy role vocabulary.
  - conftest: `admin_headers` mints role `"admin"` (user_id 1, username `admin`); `user_headers` mints role `"user"` (user_id 2, username `operator`); seeds create `admin` with role `"admin"`.

- [ ] **Step 1: Write the failing dependency unit tests**

Create `tests/core/unit/test_role_dependencies.py`:

```python
"""Unit tests for the two-role gate dependencies (spec §9.1, §9.5)."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from smart_pid_core.adapters.inbound.api.auth import create_access_token
from smart_pid_core.adapters.inbound.api.dependencies import require_admin, require_user
from smart_pid_domain.dtos.auth import UserClaims

_SECRET = "unit-test-secret"


def _make_app() -> FastAPI:
    app = FastAPI()

    class _Settings:
        jwt_secret = _SECRET

    app.state.settings = _Settings()

    @app.get("/any")
    def any_route(user: Annotated[UserClaims, Depends(require_user)]) -> dict:
        return {"role": user.role.value}

    @app.get("/admin-only")
    def admin_route(user: Annotated[UserClaims, Depends(require_admin)]) -> dict:
        return {"role": user.role.value}

    return app


def _headers(role: str) -> dict[str, str]:
    token = create_access_token(
        user_id=1, username="someone", role=role, secret=_SECRET
    )
    return {"Authorization": f"Bearer {token}"}


class TestRequireUser:
    def test_user_role_passes(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/any", headers=_headers("user"))
        assert resp.status_code == 200
        assert resp.json() == {"role": "user"}

    def test_admin_role_passes(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/any", headers=_headers("admin"))
        assert resp.status_code == 200
        assert resp.json() == {"role": "admin"}

    def test_missing_header_401(self) -> None:
        client = TestClient(_make_app())
        assert client.get("/any").status_code == 401


class TestRequireAdmin:
    def test_admin_role_passes(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/admin-only", headers=_headers("admin"))
        assert resp.status_code == 200

    def test_user_role_403(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/admin-only", headers=_headers("user"))
        assert resp.status_code == 403
        assert resp.json() == {"detail": "Admin privileges required"}


class TestLegacyClaimRejection:
    """Spec §9.5: legacy vocabulary is rejected with 401 — never mapped."""

    def test_legacy_roles_rejected_on_user_gate(self) -> None:
        client = TestClient(_make_app())
        for legacy in ("ADMIN", "SUPERVISOR", "OPERATOR"):
            resp = client.get("/any", headers=_headers(legacy))
            assert resp.status_code == 401, f"role={legacy!r} must be 401"

    def test_legacy_admin_rejected_on_admin_gate(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/admin-only", headers=_headers("ADMIN"))
        assert resp.status_code == 401  # 401 (invalid token), NOT 403
```

- [ ] **Step 2: Run the new unit tests — verify they fail**

Run: `uv run pytest tests/core/unit/test_role_dependencies.py -q`
Expected: `ImportError: cannot import name 'require_admin' from 'smart_pid_core.adapters.inbound.api.dependencies'`

- [ ] **Step 3: Update the domain tests to the new vocabulary (failing)**

In `tests/domain/test_models.py`, replace the `test_user_role_values` method (lines 90-93):

```python
    def test_user_role_values(self) -> None:
        assert UserRole.ADMIN == "admin"
        assert UserRole.USER == "user"
        assert {r.value for r in UserRole} == {"admin", "user"}
```

In `tests/domain/test_dtos.py`, replace `test_user_create_default_role` and `test_user_claims` (lines 33-40 in class `TestAuthDTOs`) and add a rejection test. Add `import pytest` and `from pydantic import ValidationError` to the file's top-level imports; the method-local `from smart_pid_domain.enums import UserRole` import moves to the top of the file (it is now used by three methods):

```python
    def test_user_create_default_role(self) -> None:
        u = UserCreate(username="bob", password="pass")
        assert u.role == UserRole.USER

    def test_user_claims(self) -> None:
        c = UserClaims(user_id=1, username="admin", role="admin")
        assert c.user_id == 1
        assert c.role == UserRole.ADMIN

    def test_user_claims_rejects_legacy_role(self) -> None:
        with pytest.raises(ValidationError):
            UserClaims(user_id=1, username="admin", role="ADMIN")
```

- [ ] **Step 4: Run domain tests — verify they fail**

Run: `uv run pytest tests/domain/test_models.py tests/domain/test_dtos.py -q`
Expected: FAIL — `assert UserRole.ADMIN == "admin"` (`'ADMIN' != 'admin'`) and `AttributeError: USER`.

- [ ] **Step 5: Implement the domain change**

In `packages/smart_pid_domain/src/smart_pid_domain/enums.py`, replace the `UserRole` class (lines 137-140):

```python
class UserRole(StrEnum):
    """Authorization tiers (spec §9): exactly two roles, lowercase values.

    Legacy values ("ADMIN", "SUPERVISOR", "OPERATOR") were retired by the
    two-role model. Persisted rows are rewritten at startup by
    ``_migrate_user_roles`` (smart_pid_core.main); legacy JWT role claims are
    rejected with 401 (single forced re-login) and are never mapped.
    """

    ADMIN = "admin"
    USER = "user"
```

In `packages/smart_pid_domain/src/smart_pid_domain/dtos/auth.py`, change the pydantic import (line 4) and replace `UserCreate` (lines 19-22):

```python
from pydantic import BaseModel, Field
```

```python
class UserCreate(BaseModel):
    """Create-user request body for ``POST /users``.

    Spec §9.3 refers to this DTO as "RegisterRequest"; in this codebase the
    symbol has always been ``UserCreate`` (kept — not renamed). Dead code in
    the single-admin deployment, reactivated by the users router.
    """

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    role: UserRole = UserRole.USER
```

- [ ] **Step 6: Run domain tests — verify they pass**

Run: `uv run pytest tests/domain -q`
Expected: PASS (all domain tests; the two edited files plus untouched neighbors).

- [ ] **Step 7: Implement strict claims + the two dependencies**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`:

Add to the runtime imports (after line 9, next to the `UserClaims` import):

```python
from smart_pid_domain.enums import UserRole
```

Replace `get_current_user` (lines 51-72) — the `.upper()` mapping disappears and *every* failure inside the `try` becomes 401:

```python
def get_current_user(request: Request) -> UserClaims:
    """Extract and validate JWT from Authorization header.

    Any failure — bad signature, expiry, missing claims, or a legacy role
    vocabulary ("ADMIN"/"SUPERVISOR"/"OPERATOR") — yields 401 so the client
    performs a single forced re-login (spec §9.5). Legacy claims are never
    mapped to the new roles.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    token = auth_header.removeprefix("Bearer ")
    settings: CoreSettings = request.app.state.settings
    try:
        payload = decode_access_token(token, secret=settings.jwt_secret)
        return UserClaims(
            user_id=payload["sub"],
            username=payload["username"],
            role=payload["role"],  # strict: only "admin" | "user" validate
        )
    except Exception:
        # jwt.PyJWTError, KeyError, pydantic.ValidationError — all 401.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None
```

Immediately after `get_current_user`, add the two gates. **Keep `require_authenticated_admin` unchanged for now** (63 call sites still point at it; Task 6 deletes it):

```python
def require_user(
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> UserClaims:
    """Gate: any authenticated principal (role ``admin`` or ``user``)."""
    return user


def require_admin(
    user: Annotated[UserClaims, Depends(get_current_user)],
) -> UserClaims:
    """Gate: authenticated ``admin`` only; any other role → 403 (spec §9)."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user
```

- [ ] **Step 8: Run the unit tests — verify they pass; observe the harness break**

Run: `uv run pytest tests/core/unit/test_role_dependencies.py -q`
Expected: PASS (7 passed).

Run: `uv run pytest tests/core/integration/test_api_controllers.py -q`
Expected: FAIL — every request in that file authenticates with fixture tokens still minted as `role="ADMIN"`/`"OPERATOR"` (legacy vocabulary), so strict `get_current_user` answers 401 where the tests expect 200/201/404. (`test_api_auth.py`'s login tests still pass — they post credentials, and the seeded DB row is fixed in the next step.) This is the cue to fix the *harness*, not the code.

- [ ] **Step 9: Flip every legacy role literal in the test harness, seed line, and pydantic-coupled HMI files**

`tests/conftest.py`:
- Line 53: `await user_repo.create("admin", admin_hash, "ADMIN")` → `await user_repo.create("admin", admin_hash, "admin")`
- Line 170 (sim fixture): same change.
- `admin_headers` (line 114): `role="ADMIN"` → `role="admin"`.
- `user_headers` (line 124): `role="OPERATOR"` → `role="user"`; docstring → `"""Pre-authenticated user-role JWT headers."""`
- `supervisor_headers` (lines 140-147): keep the fixture **temporarily** so its consumers stay green until Task 6 adapts them, but mint the new vocabulary:

```python
@pytest.fixture
def supervisor_headers(api_deps) -> dict[str, str]:
    """TEMPORARY alias of admin_headers (distinct identity, user_id 3).

    The SUPERVISOR tier no longer exists (spec §9.4 maps it to admin).
    Removed in the call-site-switch task once consumers migrate to
    admin_headers.
    """
    token = create_access_token(
        user_id=3, username="supervisor", role="admin",
        secret=api_deps["settings"].jwt_secret,
    )
    return {"Authorization": f"Bearer {token}"}
```

`packages/smart_pid_core/src/smart_pid_core/main.py` line 341:

```python
        await user_repo.create("admin", admin_hash, "admin")
```

`tests/core/api/test_ws_realtime.py` `_good_token` (lines 256-259):

```python
def _good_token() -> str:
    return create_access_token(
        user_id=1, username="admin", role="admin", secret=_SECRET
    )
```

`packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py` — the HMI is frozen, but these five literals construct `UserResponse` (pydantic, shared `UserRole`) and would crash the suite; flip only them:
- Line 172: `role="ADMIN"` → `role="admin"`
- Lines 175, 178: `role="OPERATOR"` → `role="user"`
- Line 190: `role=role or "OPERATOR"` → `role=role or "user"`
- Line 196: `role="OPERATOR"` → `role="user"`
(Do **not** touch `main.py:1477-1479`, `user_management_page.py`, or the mock JWT at `mock_service.py:87` — those compare plain strings and keep working; `"admin".upper() == "ADMIN"` still holds.)

`tests/hmi/services/test_api_client_users.py` — same reason (`UserResponse.model_validate` on dict literals):
- Line 25: `"role": "ADMIN"` → `"role": "admin"`
- Lines 26, 37, 52: `"role": "OPERATOR"` → `"role": "user"`
- Line 33: `assert users[1].role == "OPERATOR"` → `== "user"`
- Line 39: `client.create_user("newuser", "pass123", "OPERATOR")` → `"user"`
- Line 41: `assert user.role == "OPERATOR"` → `== "user"`
- Line 45: `"role": "SUPERVISOR"` → `"role": "admin"`
- Line 47: `client.update_user(2, role="SUPERVISOR")` → `role="admin"`
- Line 48: `assert user.role == "SUPERVISOR"` → `== "admin"`

- [ ] **Step 10: Add the API-level legacy-claim test (spec §9.5 contract at route level)**

Append to `tests/core/integration/test_api_auth.py` (add the import at the top of the file):

```python
from smart_pid_core.adapters.inbound.api.auth import create_access_token
```

```python
class TestLegacyRoleClaims:
    """Spec §9.5: tokens minted before the cutover carry uppercase roles for
    up to 8h. They are rejected with 401 — one forced re-login, no mapping."""

    @pytest.mark.asyncio
    async def test_legacy_role_claims_rejected_with_401(
        self, client: AsyncClient, api_deps: dict
    ) -> None:
        for legacy_role in ("ADMIN", "SUPERVISOR", "OPERATOR"):
            token = create_access_token(
                user_id=1,
                username="admin",
                role=legacy_role,
                secret=api_deps["settings"].jwt_secret,
            )
            resp = await client.get(
                "/controllers", headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code == 401, f"role={legacy_role!r} must be 401"

    @pytest.mark.asyncio
    async def test_login_now_mints_lowercase_role_accepted_by_api(
        self, client: AsyncClient
    ) -> None:
        login = await client.post(
            "/auth/login", json={"username": "admin", "password": "admin"}
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        resp = await client.get(
            "/controllers", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
```

- [ ] **Step 11: Run the backend suite — verify green**

Run: `uv run pytest tests/core tests/domain -q`
Expected: PASS (no failures; `require_authenticated_admin` still gates by authentication only, so all pre-existing role-free assertions hold).

Run: `uv run pytest tests/hmi/services/test_api_client_users.py -q`
Expected: PASS (4 passed).

- [ ] **Step 12: Commit**

```bash
git add packages/smart_pid_domain/src/smart_pid_domain/enums.py \
        packages/smart_pid_domain/src/smart_pid_domain/dtos/auth.py \
        packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py \
        packages/smart_pid_core/src/smart_pid_core/main.py \
        packages/smart_pid_hmi/src/smart_pid_hmi/services/mock_service.py \
        tests/conftest.py tests/domain/test_models.py tests/domain/test_dtos.py \
        tests/core/unit/test_role_dependencies.py \
        tests/core/integration/test_api_auth.py \
        tests/core/api/test_ws_realtime.py \
        tests/hmi/services/test_api_client_users.py
git commit -m "feat(core): cut role vocabulary over to two-tier admin/user model"
```

---

### Task 2: `GET /auth/me` and uniform gate on `/auth/refresh`

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py`
- Test: `tests/core/integration/test_api_auth.py`

**Interfaces:**
- Consumes: `require_user` (Task 1), `UserClaims`, `TokenResponse` (unchanged: `{access_token: str, token_type: "bearer"}`).
- Produces: `GET /auth/me` → 200 `{"user_id": int, "username": str, "role": "admin"|"user"}` (response_model `UserClaims`), 401 without/with-invalid token. Phase 3's `AuthContext` populates from this route after login and refetches it on any 403 (spec §11); phase 2 codegen picks it up from the OpenAPI schema. `POST /auth/refresh` behavior unchanged (fresh token for any authenticated principal).

- [ ] **Step 1: Write the failing tests**

Append to `tests/core/integration/test_api_auth.py`:

```python
class TestMe:
    @pytest.mark.asyncio
    async def test_me_returns_admin_claims(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json() == {"user_id": 1, "username": "admin", "role": "admin"}

    @pytest.mark.asyncio
    async def test_me_returns_user_claims(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/auth/me", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json() == {"user_id": 2, "username": "operator", "role": "user"}

    @pytest.mark.asyncio
    async def test_me_requires_token(self, client: AsyncClient) -> None:
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_works_for_user_role(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post("/auth/refresh", headers=user_headers)
        assert resp.status_code == 200
        assert "access_token" in resp.json()
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/core/integration/test_api_auth.py::TestMe -q`
Expected: FAIL — `assert 404 == 200` (route `/auth/me` does not exist yet); the refresh test passes already.

- [ ] **Step 3: Implement**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py`:

Change the dependencies import (lines 12-17) — `get_current_user` is replaced by `require_user`:

```python
from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    get_settings,
    get_user_repo,
    require_user,
)
```

Switch `refresh_token`'s gate (line 57):

```python
    current_user: Annotated[UserClaims, Depends(require_user)],
```

Append the new route after `refresh_token`:

```python
@router.get("/me", response_model=UserClaims)
async def me(
    current_user: Annotated[UserClaims, Depends(require_user)],
) -> UserClaims:
    """Return the authenticated principal's claims.

    The SPA populates its AuthContext from this route after login and
    refetches it whenever a 403 arrives (spec §11) — a role changed
    mid-session is discovered here, not by decoding the JWT client-side.
    """
    return current_user
```

- [ ] **Step 4: Run — verify pass**

Run: `uv run pytest tests/core/integration/test_api_auth.py -q`
Expected: PASS (all classes: login, JWT validation, legacy claims, me, refresh).

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/auth.py \
        tests/core/integration/test_api_auth.py
git commit -m "feat(core): add GET /auth/me returning authenticated claims"
```

---

### Task 3: Realtime WS rejects legacy-role tokens

`/ws/realtime` first-message auth only verifies the JWT signature/expiry. A legacy-vocabulary token (valid for up to 8h) must not keep streaming telemetry after REST already forced a re-login — same §9.5 rule, same session-wide cutover.

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py:219-223`
- Test: `tests/core/api/test_ws_realtime.py`

**Interfaces:**
- Consumes: `UserRole` (Task 1), `decode_access_token`, `_WS_CLOSE_AUTH` (= 4401, already defined in `realtime.py`).
- Produces: WS close code **4401** for any token whose `role` claim is not `"admin"`/`"user"`. Phase 3's `RealtimeProvider` treats 4401 as "force re-login" (spec §11) — no new close code is introduced.

- [ ] **Step 1: Write the failing test**

Append to `tests/core/api/test_ws_realtime.py` (after `test_ws_rejects_bad_origin`, reusing `_make_app`, `_SECRET`, `_ALLOWED_ORIGIN`):

```python
def test_ws_rejects_legacy_role_token() -> None:
    """Spec §9.5 applies to the socket too: legacy vocabulary => 4401."""
    app = _make_app()
    client = TestClient(app)
    for legacy in ("ADMIN", "SUPERVISOR", "OPERATOR"):
        legacy_token = create_access_token(
            user_id=1, username="admin", role=legacy, secret=_SECRET
        )
        with client.websocket_connect(
            "/ws/realtime", headers={"origin": _ALLOWED_ORIGIN}
        ) as ws:
            ws.send_json({"type": "auth", "token": legacy_token})
            with pytest.raises(WebSocketDisconnect) as exc:
                ws.receive_text()
        assert exc.value.code == 4401, f"role={legacy!r} must close 4401"
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/core/api/test_ws_realtime.py::test_ws_rejects_legacy_role_token -q`
Expected: FAIL — the server answers `{"type": "auth_ok"}` (signature is valid), so `receive_text()` returns instead of raising; pytest reports `Failed: DID NOT RAISE <class 'starlette.websockets.WebSocketDisconnect'>`.

- [ ] **Step 3: Implement**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py`:

Add the import next to the existing `decode_access_token` import (line 21):

```python
from smart_pid_domain.enums import UserRole
```

Add a module-level constant near the other `_`-constants:

```python
_VALID_ROLES = frozenset(role.value for role in UserRole)
```

Replace the decode block (lines 219-223):

```python
        try:
            payload = decode_access_token(token, secret=settings.jwt_secret)
        except Exception:  # noqa: BLE001 — any JWT error => reject
            await websocket.close(code=_WS_CLOSE_AUTH)
            return
        if payload.get("role") not in _VALID_ROLES:
            # Legacy vocabulary ("ADMIN"/"SUPERVISOR"/"OPERATOR") => forced
            # re-login (spec §9.5) — REST and WS cut over together.
            await websocket.close(code=_WS_CLOSE_AUTH)
            return
```

- [ ] **Step 4: Run — verify pass**

Run: `uv run pytest tests/core/api/test_ws_realtime.py -q`
Expected: PASS (whole file, including the pre-existing accept/reject tests — `_good_token` already mints `"admin"` since Task 1).

- [ ] **Step 5: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/ws/realtime.py \
        tests/core/api/test_ws_realtime.py
git commit -m "feat(core): reject legacy-role JWTs on the realtime websocket"
```

---

### Task 4: Admin-gated `/users` management router

New surface per spec §9.3: list / create / update role / change password / deactivate — all behind `require_admin`. `UserCreate` (Task 1) is the request body for create; `UserUpdate`/`UserResponse` already exist in the domain. A lockout guard refuses to demote or deactivate the **last active admin** (409): `users.db` is standalone, so a deployment with zero active admins can never manage users again.

**Files:**
- Create: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/users.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py:15-30,174`
- Test: `tests/core/integration/test_api_users.py`

**Interfaces:**
- Consumes: `require_admin`, `get_user_repo`, `get_audit_repo` (dependencies.py); `UserRepository.create/list_all/get_by_id/update/deactivate` and dataclass `User` (`adapters/outbound/user_repo.py`); `hash_password` (`api/auth.py`); `UserCreate` (Task 1); `UserResponse`, `UserUpdate` (`smart_pid_domain/dtos/users.py`); `AuditAction.CREATE_USER/UPDATE_USER/DEACTIVATE_USER`; `AuditRepository.record(user_id, username, action, resource, detail)`.
- Produces (phase 2 codegen + phase 10 users UI consume these exactly):
  - `GET /users` → 200 `list[UserResponse]`
  - `POST /users` body `UserCreate {username, password, role?="user"}` → 201 `UserResponse`; 409 duplicate username; 422 invalid role/empty fields
  - `PATCH /users/{user_id}` body `UserUpdate {role?, password?, active?}` → 200 `UserResponse`; 404 unknown id; 409 last-admin demotion/deactivation
  - `DELETE /users/{user_id}` → 200 `UserResponse` (soft-deactivate); 404 unknown id; 409 last admin
  - All four: 401 unauthenticated, 403 for role `user`
  - `UserResponse` JSON: `{"id": int, "username": str, "role": "admin"|"user", "active": bool, "created_at": str}`

- [ ] **Step 1: Write the failing tests**

Create `tests/core/integration/test_api_users.py`:

```python
"""Tests for the admin-gated /users management router (spec §9.3)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


async def _create(client: AsyncClient, headers: dict[str, str], username: str,
                  password: str = "pw123", role: str = "user") -> dict:
    resp = await client.post(
        "/users",
        json={"username": username, "password": password, "role": role},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestListUsers:
    @pytest.mark.asyncio
    async def test_admin_lists_seeded_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/users", headers=admin_headers)
        assert resp.status_code == 200
        users = resp.json()
        assert len(users) == 1
        assert users[0]["username"] == "admin"
        assert users[0]["role"] == "admin"
        assert users[0]["active"] is True
        assert set(users[0]) == {"id", "username", "role", "active", "created_at"}

    @pytest.mark.asyncio
    async def test_user_role_forbidden(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.get("/users", headers=user_headers)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_401(self, client: AsyncClient) -> None:
        resp = await client.get("/users")
        assert resp.status_code == 401


class TestCreateUser:
    @pytest.mark.asyncio
    async def test_create_then_login_round_trip(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        created = await _create(client, admin_headers, "op1", password="secret1")
        assert created["role"] == "user"
        assert created["active"] is True
        login = await client.post(
            "/auth/login", json={"username": "op1", "password": "secret1"}
        )
        assert login.status_code == 200

    @pytest.mark.asyncio
    async def test_duplicate_username_409(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        await _create(client, admin_headers, "dup")
        resp = await client.post(
            "/users",
            json={"username": "dup", "password": "x", "role": "user"},
            headers=admin_headers,
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_legacy_role_body_422(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/users",
            json={"username": "x", "password": "x", "role": "SUPERVISOR"},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_user_role_forbidden(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/users",
            json={"username": "nope", "password": "x", "role": "user"},
            headers=user_headers,
        )
        assert resp.status_code == 403


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_promote_to_admin(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        created = await _create(client, admin_headers, "promoted")
        resp = await client.patch(
            f"/users/{created['id']}", json={"role": "admin"}, headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    @pytest.mark.asyncio
    async def test_change_password_round_trip(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        created = await _create(client, admin_headers, "pwuser", password="old-pw")
        resp = await client.patch(
            f"/users/{created['id']}", json={"password": "new-pw"}, headers=admin_headers
        )
        assert resp.status_code == 200
        assert (await client.post(
            "/auth/login", json={"username": "pwuser", "password": "new-pw"}
        )).status_code == 200
        assert (await client.post(
            "/auth/login", json={"username": "pwuser", "password": "old-pw"}
        )).status_code == 401

    @pytest.mark.asyncio
    async def test_unknown_id_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.patch(
            "/users/9999", json={"role": "user"}, headers=admin_headers
        )
        assert resp.status_code == 404


class TestDeactivateUser:
    @pytest.mark.asyncio
    async def test_deactivated_user_cannot_login(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        created = await _create(client, admin_headers, "leaver", password="bye")
        resp = await client.delete(f"/users/{created['id']}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["active"] is False
        login = await client.post(
            "/auth/login", json={"username": "leaver", "password": "bye"}
        )
        assert login.status_code == 401  # get_by_username filters ativo = 1

    @pytest.mark.asyncio
    async def test_unknown_id_404(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.delete("/users/9999", headers=admin_headers)
        assert resp.status_code == 404


class TestLastAdminGuard:
    """users.db is standalone: zero active admins == permanent lockout."""

    @pytest.mark.asyncio
    async def test_demoting_sole_admin_409(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.patch("/users/1", json={"role": "user"}, headers=admin_headers)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_deactivating_sole_admin_409(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.delete("/users/1", headers=admin_headers)
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_demotion_allowed_once_second_admin_exists(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        await _create(client, admin_headers, "admin2", role="admin")
        resp = await client.patch("/users/1", json={"role": "user"}, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["role"] == "user"
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/core/integration/test_api_users.py -q`
Expected: FAIL — no `/users` routes are mounted, so FastAPI answers 404 for the unknown paths: every 200/201/403/409 assertion fails (e.g. `assert 404 == 201` in `_create`). Only the two `test_unknown_id_404` cases pass vacuously (404 for a different reason); they gain their real meaning once the router exists.

- [ ] **Step 3: Implement the router**

Create `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/users.py`:

```python
"""User management router — admin-gated (spec §9.3).

New surface introduced by the two-role model: list / create / update role /
change password / deactivate. Every route requires ``require_admin``; the
frontend management panel arrives in phase 10.
"""
from __future__ import annotations

from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status

from smart_pid_core.adapters.inbound.api.auth import hash_password
from smart_pid_core.adapters.inbound.api.dependencies import (
    get_audit_repo,
    get_user_repo,
    require_admin,
)
from smart_pid_core.adapters.outbound.audit_repo import AuditRepository  # noqa: TC001
from smart_pid_core.adapters.outbound.user_repo import User, UserRepository  # noqa: TC001
from smart_pid_domain.dtos.auth import UserClaims, UserCreate  # noqa: TC001
from smart_pid_domain.dtos.users import UserResponse, UserUpdate  # noqa: TC001
from smart_pid_domain.enums import AuditAction, UserRole

router = APIRouter()


def _to_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        role=UserRole(user.role),
        active=user.active,
        created_at=user.created_at,
    )


async def _reject_if_last_active_admin(
    user_repo: UserRepository, user_id: int
) -> None:
    """409 when the change would leave zero active admins.

    Lockout guard: users.db is standalone (never inside .spid), so with no
    active admin left, user management — and every admin capability — becomes
    permanently unreachable.
    """
    target = await user_repo.get_by_id(user_id)
    if target is None or not target.active or target.role != UserRole.ADMIN:
        return  # not an active admin — nothing to protect
    admins = [
        u for u in await user_repo.list_all()
        if u.active and u.role == UserRole.ADMIN
    ]
    if len(admins) <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot demote or deactivate the last active admin",
        )


@router.get("", response_model=list[UserResponse])
async def list_users(
    _admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> list[UserResponse]:
    return [_to_response(u) for u in await user_repo.list_all()]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreate,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    try:
        created = await user_repo.create(
            body.username, hash_password(body.password), body.role.value
        )
    except aiosqlite.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        ) from None
    await audit_repo.record(
        admin.user_id, admin.username, AuditAction.CREATE_USER,
        body.username, f"role={body.role.value}",
    )
    return _to_response(created)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdate,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    if await user_repo.get_by_id(user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if body.role == UserRole.USER or body.active is False:
        await _reject_if_last_active_admin(user_repo, user_id)
    updated = await user_repo.update(
        user_id,
        role=body.role.value if body.role is not None else None,
        password_hash=hash_password(body.password) if body.password is not None else None,
        active=body.active,
    )
    if updated is None:  # pragma: no cover — guarded by the 404 above
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    changed = [
        name
        for name, value in (
            ("role", body.role), ("password", body.password), ("active", body.active)
        )
        if value is not None
    ]
    await audit_repo.record(
        admin.user_id, admin.username, AuditAction.UPDATE_USER,
        updated.username, f"changed={','.join(changed) or 'nothing'}",
    )
    return _to_response(updated)


@router.delete("/{user_id}", response_model=UserResponse)
async def deactivate_user(
    user_id: int,
    admin: Annotated[UserClaims, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    audit_repo: Annotated[AuditRepository, Depends(get_audit_repo)],
) -> UserResponse:
    if await user_repo.get_by_id(user_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    await _reject_if_last_active_admin(user_repo, user_id)
    updated = await user_repo.deactivate(user_id)
    if updated is None:  # pragma: no cover — guarded by the 404 above
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    await audit_repo.record(
        admin.user_id, admin.username, AuditAction.DEACTIVATE_USER,
        updated.username, None,
    )
    return _to_response(updated)
```

- [ ] **Step 4: Wire the router into the app**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py`:

Add `users` to the routers import block (lines 15-30, keep alphabetical-ish order — after `system_events`):

```python
from smart_pid_core.adapters.inbound.api.routers import (
    ai,
    alarms,
    audit,
    auth,
    commands,
    controllers,
    export,
    history,
    opcua,
    project,
    simulator,
    stats,
    system,
    system_events,
    users,
)
```

After the `export` include (line 174), add:

```python
    app.include_router(users.router, prefix="/users", tags=["users"])
```

- [ ] **Step 5: Run — verify pass**

Run: `uv run pytest tests/core/integration/test_api_users.py -q`
Expected: PASS (15 passed).

- [ ] **Step 6: Run neighbors to catch wiring regressions**

Run: `uv run pytest tests/core/integration/test_api_auth.py tests/core/integration/test_api_controllers.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/users.py \
        packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/app.py \
        tests/core/integration/test_api_users.py
git commit -m "feat(core): add admin-gated /users management router"
```

---

### Task 5: Role-value data migration, DDL default, seed helper

Spec §9.4 (mandatory): existing `users.db` rows hold `'ADMIN'`/`'SUPERVISOR'`/`'OPERATOR'` — after Task 1 those rows mint tokens that 401 forever (login works, every API call fails). A startup `UPDATE` rewrites them; the DDL default flips to `'user'`; the seed block becomes a testable helper seeding role `'admin'`. The migration runs at **every** startup (each `UPDATE` matches zero rows once migrated — idempotent), which also self-heals any stray uppercase row that a pre-existing database's stale `DEFAULT 'OPERATOR'` could produce (SQLite cannot `ALTER COLUMN SET DEFAULT`, and `CREATE TABLE IF NOT EXISTS` never rewrites an existing table).

**Files:**
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py:27`
- Modify: `packages/smart_pid_core/src/smart_pid_core/main.py` (imports; new helpers after `_migrate_users_if_needed`; run() block lines 335-346)
- Test: `tests/core/integration/test_user_role_migration.py`

**Interfaces:**
- Consumes: `UserRepository` (`db` property, `initialize`, `list_all`, `create`), `hash_password`, `UserRole` (Task 1).
- Produces (phase 1 re-expresses these two, same names, on the SQLAlchemy engine C):
  - `async def _migrate_user_roles(user_repo: UserRepository) -> None` — module-level in `smart_pid_core/main.py`, executes raw `UPDATE Usuarios SET perfil = ? WHERE perfil = ?` via `user_repo.db.execute` for each `(legacy, new)` pair in `_ROLE_VALUE_MAP`, then commits.
  - `_ROLE_VALUE_MAP: tuple[tuple[str, str], ...] = (("ADMIN", "admin"), ("SUPERVISOR", "admin"), ("OPERATOR", "user"))`
  - `async def _seed_default_admin(user_repo: UserRepository) -> None` — creates `admin`/`admin` with role `UserRole.ADMIN.value` when `list_all()` is empty.
  - `_USERS_DDL` default: `perfil TEXT NOT NULL DEFAULT 'user'`.

- [ ] **Step 1: Write the failing tests**

Create `tests/core/integration/test_user_role_migration.py`:

```python
"""Role-value migration tests (spec §9.4, §14 "3-role fixture users.db").

Legacy databases hold uppercase roles: ADMIN → admin, SUPERVISOR → admin
(they held tuning/config powers), OPERATOR → user. The fixture builds the
users.db with the PRE-cutover DDL (DEFAULT 'OPERATOR') exactly as a field
deployment would have it.
"""
from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from smart_pid_core.adapters.inbound.api.auth import hash_password, verify_password
from smart_pid_core.adapters.outbound.user_repo import UserRepository
from smart_pid_core.main import _migrate_user_roles, _seed_default_admin

_LEGACY_DDL = """
CREATE TABLE Usuarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL UNIQUE,
    senha_hash  TEXT    NOT NULL,
    perfil      TEXT    NOT NULL DEFAULT 'OPERATOR',
    ativo       INTEGER NOT NULL DEFAULT 1,
    criado_em   TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


async def _make_legacy_users_db(path: Path) -> None:
    async with aiosqlite.connect(path) as db:
        await db.executescript(_LEGACY_DDL)
        await db.executemany(
            "INSERT INTO Usuarios (nome, senha_hash, perfil, ativo) VALUES (?, ?, ?, ?)",
            [
                ("root", "hash-a", "ADMIN", 1),
                ("chief", "hash-s", "SUPERVISOR", 1),
                ("op1", "hash-o", "OPERATOR", 0),
            ],
        )
        await db.commit()


async def _roles_by_name(repo: UserRepository) -> dict[str, str]:
    return {u.username: u.role for u in await repo.list_all()}


class TestRoleValueMigration:
    @pytest.mark.asyncio
    async def test_three_legacy_roles_are_mapped(self, tmp_path: Path) -> None:
        db_path = tmp_path / "users.db"
        await _make_legacy_users_db(db_path)
        repo = UserRepository(db_path)
        await repo.initialize()
        await _migrate_user_roles(repo)
        assert await _roles_by_name(repo) == {
            "root": "admin",
            "chief": "admin",   # SUPERVISOR held tuning/config powers
            "op1": "user",
        }
        await repo.close()

    @pytest.mark.asyncio
    async def test_migration_is_idempotent_and_preserves_other_columns(
        self, tmp_path: Path
    ) -> None:
        db_path = tmp_path / "users.db"
        await _make_legacy_users_db(db_path)
        repo = UserRepository(db_path)
        await repo.initialize()
        await _migrate_user_roles(repo)
        await _migrate_user_roles(repo)  # second run: zero rows touched
        users = {u.username: u for u in await repo.list_all()}
        assert users["root"].password_hash == "hash-a"
        assert users["op1"].active is False
        assert users["op1"].role == "user"
        assert len(users) == 3
        await repo.close()

    @pytest.mark.asyncio
    async def test_new_vocabulary_rows_untouched(self, tmp_path: Path) -> None:
        db_path = tmp_path / "users.db"
        repo = UserRepository(db_path)
        await repo.initialize()
        await repo.create("fresh", "h", "user")
        await _migrate_user_roles(repo)
        assert (await _roles_by_name(repo))["fresh"] == "user"
        await repo.close()


class TestDDLDefault:
    @pytest.mark.asyncio
    async def test_fresh_db_defaults_perfil_to_user(self, tmp_path: Path) -> None:
        repo = UserRepository(tmp_path / "users.db")
        await repo.initialize()
        await repo.db.execute(
            "INSERT INTO Usuarios (nome, senha_hash) VALUES ('nodefault', 'h')"
        )
        await repo.db.commit()
        assert (await _roles_by_name(repo))["nodefault"] == "user"
        await repo.close()


class TestSeedDefaultAdmin:
    @pytest.mark.asyncio
    async def test_seeds_admin_role_admin_on_empty_db(self, tmp_path: Path) -> None:
        repo = UserRepository(tmp_path / "users.db")
        await repo.initialize()
        await _seed_default_admin(repo)
        users = await repo.list_all()
        assert len(users) == 1
        assert users[0].username == "admin"
        assert users[0].role == "admin"
        assert users[0].active is True
        assert verify_password("admin", users[0].password_hash)
        await repo.close()

    @pytest.mark.asyncio
    async def test_noop_when_users_exist(self, tmp_path: Path) -> None:
        repo = UserRepository(tmp_path / "users.db")
        await repo.initialize()
        await repo.create("existing", hash_password("x"), "user")
        await _seed_default_admin(repo)
        users = await repo.list_all()
        assert [u.username for u in users] == ["existing"]
        await repo.close()
```

- [ ] **Step 2: Run — verify failure**

Run: `uv run pytest tests/core/integration/test_user_role_migration.py -q`
Expected: FAIL at collection — `ImportError: cannot import name '_migrate_user_roles' from 'smart_pid_core.main'`.

- [ ] **Step 3: Implement**

In `packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py`, change the DDL default (line 27):

```python
    perfil      TEXT    NOT NULL DEFAULT 'user',
```

In `packages/smart_pid_core/src/smart_pid_core/main.py`:

Add the import (with the other domain imports near the top; there are none yet, so place it after line 26 `from smart_pid_core.config import CoreSettings`):

```python
from smart_pid_domain.enums import UserRole
```

Insert after `_migrate_users_if_needed` (after line 157):

```python
_ROLE_VALUE_MAP: tuple[tuple[str, str], ...] = (
    ("ADMIN", "admin"),
    ("SUPERVISOR", "admin"),  # held tuning/config powers → admin (spec §9.4)
    ("OPERATOR", "user"),
)


async def _migrate_user_roles(user_repo: UserRepository) -> None:
    """Rewrite legacy role values in users.db (spec §9.4).

    Runs at every startup; each UPDATE matches zero rows once migrated, so
    the call is idempotent. Without it, legacy rows mint tokens that fail
    UserClaims validation and every legacy login is locked out for good.
    """
    migrated = 0
    for legacy, new in _ROLE_VALUE_MAP:
        cursor = await user_repo.db.execute(
            "UPDATE Usuarios SET perfil = ? WHERE perfil = ?", (new, legacy),
        )
        migrated += max(cursor.rowcount, 0)
    await user_repo.db.commit()
    if migrated:
        logger.info("migrated_user_roles", rows=migrated)


async def _seed_default_admin(user_repo: UserRepository) -> None:
    """Create the default admin account when users.db has no rows."""
    users = await user_repo.list_all()
    if users:
        return
    admin_hash = hash_password("admin")
    await user_repo.create("admin", admin_hash, UserRole.ADMIN.value)
    logger.warning(
        "seeded_default_admin",
        msg="SECURITY: Default admin account created with password 'admin'. "
        "Change it immediately.",
    )
```

Replace the run() block (lines 335-346, currently repo-construct → initialize → list → inline seed):

```python
    # Phase 2: User repo + role-value migration + seed admin (standalone DB)
    user_repo = UserRepository(settings.users_db_path)
    await user_repo.initialize()
    await _migrate_user_roles(user_repo)
    await _seed_default_admin(user_repo)
```

(The `_migrate_users_if_needed(...)` call at line 333 stays exactly where it is — it runs **before** this block, so a fresh install pointed at an old `.spid` gets its verbatim-copied uppercase rows normalized by `_migrate_user_roles` in the same startup.)

- [ ] **Step 4: Run — verify pass**

Run: `uv run pytest tests/core/integration/test_user_role_migration.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Run the user-repo and legacy-migration neighbors**

Run: `uv run pytest tests/core/integration/test_user_repo.py tests/core/integration/test_user_migration.py tests/core/integration/test_main_wiring.py -q`
Expected: PASS (the `.spid → users.db` copy tests are unaffected: they assert row counts/usernames, not role values).

- [ ] **Step 6: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/outbound/user_repo.py \
        packages/smart_pid_core/src/smart_pid_core/main.py \
        tests/core/integration/test_user_role_migration.py
git commit -m "feat(core): migrate legacy user role values and seed admin as 'admin'"
```

---

### Task 6: The switch — 63 call sites re-gated + 403-per-route contract test

The contract test is written **first** against Appendix A; it fails while routes still use `require_authenticated_admin` (a `user` token passes gates that must 403). Then every router is swapped, the old gate is deleted, and the pre-existing tests that encoded the single-admin world ("any authenticated user allowed") are flipped to the two-role contract.

**Files:**
- Create: `tests/core/integration/test_role_contract.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/{ai,alarms,audit,commands,controllers,export,history,opcua,project,simulator,stats,system_events}.py`
- Modify: `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py` (delete `require_authenticated_admin`)
- Modify: `tests/conftest.py` (delete `supervisor_headers`)
- Modify: `tests/core/integration/{test_ai_control_endpoints,test_alarm_config_crud,test_api_commands,test_api_controllers,test_api_optimization_toggle,test_api_project,test_project_auth_required}.py`

**Interfaces:**
- Consumes: `require_user`, `require_admin` (Task 1), `/users` routes (Task 4), Appendix A (normative classification).
- Produces: every route enforces its Appendix-A gate; `require_authenticated_admin` no longer exists anywhere; `tests/core/integration/test_role_contract.py::ADMIN_ONLY_ROUTES` / `USER_ALLOWED_ROUTES` are the machine-readable form of Appendix A (phases 4–10 consult them when wiring `useCan` and the `user`-role E2E spec).

- [ ] **Step 1: Write the failing contract test**

Create `tests/core/integration/test_role_contract.py`:

```python
"""Parametrised 403-per-route authorization contract (spec §9.2, §12).

Machine-readable form of the phase-0 plan's Appendix A. Two token classes
hit every gated route:

- role "user"  → EXACTLY 403 on admin-only routes; NEVER 401/403 on
  user-allowed routes;
- role "admin" → NEVER 401/403 anywhere. Business outcomes vary with fixture
  state (404 unknown ids, 409 conflicts, 422 imperfect bodies, 404 absent
  simulator/OPC-UA adapters) — the contract asserts the GATE, not the
  business result.

FastAPI resolves dependencies before request-body validation, so 403 always
wins over 422; bodies below are best-effort valid to keep admin-side
responses meaningful.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

_WINDOW = "start=2026-01-01T00:00:00&end=2026-12-31T00:00:00"

# (method, path, json-body-or-None) — every admin-only route except the
# multipart POST /project/import (covered by TestProjectImportGate below).
ADMIN_ONLY_ROUTES: list[tuple[str, str, dict | None]] = [
    # controllers
    ("post", "/controllers", {"name": "RBAC-TEST"}),
    ("put", "/controllers/9999", {"name": "renamed"}),
    ("delete", "/controllers/9999", None),
    ("put", "/controllers/9999/alarm-config", {"thresholds": []}),
    # ai (under /controllers prefix)
    ("post", "/controllers/9999/ai/start", None),
    ("post", "/controllers/9999/ai/stop", None),
    ("post", "/controllers/9999/ai/pause", None),
    # commands
    ("post", "/commands/optimization", {"controller_id": 9999, "enabled": True}),
    ("post", "/commands/tuning", {"controller_id": 9999, "kp": 1.0}),
    ("post", "/commands/apply-tuning/9999", None),
    # opcua (adapter absent in this fixture → admin side sees 404, never 401/403)
    ("get", "/opcua/browse/ns=0;i=85", None),
    ("get", "/opcua/search?q=temp", None),
    ("put", "/opcua/endpoint", {"endpoint": "opc.tcp://127.0.0.1:4840"}),
    ("post", "/opcua/connect", None),
    ("post", "/opcua/disconnect", None),
    # project
    ("post", "/project/new", {"name": "rbac-contract"}),
    ("post", "/project/open", {"name": "nonexistent"}),
    ("get", "/project/list", None),
    ("get", "/project/download", None),
    ("delete", "/project/nonexistent", None),
    # simulator — admin-only EXCEPT twin sp/mode/co (spec §9.2)
    ("post", "/simulator/start", None),
    ("post", "/simulator/stop", None),
    ("get", "/simulator/status", None),
    ("get", "/simulator/opcua/status", None),
    ("post", "/simulator/opcua/start", None),
    ("post", "/simulator/opcua/stop", None),
    ("post", "/simulator/preset", {"controller_id": 1, "preset": "FLOW"}),
    ("put", "/simulator/parameters",
     {"controller_id": 1, "gain": 1.0, "tau1": 1.0, "tau2": 1.0, "dead_time": 1.0}),
    ("post", "/simulator/disturbance",
     {"controller_id": 1, "type": "step", "amplitude": 1.0}),
    ("delete", "/simulator/disturbance/1", None),
    ("post", "/simulator/1/pid/enable", {"controller_id": 1, "enabled": True}),
    ("post", "/simulator/1/pid/params",
     {"controller_id": 1, "kp": 1.0, "ti": 1.0, "td": 0.0}),
    ("get", "/simulator/1/pid/status", None),
    ("put", "/simulator/1/auto-sp", {"enabled": False}),
    ("put", "/simulator/1/auto-disturbance", {"enabled": False}),
    # audit
    ("get", f"/audit?{_WINDOW}", None),
    # users (new surface, Task 4)
    ("get", "/users", None),
    ("post", "/users", {"username": "rbac-new", "password": "pw", "role": "user"}),
    ("patch", "/users/9999", {"role": "user"}),
    ("delete", "/users/9999", None),
]

USER_ALLOWED_ROUTES: list[tuple[str, str, dict | None]] = [
    ("get", "/auth/me", None),
    ("post", "/auth/refresh", None),
    ("get", "/controllers", None),
    ("get", "/controllers/9999", None),
    ("get", "/controllers/9999/alarm-config", None),
    ("get", "/controllers/stats", None),
    ("get", "/controllers/9999/stats", None),
    ("get", "/controllers/9999/ai/status", None),
    ("get", "/controllers/9999/ai/history", None),
    ("post", "/commands/setpoint", {"controller_id": 9999, "value": 50.0}),
    ("post", "/commands/mode", {"controller_id": 9999, "mode": "AUTO"}),
    ("post", "/commands/output", {"controller_id": 9999, "value": 50.0}),
    ("get", "/commands/tuning-recommendations/9999", None),
    ("get", "/history/9999", None),
    ("get", "/alarms/active", None),
    ("get", f"/alarms/history?{_WINDOW}", None),
    ("get", f"/alarms/ai-history?{_WINDOW}", None),
    ("post", "/alarms/9999/ack", None),
    ("post", "/alarms/ack-all", None),
    ("get", f"/system-events?{_WINDOW}", None),
    ("post", "/export",
     {"controller_id": 1, "start": "2026-01-01T00:00:00",
      "end": "2026-01-02T00:00:00", "format": "csv"}),
    ("get", "/export/nonexistent-id", None),
    ("get", "/export/nonexistent-id/download", None),
    ("get", "/opcua/status", None),
    ("get", "/project/current", None),
    # simulator twin operate routes mirror real-loop operation (spec §9.2)
    ("post", "/simulator/9999/pid/sp", {"controller_id": 9999, "value": 50.0}),
    ("post", "/simulator/9999/co", {"controller_id": 9999, "value": 50.0}),
    ("post", "/simulator/9999/pid/mode", {"controller_id": 9999, "mode": "AUTO"}),
]


def _ids(routes: list[tuple[str, str, dict | None]]) -> list[str]:
    return [f"{method.upper()} {path}" for method, path, _ in routes]


async def _request(client: AsyncClient, method: str, path: str,
                   body: dict | None, headers: dict[str, str] | None):
    kwargs: dict = {"headers": headers} if headers else {}
    if body is not None:
        kwargs["json"] = body
    return await getattr(client, method)(path, **kwargs)


class TestRouteInventory:
    """Keeps the lists in lockstep with Appendix A of the phase-0 plan."""

    def test_admin_only_route_count(self) -> None:
        # 37 pre-existing admin routes + 4 /users routes − 1 multipart import
        assert len(ADMIN_ONLY_ROUTES) == 40

    def test_user_allowed_route_count(self) -> None:
        # 26 pre-existing user routes + /auth/me + /auth/refresh
        assert len(USER_ALLOWED_ROUTES) == 28


class TestAdminOnlyRoutes:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "path", "body"), ADMIN_ONLY_ROUTES, ids=_ids(ADMIN_ONLY_ROUTES)
    )
    async def test_user_role_gets_403(
        self, client: AsyncClient, user_headers: dict[str, str],
        method: str, path: str, body: dict | None,
    ) -> None:
        resp = await _request(client, method, path, body, user_headers)
        assert resp.status_code == 403, (
            f"{method.upper()} {path}: expected 403 for role 'user', "
            f"got {resp.status_code}: {resp.text}"
        )
        assert resp.json() == {"detail": "Admin privileges required"}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "path", "body"), ADMIN_ONLY_ROUTES, ids=_ids(ADMIN_ONLY_ROUTES)
    )
    async def test_admin_role_passes_gate(
        self, client: AsyncClient, admin_headers: dict[str, str],
        method: str, path: str, body: dict | None,
    ) -> None:
        resp = await _request(client, method, path, body, admin_headers)
        assert resp.status_code not in (401, 403), (
            f"{method.upper()} {path}: admin must pass the gate, "
            f"got {resp.status_code}: {resp.text}"
        )


class TestUserAllowedRoutes:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "path", "body"), USER_ALLOWED_ROUTES, ids=_ids(USER_ALLOWED_ROUTES)
    )
    async def test_user_role_passes_gate(
        self, client: AsyncClient, user_headers: dict[str, str],
        method: str, path: str, body: dict | None,
    ) -> None:
        resp = await _request(client, method, path, body, user_headers)
        assert resp.status_code not in (401, 403), (
            f"{method.upper()} {path}: role 'user' must pass this gate, "
            f"got {resp.status_code}: {resp.text}"
        )


class TestUnauthenticated:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("method", "path", "body"),
        ADMIN_ONLY_ROUTES + USER_ALLOWED_ROUTES,
        ids=_ids(ADMIN_ONLY_ROUTES + USER_ALLOWED_ROUTES),
    )
    async def test_no_token_401(
        self, client: AsyncClient, method: str, path: str, body: dict | None
    ) -> None:
        resp = await _request(client, method, path, body, headers=None)
        assert resp.status_code == 401, (
            f"{method.upper()} {path}: expected 401 without a JWT, "
            f"got {resp.status_code}"
        )


class TestProjectImportGate:
    """POST /project/import is multipart — parametrising json bodies does not fit."""

    @pytest.mark.asyncio
    async def test_user_role_gets_403(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/project/import",
            headers=user_headers,
            files={"file": ("x.spid", b"not-a-db", "application/octet-stream")},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_role_passes_gate(
        self, client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        resp = await client.post(
            "/project/import",
            headers=admin_headers,
            files={"file": ("x.spid", b"not-a-db", "application/octet-stream")},
        )
        assert resp.status_code not in (401, 403)  # 400 (bad content) is the gate passing
```

- [ ] **Step 2: Run — verify the RIGHT failures**

Run: `uv run pytest tests/core/integration/test_role_contract.py -q`
Expected: `TestAdminOnlyRoutes::test_user_role_gets_403` FAILS on every route still gated by `require_authenticated_admin` (responses are 2xx/404/409 — the user passes a gate that must 403). `TestUserAllowedRoutes`, `TestUnauthenticated`, `TestRouteInventory`, and the admin-side tests PASS already. If a *user-allowed* row fails here, the route list has a typo — fix the list, not the code.

- [ ] **Step 3: Swap the gates, router by router**

For each file: update the `dependencies` import (replace `require_authenticated_admin` with the gate(s) that file needs) and change each handler's `Depends(require_authenticated_admin)` to the gate below. Parameter names (`user` vs `_user`) stay exactly as they are. Nothing else in the handlers changes.

`routers/ai.py` — import `require_admin, require_user`:
| Handler | New gate |
|---|---|
| `get_ai_status` | `require_user` |
| `get_ai_history` | `require_user` |
| `start_ai` | `require_admin` |
| `stop_ai` | `require_admin` |
| `pause_ai` | `require_admin` |

`routers/alarms.py` — import `require_user` only: `get_active_alarms`, `get_alarm_history`, `get_ai_log_history`, `ack_alarm`, `ack_all_alarms` → all `require_user`.

`routers/audit.py` — import `require_admin` only: `get_audit_history` → `require_admin`.

`routers/commands.py` — import `require_admin, require_user`:
| Handler | New gate |
|---|---|
| `set_setpoint` | `require_user` |
| `set_mode` | `require_user` |
| `set_output` | `require_user` |
| `set_optimization` | `require_admin` |
| `write_tuning` | `require_admin` |
| `get_tuning_recommendation` | `require_user` |
| `apply_tuning` | `require_admin` |

`routers/controllers.py` — import `require_admin, require_user`:
| Handler | New gate |
|---|---|
| `list_controllers` | `require_user` |
| `create_controller` | `require_admin` |
| `get_controller` | `require_user` |
| `update_controller` | `require_admin` |
| `delete_controller` | `require_admin` |
| `get_alarm_config` | `require_user` |
| `update_alarm_config` | `require_admin` |

`routers/export.py` — import `require_user` only: `create_export`, `get_export_status`, `download_export` → all `require_user`.

`routers/history.py` — import `require_user` only: `query_history` → `require_user`.

`routers/opcua.py` — import `require_admin, require_user`:
| Handler | New gate |
|---|---|
| `get_status` | `require_user` |
| `browse_children` | `require_admin` |
| `search_tags` | `require_admin` |
| `save_endpoint` | `require_admin` |
| `force_connect` | `require_admin` |
| `force_disconnect` | `require_admin` |

`routers/project.py` — import `require_admin, require_user`:
| Handler | New gate |
|---|---|
| `get_current` | `require_user` |
| `new_project` | `require_admin` |
| `open_project` | `require_admin` |
| `list_projects` | `require_admin` |
| `import_project` | `require_admin` |
| `download_project` | `require_admin` |
| `delete_project` | `require_admin` |

`routers/simulator.py` — import `require_admin, require_user` (spec §9.2: admin-only except twin SP/mode/CO):
| Handler | New gate |
|---|---|
| `start_simulator` | `require_admin` |
| `stop_simulator` | `require_admin` |
| `get_status` | `require_admin` |
| `get_opcua_status` | `require_admin` |
| `start_opcua_server` | `require_admin` |
| `stop_opcua_server` | `require_admin` |
| `set_preset` | `require_admin` |
| `set_parameters` | `require_admin` |
| `inject_disturbance` | `require_admin` |
| `clear_disturbance` | `require_admin` |
| `enable_pid` | `require_admin` |
| `set_pid_params` | `require_admin` |
| `set_pid_sp` | **`require_user`** |
| `set_co` | **`require_user`** |
| `set_pid_mode` | **`require_user`** |
| `get_pid_status` | `require_admin` |
| `set_auto_sp` | `require_admin` |
| `set_auto_disturbance` | `require_admin` |

`routers/stats.py` — import `require_user` only: `get_all_stats`, `get_stats` → `require_user`.

`routers/system_events.py` — import `require_user` only: `get_system_events` → `require_user`.

- [ ] **Step 4: Delete the old gate**

In `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py`, delete the whole `require_authenticated_admin` function (the block that was at lines 75-84 before Task 1's edits). Verify no references remain:

Run: `grep -rn "require_authenticated_admin" packages/ tests/`
Expected: no output.

- [ ] **Step 5: Run the contract test — verify green**

Run: `uv run pytest tests/core/integration/test_role_contract.py -q`
Expected: PASS (40 + 40 + 28 + 68 + 2 route cases + 2 inventory checks — 180 passed).

- [ ] **Step 6: Adapt the pre-existing single-admin tests**

Run: `uv run pytest tests/core -q`
Expected: FAILURES only in the six files below — each encodes "any authenticated user may do admin things". Fix them exactly as follows.

`tests/core/integration/test_ai_control_endpoints.py` — AI control is admin-only now. In the three tests `test_start_ai_returns_ok`, `test_stop_ai_returns_ok`, `test_pause_ai_returns_ok` (lines 14-55): change the fixture parameter `user_headers: dict[str, str]` to `admin_headers: dict[str, str]` and the `headers=user_headers` argument to `headers=admin_headers`.

`tests/core/integration/test_alarm_config_crud.py`:
- Replace every `supervisor_headers` fixture parameter and `headers=supervisor_headers` argument with `admin_headers` (5 tests; GET requests keeping `user_headers` stay — reads are user-allowed).
- Replace `test_update_alarm_config_any_authenticated_user_allowed` (lines 115-131) with:

```python
    @pytest.mark.asyncio
    async def test_update_alarm_config_user_role_forbidden(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict,
    ) -> None:
        # Two-role model (spec §9): alarm-limit configuration is admin-only.
        cid = await _create_controller(api_deps)
        resp = await client.put(
            f"/controllers/{cid}/alarm-config",
            json={"thresholds": []},
            headers=user_headers,
        )
        assert resp.status_code == 403
```

`tests/core/integration/test_api_commands.py`:
- Replace `test_any_authenticated_user_allowed` (tuning, lines 165-177) with:

```python
    @pytest.mark.asyncio
    async def test_tuning_user_role_forbidden(
        self, client: AsyncClient, user_headers: dict[str, str], api_deps: dict
    ) -> None:
        # Two-role model (spec §9): PID tuning writes are admin-only.
        cid = await _create_and_start_controller(api_deps)
        resp = await client.post(
            "/commands/tuning",
            json={"controller_id": cid, "kp": 5.0},
            headers=user_headers,
        )
        assert resp.status_code == 403
```

- Replace the remaining `supervisor_headers` parameters/arguments (lines 190-217) with `admin_headers`.
- Setpoint/mode/output tests keep `user_headers` (user capability — they must stay green untouched).

`tests/core/integration/test_api_controllers.py` — replace `test_create_any_authenticated_user_allowed` (lines 43-52) with:

```python
    @pytest.mark.asyncio
    async def test_create_user_role_forbidden(
        self, client: AsyncClient, user_headers: dict[str, str]
    ) -> None:
        # Two-role model (spec §9): controller CRUD is admin-only.
        resp = await client.post(
            "/controllers",
            json={"name": "TIC-101"},
            headers=user_headers,
        )
        assert resp.status_code == 403
```

(The GET tests in this file keep `user_headers` — list/read are user-allowed.)

`tests/core/integration/test_api_optimization_toggle.py` — the optimization toggle is admin-only (spec §9 capability table). In `test_disable_optimization_persists_and_reports`, `test_enable_optimization_persists_and_reports`, `test_optimization_unknown_controller`: change `user_headers` to `admin_headers` (parameter and `headers=` argument).

`tests/core/integration/test_api_project.py`:
- Replace every `supervisor_headers` parameter/argument with `admin_headers`.
- Replace the two `test_any_authenticated_user_allowed` methods with:

```python
    @pytest.mark.asyncio
    async def test_new_project_user_role_forbidden(
        self, client: httpx.AsyncClient, user_headers: dict[str, str],
    ) -> None:
        # Two-role model (spec §9): .spid project management is admin-only.
        resp = await client.post(
            "/project/new", json={"name": "x"}, headers=user_headers,
        )
        assert resp.status_code == 403
```

```python
    @pytest.mark.asyncio
    async def test_open_project_user_role_forbidden(
        self, client: httpx.AsyncClient, user_headers: dict[str, str],
    ) -> None:
        # 403 (role gate) wins over 404 (missing project): deps run first.
        resp = await client.post(
            "/project/open", json={"name": "nonexistent"}, headers=user_headers,
        )
        assert resp.status_code == 403
```

- `TestGetCurrentProject::test_returns_200` keeps `user_headers` (GET /project/current is user-allowed).

`tests/core/integration/test_project_auth_required.py` — the 401 matrix is still correct; only the stale prose changes. Replace the module docstring (lines 1-7) and the inline comment (line 29) with:

```python
"""Project routes require authentication.

Without an Authorization header every /project route returns 401. Role-based
403 semantics (two-role model, spec §9) are covered by
test_role_contract.py; this file only pins the unauthenticated case.
"""
```

```python
    # No Authorization header -> 401. Role-based 403s: see test_role_contract.
```

`tests/conftest.py` — delete the `supervisor_headers` fixture entirely (its last consumers were migrated above).

- [ ] **Step 7: Run the full backend suite — verify green**

Run: `uv run pytest tests/core tests/domain -q`
Expected: PASS, 0 failures.

Run: `grep -rn "supervisor_headers" tests/`
Expected: no output.

- [ ] **Step 8: Run the touched HMI file once more (shared-domain sanity)**

Run: `uv run pytest tests/hmi/services/test_api_client_users.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/dependencies.py \
        packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/ \
        tests/conftest.py tests/core/integration/
git commit -m "feat(core): enforce two-role authorization on every API route"
```

---

## Appendix A — Route classification (normative)

Derivation rules, in precedence order:
1. Spec §9 capability table rows map writes directly (tuning/AI-control/CRUD/alarm-config/OPC-UA-config/projects/users/settings → admin; SP/mode/CO/ack/export → user).
2. Simulator: admin-only except twin `pid/sp`, `pid/mode`, `co` (spec §9.2 verbatim; "mirroring real-loop operation").
3. Observation reads named by the §7 resync set (controllers, active alarms, alarm history, AI status, OPC-UA status) are `user` — a user-role session must be able to resync. **Exception:** simulator status stays admin because rule 2 is explicit; the phase-3 resync must skip it on 403 for user sessions (recorded in "Interfaces exported").
4. Remaining reads are `user` when they observe process/operational data (stats, histories, tuning recommendations, alarm-config *view* — the AnalogBar limit markers need it), `admin` when they exist solely to power admin capabilities (OPC-UA browse/search for tag mapping; `/audit` — the user-action trail is a compliance surface tied to user management; project *listing/download* — `.spid` management).

63 pre-existing gated routes + 2 auth routes + 1 public + 4 new = 70 rows.

### auth (`/auth`) — `routers/auth.py`
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 1 | POST | `/auth/login` | `login` | public (credentials are the gate) |
| 2 | POST | `/auth/refresh` | `refresh_token` | `require_user` |
| 3 | GET | `/auth/me` | `me` (Task 2, new) | `require_user` |

### system (`/system`) — `routers/system.py`
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 4 | GET | `/system/status` | `system_status` | public (health check, unchanged) |

### controllers (`/controllers`) — `routers/controllers.py` (7 sites)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 5 | GET | `/controllers` | `list_controllers` | `require_user` |
| 6 | POST | `/controllers` | `create_controller` | `require_admin` |
| 7 | GET | `/controllers/{controller_id}` | `get_controller` | `require_user` |
| 8 | PUT | `/controllers/{controller_id}` | `update_controller` | `require_admin` |
| 9 | DELETE | `/controllers/{controller_id}` | `delete_controller` | `require_admin` |
| 10 | GET | `/controllers/{controller_id}/alarm-config` | `get_alarm_config` | `require_user` |
| 11 | PUT | `/controllers/{controller_id}/alarm-config` | `update_alarm_config` | `require_admin` |

### stats (`/controllers` prefix) — `routers/stats.py` (2 sites)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 12 | GET | `/controllers/stats` | `get_all_stats` | `require_user` |
| 13 | GET | `/controllers/{controller_id}/stats` | `get_stats` | `require_user` |

### ai (`/controllers` prefix) — `routers/ai.py` (5 sites)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 14 | GET | `/controllers/{controller_id}/ai/status` | `get_ai_status` | `require_user` (§7 resync) |
| 15 | GET | `/controllers/{controller_id}/ai/history` | `get_ai_history` | `require_user` (observation) |
| 16 | POST | `/controllers/{controller_id}/ai/start` | `start_ai` | `require_admin` |
| 17 | POST | `/controllers/{controller_id}/ai/stop` | `stop_ai` | `require_admin` |
| 18 | POST | `/controllers/{controller_id}/ai/pause` | `pause_ai` | `require_admin` |

### commands (`/commands`) — `routers/commands.py` (7 sites)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 19 | POST | `/commands/setpoint` | `set_setpoint` | `require_user` |
| 20 | POST | `/commands/mode` | `set_mode` | `require_user` |
| 21 | POST | `/commands/output` | `set_output` | `require_user` |
| 22 | POST | `/commands/optimization` | `set_optimization` | `require_admin` (capability table: optimization toggle) |
| 23 | POST | `/commands/tuning` | `write_tuning` | `require_admin` |
| 24 | GET | `/commands/tuning-recommendations/{controller_id}` | `get_tuning_recommendation` | `require_user` (read-only observation) |
| 25 | POST | `/commands/apply-tuning/{controller_id}` | `apply_tuning` | `require_admin` |

### history (`/history`) — `routers/history.py` (1 site)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 26 | GET | `/history/{controller_id}` | `query_history` | `require_user` |

### alarms (`/alarms`) — `routers/alarms.py` (5 sites)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 27 | GET | `/alarms/active` | `get_active_alarms` | `require_user` |
| 28 | GET | `/alarms/history` | `get_alarm_history` | `require_user` (§7 resync closes fired-and-cleared gap) |
| 29 | GET | `/alarms/ai-history` | `get_ai_log_history` | `require_user` |
| 30 | POST | `/alarms/{alarm_id}/ack` | `ack_alarm` | `require_user` |
| 31 | POST | `/alarms/ack-all` | `ack_all_alarms` | `require_user` |

### audit (`/audit`) — `routers/audit.py` (1 site)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 32 | GET | `/audit` | `get_audit_history` | `require_admin` (compliance surface) |

### system-events (`/system-events`) — `routers/system_events.py` (1 site)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 33 | GET | `/system-events` | `get_system_events` | `require_user` (EVENT.SYSTEM is broadcast to every WS session; the REST history read matches) |

### export (`/export`) — `routers/export.py` (3 sites)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 34 | POST | `/export` | `create_export` | `require_user` |
| 35 | GET | `/export/{export_id}` | `get_export_status` | `require_user` |
| 36 | GET | `/export/{export_id}/download` | `download_export` | `require_user` |

### opcua (`/opcua`) — `routers/opcua.py` (6 sites)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 37 | GET | `/opcua/status` | `get_status` | `require_user` (§7 resync + §11 502 banner) |
| 38 | GET | `/opcua/browse/{node_id:path}` | `browse_children` | `require_admin` (tag mapping) |
| 39 | GET | `/opcua/search` | `search_tags` | `require_admin` (tag mapping) |
| 40 | PUT | `/opcua/endpoint` | `save_endpoint` | `require_admin` |
| 41 | POST | `/opcua/connect` | `force_connect` | `require_admin` |
| 42 | POST | `/opcua/disconnect` | `force_disconnect` | `require_admin` |

### project (`/project`) — `routers/project.py` (7 sites)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 43 | GET | `/project/current` | `get_current` | `require_user` (operational context for the shell; no management capability leaked) |
| 44 | POST | `/project/new` | `new_project` | `require_admin` |
| 45 | POST | `/project/open` | `open_project` | `require_admin` |
| 46 | GET | `/project/list` | `list_projects` | `require_admin` |
| 47 | POST | `/project/import` | `import_project` | `require_admin` |
| 48 | GET | `/project/download` | `download_project` | `require_admin` |
| 49 | DELETE | `/project/{name}` | `delete_project` | `require_admin` |

### simulator (`/simulator`) — `routers/simulator.py` (18 sites — spec §9.2 says "17"; the verified count is 18, rule unchanged)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 50 | POST | `/simulator/start` | `start_simulator` | `require_admin` |
| 51 | POST | `/simulator/stop` | `stop_simulator` | `require_admin` |
| 52 | GET | `/simulator/status` | `get_status` | `require_admin` (§9.2 explicit; user-session resync 403-skips) |
| 53 | GET | `/simulator/opcua/status` | `get_opcua_status` | `require_admin` |
| 54 | POST | `/simulator/opcua/start` | `start_opcua_server` | `require_admin` |
| 55 | POST | `/simulator/opcua/stop` | `stop_opcua_server` | `require_admin` |
| 56 | POST | `/simulator/preset` | `set_preset` | `require_admin` |
| 57 | PUT | `/simulator/parameters` | `set_parameters` | `require_admin` |
| 58 | POST | `/simulator/disturbance` | `inject_disturbance` | `require_admin` |
| 59 | DELETE | `/simulator/disturbance/{controller_id}` | `clear_disturbance` | `require_admin` |
| 60 | POST | `/simulator/{controller_id}/pid/enable` | `enable_pid` | `require_admin` |
| 61 | POST | `/simulator/{controller_id}/pid/params` | `set_pid_params` | `require_admin` |
| 62 | POST | `/simulator/{controller_id}/pid/sp` | `set_pid_sp` | **`require_user`** (twin SP) |
| 63 | POST | `/simulator/{controller_id}/co` | `set_co` | **`require_user`** (twin CO) |
| 64 | POST | `/simulator/{controller_id}/pid/mode` | `set_pid_mode` | **`require_user`** (twin mode) |
| 65 | GET | `/simulator/{controller_id}/pid/status` | `get_pid_status` | `require_admin` |
| 66 | PUT | `/simulator/{controller_id}/auto-sp` | `set_auto_sp` | `require_admin` |
| 67 | PUT | `/simulator/{controller_id}/auto-disturbance` | `set_auto_disturbance` | `require_admin` |

### users (`/users`, new) — `routers/users.py` (Task 4)
| # | Method | Path | Handler | Gate |
|---|---|---|---|---|
| 68 | GET | `/users` | `list_users` | `require_admin` |
| 69 | POST | `/users` | `create_user` | `require_admin` |
| 70 | PATCH | `/users/{user_id}` | `update_user` | `require_admin` |
| 71 | DELETE | `/users/{user_id}` | `deactivate_user` | `require_admin` |

**Totals** (pre-existing 63 gated sites): `require_user` = 26, `require_admin` = 37. With the 4 new `/users` routes: 41 admin-gated. Cross-check: 5+5+1+7+7+3+1+6+7+18+2+1 = 63 ✓.

## Appendix B — Call-site verification (2026-07-26)

`grep -rn "require_authenticated_admin" packages/smart_pid_core` before this plan executes:

| Router file | Depends() call sites | Handlers |
|---|---|---|
| `routers/ai.py` | 5 | `get_ai_status`, `get_ai_history`, `start_ai`, `stop_ai`, `pause_ai` |
| `routers/alarms.py` | 5 | `get_active_alarms`, `get_alarm_history`, `get_ai_log_history`, `ack_alarm`, `ack_all_alarms` |
| `routers/audit.py` | 1 | `get_audit_history` |
| `routers/commands.py` | 7 | `set_setpoint`, `set_mode`, `set_output`, `set_optimization`, `write_tuning`, `get_tuning_recommendation`, `apply_tuning` |
| `routers/controllers.py` | 7 | `list_controllers`, `create_controller`, `get_controller`, `update_controller`, `delete_controller`, `get_alarm_config`, `update_alarm_config` |
| `routers/export.py` | 3 | `create_export`, `get_export_status`, `download_export` |
| `routers/history.py` | 1 | `query_history` |
| `routers/opcua.py` | 6 | `get_status`, `browse_children`, `search_tags`, `save_endpoint`, `force_connect`, `force_disconnect` |
| `routers/project.py` | 7 | `get_current`, `new_project`, `open_project`, `list_projects`, `import_project`, `download_project`, `delete_project` |
| `routers/simulator.py` | 18 | all handlers (Appendix A rows 50-67) |
| `routers/stats.py` | 2 | `get_all_stats`, `get_stats` |
| `routers/system_events.py` | 1 | `get_system_events` |
| **Total** | **63** | across **12** router modules (`auth.py`, `system.py` carry none; the definition itself lives in `dependencies.py:75`) |

Spec deviations found by verification (both recorded, neither changes the rules):
- Spec §1/§9.1 says "63 call sites across 14 routers" — the 63 sites live in 12 of the 14 router modules.
- Spec §9.2 says "Simulator's 17 endpoints" — the simulator router has 18 gated endpoints. The classification rule ("admin-only except twin SP/mode/CO") is applied to all 18.

---

## Interfaces exported (for later phases)

Everything below is what phases 1–11 may rely on from phase 0. Names are frozen.

### Python (backend — phase 1 ORM port re-expresses, must keep names)

```python
# smart_pid_domain.enums
class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"

# smart_pid_domain.dtos.auth
class LoginRequest(BaseModel):    # unchanged
    username: str
    password: str

class TokenResponse(BaseModel):   # unchanged — deliberately NO role field
    access_token: str
    token_type: str = "bearer"

class UserCreate(BaseModel):      # spec §9.3's "RegisterRequest", reworked
    username: str                 # Field(min_length=1, max_length=64)
    password: str                 # Field(min_length=1, max_length=128)
    role: UserRole = UserRole.USER

class UserClaims(BaseModel):
    user_id: int
    username: str
    role: UserRole

# smart_pid_domain.dtos.users (unchanged shapes, now served by /users)
class UserResponse(BaseModel):
    id: int
    username: str
    role: UserRole
    active: bool = True
    created_at: str = ""

class UserUpdate(BaseModel):
    role: UserRole | None = None
    password: str | None = None
    active: bool | None = None

# smart_pid_core.adapters.inbound.api.dependencies
def get_current_user(request: Request) -> UserClaims: ...   # 401 on ANY bad/legacy claim
def require_user(user: Annotated[UserClaims, Depends(get_current_user)]) -> UserClaims: ...
def require_admin(user: Annotated[UserClaims, Depends(get_current_user)]) -> UserClaims: ...
# require_authenticated_admin NO LONGER EXISTS after this phase.

# smart_pid_core.main — phase 1 ports these onto engine C, same names:
_ROLE_VALUE_MAP: tuple[tuple[str, str], ...]                       # (("ADMIN","admin"),("SUPERVISOR","admin"),("OPERATOR","user"))
async def _migrate_user_roles(user_repo: UserRepository) -> None:  # raw UPDATE via user_repo.db.execute, idempotent, every startup
async def _seed_default_admin(user_repo: UserRepository) -> None:  # admin/admin, role UserRole.ADMIN.value, only when empty
```

### HTTP surface (phase 2 codegen regenerates from `app.openapi()` right after this phase)

Auth:
- `POST /auth/login` — body `{username, password}` → 200 `{"access_token": str, "token_type": "bearer"}` | 401. Token claims: `{sub: str(user_id), username, role: "admin"|"user", exp}`.
- `POST /auth/refresh` — gate `require_user` → 200 `TokenResponse`.
- `GET /auth/me` — gate `require_user` → 200 `{"user_id": int, "username": str, "role": "admin"|"user"}`. **AuthContext (phase 3/4) populates from here after login and refetches on every 403 (spec §11); the client never decodes the JWT.**

Users API (all `require_admin`; phase 10 builds the management panel on exactly this):
- `GET /users` → 200 `UserResponse[]`
- `POST /users` — body `{"username": str, "password": str, "role"?: "admin"|"user"}` (default `"user"`) → 201 `UserResponse` | 409 duplicate username | 422 invalid role/empty fields
- `PATCH /users/{user_id}` — body `{"role"?: "admin"|"user", "password"?: str, "active"?: bool}` → 200 `UserResponse` | 404 | 409 last-active-admin demotion/deactivation
- `DELETE /users/{user_id}` — soft-deactivate → 200 `UserResponse` | 404 | 409 last active admin

Error semantics (phase 3 `apiClient` + §11 table):
- 401 body `{"detail": "Invalid or expired token"}` or `{"detail": "Missing or invalid Authorization header"}` → clear session, redirect to login. **Legacy-role JWTs land here — one forced re-login.**
- 403 body `{"detail": "Admin privileges required"}` → toast "sem permissão", refetch `/auth/me`.
- 409 on users API: `{"detail": "Username already exists"}` | `{"detail": "Cannot demote or deactivate the last active admin"}`.

WebSocket:
- `/ws/realtime` closes **4401** for missing/invalid token, bad origin, **and legacy-role claims** — the client treats all 4401 as force-re-login (no new close code).

### Route → role map (phase 4+ `useCan(action)`, phase 5 `user-role` E2E spec)

- Normative table: Appendix A. Machine-readable mirror: `ADMIN_ONLY_ROUTES` / `USER_ALLOWED_ROUTES` in `tests/core/integration/test_role_contract.py` (40 + import / 28 entries).
- Capability → gate summary for `useCan`: `operate` (SP/mode/CO incl. twin), `ack`, `export`, `observe` (all reads except below) → both roles; `tune`, `ai.control`, `controllers.write`, `alarms.configure`, `opcua.configure`, `projects.manage`, `users.manage`, `sim.admin`, `audit.read` → admin only.
- **§7/§9 tension, resolved and frozen:** `GET /simulator/status` is **admin** (spec §9.2 explicit) even though §7's resync set names simulator status. A `user`-session resync runs the full §7 set *except* simulator status, treating its deterministic 403 as "skip" (never an error toast). Phase 3's `RealtimeProvider` must encode this.
- The `user`-role faceplate omits `[Apply tuning]` (spec §6.9) — backend enforcement is `POST /commands/apply-tuning/{id}` → 403.

### Test fixtures later phases inherit

- `tests/conftest.py`: `admin_headers` (user_id 1, `admin`, role `admin`), `user_headers` (user_id 2, `operator`, role `user`); `supervisor_headers` is **gone**; both `api_deps`/`sim_api_deps` seed `admin`/`admin` with role `"admin"`.
- `tests/core/integration/test_role_contract.py` is the phase-0 acceptance gate; phases 1 and 2 must keep it green untouched (phase 1 swaps the data layer under it; phase 2 regenerates the OpenAPI client from the schema it implies).
