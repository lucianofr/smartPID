# Phase 0 progress

- Replaced all production-router `require_authenticated_admin` references.
- Applied Appendix A `require_admin`/`require_user` classifications.
- Registered missing AI route decorators for status/history/start/stop/pause endpoints.
- Converted invalid project import uploads to HTTP 400 after authorization succeeds.
- Contract test: `uv run pytest tests/core/integration/test_role_contract.py -q` → 180 passed.
- Deprecated gate grep is clean.

# Phase 1 progress

- All seven repo borrowers (alarm, audit, AI, system_event, user, historian, sqlite CRUD) re-expressed on SQLAlchemy async sessions.
- `_load_alarm_configs` and `_retention_cleanup` take `session_factory`.
- `_migrate_users_if_needed` and `_migrate_user_roles` use engine-C sessions.
- `SQLiteRepository.db` (legacy aiosqlite connection) deleted — `grep -n 'repo.db' packages tests` returns 0.
- `UserRepository` now owns engine C; `_USERS_DDL` unchanged.
- `tests/core/integration/test_engine_lifecycle.py` (6 tests, NEW) passes: switch-away drain, WAL checkpoint on download, busy_timeout absorbs contention, DB-worker restart on project switch.
- Post-port historian benchmark: 103,477 rows/s (pre-port 157,473). Recorded in `packages/smart_pid_core/scripts/BENCH.md`.
- `db_worker=db_worker` thread to `ProjectService`; `ProjectService.prepare_download` (async) replaces sync `download_path`.
- 7 conventional commits on `docs/web-frontend-rewrite-spec`: see `.superpowers/sdd/phase01-report.md`.
