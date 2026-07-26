# Phase 0 progress

- Replaced all production-router `require_authenticated_admin` references.
- Applied Appendix A `require_admin`/`require_user` classifications.
- Registered missing AI route decorators for status/history/start/stop/pause endpoints.
- Converted invalid project import uploads to HTTP 400 after authorization succeeds.
- Contract test: `uv run pytest tests/core/integration/test_role_contract.py -q` → 180 passed.
- Deprecated gate grep is clean.
