# Estado Atual — Fix Alarm System

**Data:** 2026-04-07
**Branch:** `fix/alarm-system-hotreload-persistence`

## O que foi feito

### Bug 1: Alarm configs não recarregados após salvar via HMI (ROOT CAUSE)
- `update_alarm_config` REST endpoint agora chama `alarm_worker.update_config()` após salvar no SQLite
- `alarm_worker` adicionado ao `app.state` via `create_app` e dependency injection
- Helper `_thresholds_to_alarm_config()` converte DTOs para AlarmConfig domain model

### Bug 2: Alarm transitions não persistidas no DB
- `AlarmWorker` recebe `event_loop` e usa `asyncio.run_coroutine_threadsafe` para chamar `_persist_alarm()` do thread síncrono
- Cada transição (TRIGGERED/CLEARED) agora é persistida no `Log_Alarmes`

### Bug 3: delay_on/delay_off não implementados no AlarmEngine
- `_PointState` agora rastreia `pending_trigger_since` e `pending_clear_since`
- `_check_transition()` implementa lógica de temporização: condição deve persistir por `delay_on_s` antes de disparar, e por `delay_off_s` antes de limpar
- Delays resetam se a condição muda antes de expirar

### UI: Remoção do AI Log e integração no painel de Alarmes
- Removido `QPlainTextEdit` do AI Log do dashboard (dashboard_page.py)
- Removido `QPlainTextEdit` do AI Log do alarm panel (era um widget separado no splitter)
- AI actions agora aparecem como linhas na tabela de alarmes/eventos com categoria "AI Log"

### UI: Painel de Alarmes com filtros multi-select e categorias
- Novo widget `CheckableComboBox` (multi-select com checkboxes)
- 3 categorias: "Loop Alarm", "AI Log", "System Event"
- Filtros de Categoria, Priority e Type agora são multi-select
- AI Logs: tipo e prioridade mostrados como "—" (não aplicáveis)
- System Events: tipo mostrado como "—" (não aplicável)
- Filtros de priority/type não bloqueiam eventos de categorias que não usam esses campos

## Arquivos modificados

### Backend (smart_pid_core)
- `adapters/inbound/api/app.py` — aceita `alarm_worker` param
- `adapters/inbound/api/dependencies.py` — `get_alarm_worker()`
- `adapters/inbound/api/routers/controllers.py` — hot-reload + helper
- `application/workers/alarm_worker.py` — event_loop + _schedule_persist
- `domain/services/alarm_engine.py` — delay_on/off + _PointState timing
- `main.py` — passa event_loop ao AlarmWorker

### HMI (smart_pid_hmi)
- `pages/dashboard_page.py` — removido AI log widget
- `pages/alarm_panel.py` — reescrito com categorias e multi-select
- `widgets/checkable_combo.py` — novo widget CheckableComboBox
- `main.py` — AI actions vão para alarm_panel.on_ai_event()

### Testes
- `tests/hmi/pages/test_alarm_panel.py` — reescritos para nova API (26 tests pass)

## Próximos passos
- Aguardando aprovação do usuário para merge
