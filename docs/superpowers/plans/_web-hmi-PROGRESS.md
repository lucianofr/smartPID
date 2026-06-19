# Web HMI — Execution PROGRESS (centralized state)

> Running state for the subagent-driven execution of the 8 fatias. Companion to
> `_web-hmi-INDEX.md` (the checkbox tracker). Update this on every logical boundary.
> User decision (2026-06-18): state lives **centralized here in the docs worktree**.

_Last updated: 2026-06-18 — after preconditions P1+P2._

## Worktrees (durable, outside /tmp)
- **Plans / state (this branch):** `.worktrees/web-hmi-plans` @ `docs/web-hmi-implementation-plans`
- **Main (host for merges + fatia branch forks):** `.worktrees/main-web-hmi` @ `main`
- Main repo dir stays on `feat/windows-installers` (NO-TOUCH, dirty).

## Decisions locked this session
- **Do ALL P1–P4 now** before Fatia 0+1 (P3/P4 implemented as standalone precondition branches, merged to main).
- State **centralized in docs worktree** (this file + INDEX checkboxes).
- Merges to `main` need explicit user approval; P1–P4 pre-approved. **Each fatia merge needs separate approval.**

## Preconditions
- [x] **P1** — `fix/backend-security-hardening` → main. Merge commit `1f90c2b` (parents d2d1565 + 6f72c43). Clean (forked off current main HEAD).
- [x] **P2** — `feat/pid-optimization-enable-toggle` → main. Merge commit `903f7a6` (parents 1f90c2b + ac15e53). Conflict in `smart_pid_domain/dtos/commands.py` resolved by **keeping both** `TuningCommand` (P1) + `OptimizationCommand` (P2); router imports both directly (L156 / L227). `dtos/__init__.py` does NOT re-export these two — fine, direct module import.
- [x] **P3** — TD-007 single-admin. Branch `fix/td-007-single-admin` → merge `cb8316d`. One `require_authenticated_admin` gate across all routers; `routers/users.py` + `POST /register` removed; admin bootstrap (`main.py:335-346`) + `UserRepository` kept; 401-not-403. Reviewed (fastapi-reviewer): SPEC ✅, QUALITY approved, 66 handlers enumerated, **no route left ungated**, no 403-by-role. Tests 70 passed + 3 known opcua env failures.
- [x] **P4** — TD-004. Branch `fix/td-004-cors-headers` → merge `cb7f16c`. CORSMiddleware allow-list (`http://127.0.0.1:5173`,`http://localhost:5173`; allow_credentials, specific methods/headers, NO wildcard), TrustedHostMiddleware (`127.0.0.1`,`localhost`), security-headers middleware (nosniff/X-Frame DENY/Referrer/Permissions/CSP), `api_host` default → `127.0.0.1` (opt-in `0.0.0.0` via `SPID_API_HOST`). Verified directly: no `*`+credentials footgun; `trusted_hosts` clean (tests use 127.0.0.1 base URL). 99 tests pass. **Left for Fatia 0+1 Task 5:** `/ws/realtime` Origin validation + SPA single-origin static mount (do NOT re-do CORS/headers).

## ✅ PRECONDITIONS P1–P4 COMPLETE — main ready for fatias
main HEAD = `cb7f16c`. Merge chain: `1f90c2b`(P1) → `903f7a6`(P2) → `cb8316d`(P3) → `cb7f16c`(P4). Combined smoke (auth+security+commands+rbac) = 26 passed.

## Follow-ups raised by P3 review (not blocking; triage in final whole-branch review)
- Minor: `AuthorizationError` + its 403 handler in `error_handlers.py` are now dead code (orphaned when role gating removed). Safe to delete in a later cleanup.
- Operational: single admin has default password `admin` and NO change path (the only mutation, `PUT /users/{id}`, was removed). Recommend a follow-up `POST /auth/change-password` gated by `require_authenticated_admin`. Candidate for Fatia 7 (settings) or a small standalone fix.

## Verification status
- P1/P2 affected-code tests GREEN: `test_api_commands.py` + `test_api_project.py` + `test_project_service.py` = **97 passed**; `test_api_optimization_toggle.py` = **6 passed**.
- ⚠️ **Full `uv run pytest tests/` SIGABRTs (exit 134) at ~8%** in a fresh worktree venv — Py3.14 + aiosqlite teardown thread races a closed asyncio loop (`RuntimeError: Event loop is closed`). Environmental, broader than the 3 known opcua failures. **Implication for fatias:** do NOT rely on a clean full-suite run in a fresh worktree venv. Mitigations to choose next session: (a) run targeted test paths per task, (b) investigate aiosqlite/anyio teardown fixture, or (c) run suite in the main repo's established venv. Decide before Fatia 0+1 e2e tasks.

## Fatias — not started (0/83 tasks)
Order 0+1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. See INDEX for per-task checkboxes and the
cross-cutting reconciliations (GAP register). Each fatia: new branch from main,
subagent-driven (implementer → task review → fix loop), TDD, opus subagents,
conventional commits no attribution. Frontend: context7 + frontend-design +
karpathy-guidelines per the resume directive.

## NEXT STEP — Fatia 0+1 (the linchpin)
Preconditions done. Start Fatia 0+1 `feat/web-fatia01-foundation-dashboard` from `main`
(`cb7f16c`) — dedicated worktree forked from main. Plan:
`2026-06-18-web-fatia01-foundation-dashboard.md` (12 tasks). Shared anchors first:
`_web-hmi-foundation-contract.md` + `_web-hmi-backend-surface.md`. Subagent-driven, opus,
TDD; frontend uses context7 + frontend-design + karpathy-guidelines.
**Carry forward:** Task 5 must NOT re-do CORS/headers (P4 did them) — only `/ws/realtime`
Origin validation + SPA single-origin static mount remain. Verification: full `uv run pytest`
SIGABRTs on Py3.14 — use targeted paths (decision still open: fix teardown vs main-repo venv).
Recommend `/compact` before starting (fatias are a large body of work).
