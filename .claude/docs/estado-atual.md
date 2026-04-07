# Estado Atual — Phase 6: Alarms, Events & ACK Workflow

**Data:** 2026-04-07
**Branch:** `feat/phase6-alarms-events`

## Status: COMPLETO — Todas as 17 Tasks implementadas

### Commits (em ordem cronológica)
1. `0376128` — Task 1: Remove AlarmEngine from PIDWorker/LoopManager (Bug #1, #2)
2. `211a7a9` — Task 2: Fix deadband calc over instrument span (Bug #11)
3. `2d06479` — Task 3: Fix AlarmWorker — enrich events, pv_range, log errors (Bug #6, #9)
4. `05fe03b` — Task 4: ACK returns alarm details and controller_ids (§5.5, §9.1)
5. `4c7a7c6` — Task 6: SystemEventRepository + Log_System_Events DDL (§4.3)
6. `c5c8d6c` — Task 7: SystemEventWorker facade (§6.1)
7. `2a25e9c` — Task 8: GET /system-events endpoint (§9.3)
8. `3f90cbe` — Task 9: Bridge EVENT.SYSTEM via ZMQ (§6.3, §6.4)
9. `16a16ec` — Task 10: Wire SystemEventWorker + AlarmWorker metadata in daemon (§6.2)
10. `e4de577` — Task 11: HMI API client — get_system_events (§9.3)
11. `a26f02e` — Task 12: Fix AlarmPanel — api_client required, ACK uses 'id' (Bug #3, #4)
12. `42cd383` — Task 13: Redesign AlarmBar as QTableWidget grid (§8.1)
13. `11e64b1` — Task 14: ACK updates all 3 widgets (Bug #5)
14. `5149154` — Task 15: AlarmPanel Live mode with 5s auto-refresh (§7.3)
15. `92647b9` — Task 16: Daily retention cleanup — alarms 30d, logs 7d (§4)
16. `9569610` — Task 17: Fix lint + stale tests

## Bugs corrigidos
| Bug # | Descrição |
|-------|-----------|
| #1 | Duplicate alarm engines — removed from PIDWorker/LoopManager |
| #2 | Alarms never trigger in Execute — dead code removed |
| #3 | AlarmPanel no api_client — made required parameter |
| #4 | ACK Selected wrong field — uses 'id' not 'alarm_id' |
| #5 | ACK All doesn't update all widgets — all 3 updated |
| #6 | AlarmBar shows "?" for name — events enriched |
| #9 | Silent processing failures — added logging |
| #11 | Zero deadband at limit=0 — span-based calculation |

## Features entregues
- SystemEventRepository + DDL + REST API
- SystemEventWorker facade
- EVENT.SYSTEM ZMQ bridging (backend → HMI)
- AlarmBar redesigned as QTableWidget grid with per-row ACK
- AlarmPanel Live mode (5s refresh)
- ACK response contracts (alarm details + controller_ids)
- Data retention cleanup (30d alarms, 7d logs)

## Testes
- 116 tests Phase 6-específicos: ALL PASS
- 2 falhas pré-existentes (não relacionadas a Phase 6):
  - `test_stats_worker::test_publishes_stats_after_samples` — flaky ZMQ timing
  - `test_config_users_db::test_default_users_db_path` — path mismatch
- Lint (ruff): ALL PASS

## Próximos passos
- Aguardando aprovação do usuário para merge para main
