# Estado Atual — ProcessSpeed Stats Window

**Data:** 2026-04-06
**Branch:** main (merged de feat/process-speed-stats-window)
**Commit:** 2b55f55

---

## O que foi feito

### ProcessSpeed como campo obrigatório do Controller

1. **Enum expandido** — 4 membros: ULTRA_FAST (5s/0.02), FAST (60s/0.05), MEDIUM (1200s/0.15), SLOW (7200s/0.30) com properties: stats_window_s, speed_factor, label
2. **Campo movido** — process_speed saiu de AIConfig e foi para Controller (campo raiz, obrigatório, default MEDIUM)
3. **DTOs atualizados** — process_speed no nível raiz de ControllerCreate/Update/Response, removido de AIConfigDTO
4. **API router** — _to_response, _body_to_controller, _NESTED_BUILDERS, _ENUM_FIELDS atualizados
5. **SQLite repo** — save/load mapeiam process_speed de Controller, não mais de AIConfig
6. **AI engines** — SPEED_FACTORS dict removido, fuzzy/RL usam speed.speed_factor diretamente
7. **StatsWorker** — window_size dinâmico: `stats_window_s * 1000 // scan_rate_ms`, publish_interval = max(1, window_size // 5)
8. **ControllerDialog** — combo movido para aba General com labels descritivos ("Ultra Fast — Motors / Converters")

### Conflito resolvido no merge

- `controller_dialog.py`: main tinha scan_rate como combo (findData/currentData), branch tinha spinbox. Mantido combo do main + process_speed da branch.

## Testes

- Domain: 144 passed
- Core unit: 341 passed
- HMI: 347 passed (1 falha pré-existente em test_alarm_bar)
- Total: 832 passed

## Specs e Planos

- Spec: `docs/superpowers/specs/2026-04-06-process-speed-stats-window-design.md`
- Plano: `docs/superpowers/plans/2026-04-06-process-speed-stats-window.md`
