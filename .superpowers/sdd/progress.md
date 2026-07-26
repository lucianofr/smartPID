# Phase 1 — SQLAlchemy 2.0 Async Data Layer
- Plan: docs/superpowers/plans/2026-07-26-phase01-sqlalchemy-async.md
- Status: DONE
- BASE f3890fd → HEAD d732db3 + 4 follow-up fixes (1852f11, ca0a6f6, etc.)
- Implementation: T1-T10 + 4 follow-up test/router fixes
- Verified: 180/180 contract test, integration sweep passes (modulo noted pre-existing failures)
- Notes: pre-existing test_domain process_speed speed factor, OPC-UA external-service tests, and test_loop_manager_commands hang are out of scope for this rewrite.
