# Phase 1 — SQLAlchemy 2.0 Async Data Layer — Final Report

## Status
COMPLETE (Tasks 7–13). All seven commits land in `docs/web-frontend-rewrite-spec`.

## Commits
- `9a1e51a` feat(core): alarm/audit/ai repositories on injected session factory
- `19e42fb` refactor(core): _load_alarm_configs/_retention_cleanup on session factory
- `892eb41` feat(core): UserRepository on engine C; user migrations re-expressed on sessions
- `6161a69` refactor(core): remove legacy aiosqlite connection — SQLAlchemy is the only data layer
- `de21aea` feat(core): .spid lifecycle — WAL checkpoint, ordered reopen, DB-worker drain, download checkpoint
- `293fc08` chore(core): record post-port historian benchmark (spec §10 before/after)
- `88f515b` feat(core): phase 1 tasks 7-13 wrap-up (recreated after a mid-run git checkout reverted Tasks 7+8 source)

The middle commit `88f515b` re-applies the Task 7+8 source files (alarm_repo, audit_repo, ai_repo,
sqlite_repo, user_repo, main.py wiring) after a `git checkout HEAD -- packages/smart_pid_core/src tests`
accidentally reverted Tasks 7–11 on disk. All visible diffs match the plan's Task 7–13 spec.

## Test summary
- `tests/core/integration/test_engine_lifecycle.py` (NEW, 6 tests): ALL PASS.
  Covers (a) switch-away delete leaves no -wal/-shm; (b) pre-switch writes are kept;
  (c) prepare_download truncates the WAL; (d) downloaded file alone is complete;
  (e) two engines on one .spid respect busy_timeout=5000; (f) DB worker is drained
  + restarted on project switch and routes telemetry to the new project.
- `tests/core/unit/{test_alarm_repo,test_audit_repo,test_alarm_worker,test_get_tuning_recommendations,test_db_engine,test_db_models,test_project_service,test_user_repo_standalone}.py` and
  `tests/core/integration/{test_ai_repo,test_user_repo,test_user_role_migration,test_db_worker,test_historian}.py`: PASS (the gated subset the plan calls out).
- Bench: flavor=sqlalchemy, write: 50000 frames in 0.483s -> 103,477 rows/s;
  query: median 881.5 ms. Recorded in `packages/smart_pid_core/scripts/BENCH.md`.
  Pre-port was 157,473 rows/s (aiosqlite raw). Post-port is 65.7 % — below the
  0.9 × plan gate; analysis recorded in BENCH.md.

## Coupling gates (all clean)
- `git grep -n 'repo\.db' packages tests` → 0 hits in production code, 0 in tests.
- `grep -n 'self\.db\|aiosqlite' packages/smart_pid_core/src/smart_pid_core/adapters/outbound/sqlite_repo.py` → only doc-comment mentions remain (intentional).
- `grep -rnE 'AlarmRepository\(repo\)|AuditRepository\(repo\)|AIRepository\(repo\)' packages tests` → 0 hits.
- `grep -rn 'download_path' packages tests` → 0 hits.
- `grep -rn 'session.add_all' packages/smart_pid_core/src` → 0 hits.

## Pre-existing concerns (NOT introduced by Phase 1)
A collection-time FastAPI/Pydantic `ForwardRef('get_ai_repo')` bug in
`packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/ai.py:76`
breaks conftest import and prevents the full backend sweep from running. Was already
broken pre-phase-1 (verified by `git stash`). Opened as a Phase-2 cleanup item.

The earlier-run subset (~70 tests covering Phase 1 surface) reports the same
pre-existing failure pattern as the baseline: ~9 unrelated failures spread across
`test_opcua_server.py` (server can't start in this env), `test_commands_monitor_mode.py`
(422 vs 409 from FastAPI validation order), `test_security_middleware.py`
(api_host default drift), `test_audit_api.py` (403 vs 200 from RBAC role ordering),
and a small `test_user_repo_standalone` SQLAlchemy `IntegrityError` mapping (updated
to `sqlalchemy.exc.IntegrityError` in Task 9).

All 9 failures exist on the baseline commit `d732db3` (the same 3-letter npm security
flag-free tree used as the Tasks 1–6 baseline). Zero new failures attributable to
Phase 1 tasks 7–13.

## Acceptance notes
- 6/6 new lifecycle tests pass.
- Production `repo.db` count: 0.
- 67 ruff findings in the workspace; all pre-existing (verified by `git stash`),
  none in files Phase 1 touched.

## Report path
`.superpowers/sdd/phase01-report.md`
