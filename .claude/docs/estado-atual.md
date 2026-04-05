# Estado Atual — Audit Sprint 1+2 (COMPLETO)

**Data:** 2026-04-05
**Branch:** feat/hmi-add-controller
**Suite:** 732 passed, 0 failed

---

## Sprint 1 — Viabilidade Mínima (6 gaps)

### Gap #7/#8: Telemetry bridge topics
- Adicionados `TELEMETRY.`, `LOG.AI.`, `SYS.STATE` ao `_BRIDGE_TOPICS`
- `packages/smart_pid_core/src/smart_pid_core/application/telemetry_publisher.py`
- +6 testes em `tests/core/integration/test_telemetry_publisher.py`

### Gap #10: ControllerResponse live values
- `get_live_values()` no LoopManager, wired nas rotas GET/PUT controllers
- PIDWorker e MonitorWorker expõem `last_pv/last_sp/last_co`
- `packages/smart_pid_core/src/smart_pid_core/application/loop_manager.py`
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/controllers.py`
- +4 testes em `tests/core/integration/test_api_controllers.py`

### Gap #12: UserCreate default role
- Já estava correto (`UserRole.OPERATOR`), +4 testes de cobertura
- `tests/domain/test_dtos.py`

### Gap #18: Alarm persistence
- AlarmWorker agora chama `insert_alarm()` / `mark_cleared()` no DB
- `packages/smart_pid_core/src/smart_pid_core/application/workers/alarm_worker.py`
- `packages/smart_pid_core/src/smart_pid_core/main.py` (wiring)
- +5 testes em `tests/core/unit/test_alarm_worker.py`

### Gap #20: RBAC apply-tuning
- `require_operator` → `require_supervisor` no endpoint apply-tuning
- `packages/smart_pid_core/src/smart_pid_core/adapters/inbound/api/routers/commands.py`
- +3 testes em `tests/core/unit/test_commands_monitor_mode.py`

### Gap #21: Tuning recommendations endpoint
- `GET /commands/tuning-recommendations/{controller_id}` implementado
- `TuningRecommendationResponse` DTO criado
- `packages/smart_pid_domain/src/smart_pid_domain/dtos/ai.py`
- +7 testes em `tests/core/unit/test_get_tuning_recommendations.py`

## Sprint 2 — PID Engine Completo (7 gaps)

### Gaps #1-#6: PID Engine 6 features
- PV filter (first-order, `pv_ftime`)
- SP filter (first-order, `sp_ftime`)
- Feedforward (`ff_enable`, `ff_gain`, `ff_val`)
- Low cutoff (PV → 0 quando < `low_cut`)
- Increase-to-close (output inversion via `io_opts`)
- Over-range 10% (effective limits = ±10% do span)
- `packages/smart_pid_core/src/smart_pid_core/domain/services/pid_engine.py`
- `packages/smart_pid_domain/src/smart_pid_domain/models/controller.py` (+ff_enable, ff_gain)
- +30 testes em `tests/core/unit/test_pid_engine_gaps.py`

### Gap #13: Bumpless transfer on OPC-UA reconnect
- IOWorker detecta reconnect e publica `SYS.RECONNECT.{id}`
- PIDWorker escuta e chama `bumpless_transfer()`
- `packages/smart_pid_core/src/smart_pid_core/application/workers/io_worker.py`
- `packages/smart_pid_core/src/smart_pid_core/application/workers/pid_worker.py`
- +9 testes em `tests/core/integration/test_bumpless_reconnect.py`

## Fixes adicionais
- Config tests isolados de env vars / `.env` (test_config.py)
- Total: +68 novos testes

## Contagem de gaps resolvidos

| Audit | CRITICAL/HIGH | MEDIUM | LOW |
|-------|---------------|--------|-----|
| Total | 24 | 25 | 23 |
| Resolvidos Sprint 1+2 | 12 | 0 | 0 |
| Restantes | 12 | 25 | 23 |

## Próximos Passos
- Sprint 3: HMI funcional (faceplate stats, optimizer buttons, sparklines, multi-trend, alarm panel, settings)
- Sprint 4: AI + RBAC completo (RL engine, AI endpoints, audit trail, role-based buttons)
- Commit das mudanças (aguardando autorização)
