# Phase 0 RBAC completion report

Routers touched: alarms, audit, commands, controllers, export, history, opcua, project, simulator, stats, system_events, plus AI route registration. All deprecated `require_authenticated_admin` references were replaced and the obsolete dependency definition removed. Route gates follow Appendix A: admin-only writes/configuration/management; user gates for operational reads, ACK, export, controller reads, simulator SP/CO/mode twins, and OPC-UA status.

Verification: `uv run pytest tests/core/integration/test_role_contract.py -q` — 180 passed. Production-router grep confirms zero `require_authenticated_admin` call-sites.

The project import handler now converts invalid uploaded project data into HTTP 400, allowing the admin authorization contract to complete without leaking a database exception.

No known RBAC gaps remain.
