# Web HMI — Execution PROGRESS (centralized state)

> Running state for the subagent-driven execution of the 8 fatias. Companion to
> `_web-hmi-INDEX.md` (the checkbox tracker). Update this on every logical boundary.
> User decision (2026-06-18): state lives **centralized here in the docs worktree**.

_Last updated: 2026-06-19 — Fatia 3 (Alarms) merged to main `4210142`._

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

## Fatia 0+1 — ✅ COMPLETE (12/12), MERGED to main `427b670` (2026-06-19)
Branch `feat/web-fatia01-foundation-dashboard` (tip `7fad4b6`) merged `--no-ff` into main
**`427b670`** (parents `754cc00` + `7fad4b6`). 14 commits. main green post-merge: backend WS
22 passed, web 11 unit + build clean, e2e 1 passed, ruff clean.
Worktree `.worktrees/main-web-hmi`. Orchestrator memory: `_web-hmi-fatia01-digest.md`.
On-disk ledger (12/12 complete): `.git/worktrees/main-web-hmi/sdd/progress.md`.
Accumulated minor/deferred findings: `.worktrees/main-web-hmi/.sdd/minor-findings.md`.

- [x] T1 `51ae813` — response_model audit. self-review.
- [x] T2 `631519c` — ConnectionManager (resilient async broadcast). self-review.
- [x] T3 `3b4bcf7` — RealtimeBridge + map_topic_to_envelope. self-review.
- [x] T4 `d891a87` — `/ws/realtime` first-msg auth + Origin + ConnectionBuffer. fastapi-reviewer (SPEC✅, gate-bypass clean).
- [x] T5 `298c6fb` — wire create_app (bridge lifespan + SPA mount + config); brief stale, applied P4 trim. fastapi-reviewer (SPEC✅).
- [x] T6 `6509bd0` — scaffold Vite/React/TS. self-review.
- [x] T7 `80e6486` — theme tokens + ThemeProvider + format. self-review.
- [x] T8 `bfcae54` — api client + AuthContext + RequireAuth + LoginPage. react-reviewer (SPEC✅).
- [x] T9 `da84a60` +fix `3a894fc` — realtime envelope/provider/hook. react-reviewer: 1 Important (stale-render) FIXED.
- [x] T10 `ce71bb8` +chore `dd9acbd` +fix `df00896` — components+shell+DashboardPage+App wiring. react-reviewer: 2 Important FIXED (eslint config, onResync deps) + opcDown ONLINE bug.
- [x] T11 `8f9a5a4` — Playwright e2e login→status frame. e2e green.
- [x] T12 `c78c69a` +gate-fix `e0b4d8a` — spec upkeep + full verify gate + state save; fixed uv-workspace exclude + vitest src scope.
- [x] Final whole-branch review (code-reviewer opus): 1 blocking Important (StatusData nested wire-shape) FIXED `7fad4b6`; auth/WS security SOUND; 16 minors triaged OK-to-defer.

**Deferred to Fatia 8 / follow-ups:** ConnectionBuffer live-wiring + overflow-close; ControllerCard real unit/range mapping (`pv_scale.unit`/`eu_min`/`eu_max`, no decimals field); minor list in `.sdd/minor-findings.md`.

**Next: Fatia 2** (commands + per-loop config) — new branch from main `427b670`.

## Fatia 2 — ✅ COMPLETE (8/8), MERGED to main `3a77ae5` (2026-06-19)
Branch `feat/web-fatia2-commands-loop-config` (forked main `427b670`) merged `--no-ff` into main
**`3a77ae5`** (parents `427b670` + `e2442f5`). 10 commits. Post-merge green: web vitest 63/63,
e2e fatia2-commands 1/1, build clean, ruff 25 baseline (0 new), mypy 541 baseline.
On-disk ledger: `.git/worktrees/main-web-hmi/sdd/progress.md`. Minors: `.../sdd/fatia2-minor-findings.md`.
Digest: `_web-hmi-fatia2-digest.md`.

- T1 `b3d8836` investigation (GAP-2a/2b confirmed; ai_config-persist discovery → engine selector ENABLED per user). self.
- T2 `2bc72fb` types+validation. self.
- T3 `e76ce8e` command wrappers + mutation hooks (+apiPut/apiDelete). self.
- T4 `48f0aaa` AI hooks (retry:false on 404 queries). self.
- T5 `c9d3dbb` CardControls + ControllerCard extend; backend `a1665c4` optimization_enabled (+5 tests). self.
- T6 `f1977c0` Dialog primitive + LoopConfigDialog (engine ENABLED, full ai_config round-trip clobber-safe). self.
- T7 `286a190` AiPanel + ConfirmApplyTuningDialog; +fix `8ecc104` (1 Important: apply-tuning silent failure → mutation). self+fix.
- T8 `9abd81a` dashboard wiring + e2e + specs. self.
- FINAL REVIEW (code-reviewer opus): READY TO MERGE — 9/9 binding constraints MET, 0 Critical/0 Important, 6 minors deferred.

**Key decisions:** engine selector ENABLED via PUT /controllers ai_config (contract premise was stale);
optimization_enabled added to ControllerResponse; all routes require_authenticated_admin; no toast.
**Next: Fatia 3 (Alarms)** — new branch from main.

## Fatia 3 — Alarms — ✅ COMPLETE (8/8), MERGED to main `4210142` (2026-06-19)
Branch `feat/web-fatia3-alarms` (forked main `3a77ae5`) merged `--no-ff` into main
**`4210142`** (parents `3a77ae5` + `05eb3a1`). 9 commits. Post-merge green: vitest 84/84
(19 files), e2e alarms 1/1, build clean (81.49 kB gzip). **Zero backend change** (verified
`git diff main...HEAD -- '*.py'` empty). On-disk ledger: `.git/worktrees/main-web-hmi/sdd/progress.md`.
Minors: `.../sdd/fatia3-minor-findings.md`. Digest: `_web-hmi-fatia3-digest.md`.

- T0 investigation (read-only, NO commit) — confirmed live alarm contract; `src/api/generated/` gitignored → types hand-typed (Fatia 2 precedent). self.
- T1 `cc4c6c3` types + ISA-101 severity helpers (icon shape+color+text). self.
- T2 `4751ae6` data hooks (active query, ack/ack-all, WS trigger; onSettled revalidate, no optimistic). self.
- T3 `af48e23` +fix `bf5b7d6` virtualized AlarmPanel. react-reviewer: 1 Important FIXED (inline-apiPost orphaned ack hooks → restored hooks + isPending + await waitFor). Installed `@tanstack/react-virtual`; jsdom ResizeObserver/offset shims.
- T4 `fc7c6a1` AlarmBar in canonical AppShell footer. self.
- T5 `113bcb0` AlarmConfigForm (full-array PUT replace-all) + `/alarms` route. self.
- T6 `dccc3ef` e2e alarm lifecycle (ack≠clear; cleared+acked drops out). e2e 1/1.
- T7 `8d9aac6` spec docs (smartPIDv2 §9.3 + identidade_visual_ISA101 §4.5). self.
- FINAL REVIEW (code-reviewer opus): MERGE WITH FOLLOW-UPS — 0 Critical/0 High; all 9 binding constraints verified; 1 Important FIXED `05eb3a1` (advisory CSS token → `--alarm-diag` + added `--alarm-diag-bg`). 5 follow-ups (F1–F5) deferred non-blocking.

**Key facts:** zero backend change (pure consume of routers/alarms + alarm-config + EVENT.ALARM/EVENT.SYSTEM WS). GAP-3a (3-state UNACK/ACK/CLEARED_UNACK; ack≠clear; cleared+acked leaves active list). GAP-3b (WS alarm frame = refetch trigger; backend = source of truth, no optimistic). ISA-101 redundant coding. Single-admin (no role gating; negative=401). NOTE: alarm routes still `require_operator/require_supervisor` on this branch (web unaffected — admin satisfies all guards) — flag vs P3/TD-007 "all-collapsed" claim; revisit at Fatia 7.
**Next: Fatia 4 (Multi-trend + Stats + Export)** — new branch from main `4210142`.

## Fatia 4 — Multi-trend + Stats + Export — ✅ COMPLETE (12/12), MERGED to main `4ea9df6` (2026-06-19)
Branch `feat/web-fatia4-multitrend-stats-export` (forked main `4210142`) merged `--no-ff` into main
**`4ea9df6`** (parents `4210142` + `9b34b24`). 17 commits. **Frontend-only** (verified `git diff main...HEAD -- '*.py'` empty).
Final verify @ `9b34b24`: vitest **123/123** (32 files), tsc 0, vite build OK, e2e multitrend **2/2**, lint 0 err (2 pre-existing warns).
On-disk ledger: `.git/worktrees/main-web-hmi/sdd/progress.md`. Minors: `.../sdd/fatia4-minor-findings.md`. Digest: `_web-hmi-fatia4-digest.md`.

- T1 `a7317e3` types+signal catalog (tonal per-loop colors). self/diff.
- T2 `8bb3375` selectSeries/valueAt. self/diff (+stale-StatusData fix: valueAt→.value, FFSignal).
- T3 `3c52185` min/max decimation + window cap (≤pxWidth*2, peak-preserving). self/diff.
- T4 `7450e12` +fix `ecf118b` live model hook. react-reviewer SPEC✅; 1 Important FIXED (monitor-mode NUMERIC timestamp dropped by Date.parse → tolerant toEpochSeconds; envelope.ts timestamp `string|number`).
- T5 `cb8fdb8` stats hooks. react-reviewer SPEC✅. CRITICAL field-name correction: REST StatsResponse == WS get_current_stats == snake_case `std_dev/total_variation/variability_sp/variability_range` (NO sigma/tv/var_range/var_sp on the wire); envelope.ts StatsData was fiction → fixed.
- T6 `f3f36a8` history hook (controller_id PATH). self/diff. (+build-gate fixes `3ff41fa`/`db94585`: T6 test had tsc/lint slips — vitest/eslint don't typecheck.)
- T7 `94f9d4c` export create→poll→download (GAP-4a, no /export/list). react-reviewer SPEC✅, poll-stop+phase empirically verified.
- T8 `a60fd3b` chart+selector+stats panel. react-reviewer SPEC✅ (chart aligned to canonical RealtimeTrend: theme axes, jsdom try/catch, --trend-bg).
- T9 `182d16a` +fix `b6701d8` history+export UI. react-reviewer; MANDATORY auth correction (brief plain `<a href>` would 401 → `apiDownload` Bearer-blob in client.ts) + 1 Important FIXED (silent download error → try/catch/finally + retry affordance + revoke-on-throw).
- T10 `2f59e26` MultiTrendPage (self-shell+real opcDown) + `/multitrend` route + functional NavRail (folds Fatia3 F3); MemoryRouter wrap on DashboardPage.test+AppShell.test (router ripple). react-reviewer SPEC✅.
- T11 `7fcf934` Playwright e2e (StubWS loops 1&2 ISO-ts; auth seed; export=button). 2/2 pass.
- T12 `a7ff3ce` response_model audit (all consumed typed; download legit FileResponse) + spec docs (smartPIDv2 + identidade_visual_ISA101) + full verify.
- FINAL whole-branch review (code-reviewer opus): MERGE-WITH-FOLLOW-UP — 1 HIGH FIXED `9b34b24` (selectSeries cross-loop series/time MISALIGNMENT on staggered selection — silent chart corruption; per-task reviews missed it (equal-length tests) → common newest-aligned window, no nulls, decimate-safe; differing-length test RED→GREEN). 6 findings total; #2–#6 LOW all OK-to-defer.

**Key facts:** frontend-only (backend untouched). STATS IS bridged to web (RealtimeWS subscribes the bus directly → `lastStats` live). Stats wire = snake_case (REST==WS); `StatsRow` is the camelCase UI alias. StatusData.timestamp is ISO (execute/pid_worker) OR numeric epoch (monitor_worker, primary path) → `string|number` + toEpochSeconds. Auth = Bearer header only (no cookie) → authenticated blob download via `apiDownload`. GAP-4a: no `/export/list`. NavRail now functional (Dashboard//Multi-trend//Alarms). Deferred LOW minors in `fatia4-minor-findings.md` (none merge-blocking).
**Next: Fatia 5 (Simulator)** — new branch from main `4ea9df6`.
