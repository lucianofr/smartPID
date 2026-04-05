# Estado Atual — Monitor + Supervisor Mode

**Data:** 2026-04-05
**Branch:** `feature/monitor-supervisor` (worktree em `.worktrees/monitor-supervisor`)

---

## Concluido — 14 Tasks (todas)

### Domain (Tasks 1-4)
- 3 novos StrEnums: `TuningWriteMode`, `TuningRecStatus`, `SystemExecutionMode`
- 2 novos modelos: `PIDParamsRead`, `TuningRecommendation` (frozen dataclasses)
- 2 novos eventos: `TuningRecommended`, `TuningApplied`
- TagBindings expandido: `node_id_kp/ti/td/mode`
- Controller expandido: `tuning_write_mode`, `max_tuning_change_pct`

### Core (Tasks 5-10)
- `CoreSettings.execution_mode` (default: `"monitor"`)
- `tuning_guardrails.py`: `clamp_tuning_change()` e `clamp_tuning_params()`
- **MonitorWorker** (novo): subscreve TELEMETRY, enriquece, publica STATUS
- **OPCUAAdapter**: `read_pid_params()`, `write_pid_params()`, `read_external_mode()`
- **LoopManager**: branch por execution_mode
- **IOWorker**: skip BKCAL write em monitor mode

### API + Wiring (Tasks 11-13)
- Commands router: 409 em monitor mode para SP/mode/output
- Novo: `POST /commands/apply-tuning/{controller_id}` com guardrails
- `main.py` wired

### Regression (Task 14)
- 642 testes passando, 0 falhas introduzidas
- `test_user_repo.py` trava (pre-existente)

## Proximos Passos
- Code review final + merge para main
- Phase 5: AIWorker monitor-mode, IOWorker PARAMS publishing, GET tuning-recommendations
