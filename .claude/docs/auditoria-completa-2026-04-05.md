# Auditoria Completa: Spec vs Implementacao

**Data:** 2026-04-05
**Branch:** `feat/hmi-add-controller`
**Revisado por:** 6 agentes Opus 4.6 em paralelo

---

## Resumo Executivo

| Area | Gaps | CRITICAL/HIGH | MEDIUM | LOW |
|------|------|---------------|--------|-----|
| Phase 1+2: Domain + PID + API | 20 | 6 | 6 | 8 |
| Phase 3a+7: HMI Desktop | 22 | 8 | 8 | 6 |
| Phase 3b+4: OPC-UA + Simulator | 9 | 1 | 3 | 5 |
| Phase 5: AI (Fuzzy/RL) + Stats | 7 | 4 | 1 | 2 |
| Phase 6: Alarms + RBAC | 10 | 3 | 5 | 2 |
| Monitor+Supervisor Mode | 4 | 2 | 2 | 0 |
| **TOTAL** | **72** | **24** | **25** | **23** |

---

## CRITICAL / HIGH — Itens que impedem uso real

### PID Engine (Phase 1)
1. **PV Filter ausente** — `pv_ftime` existe no modelo mas PID engine usa PV cru sem filtro
2. **SP Filter ausente** — `sp_ftime` existe no modelo mas nao e aplicado
3. **Feedforward ausente** — Spec requer `FF_VAL * FF_GAIN` somado ao output. Nenhuma logica FF existe
4. **Low cutoff ausente** — PV deveria ser forcada a 0 quando abaixo de LOW_CUT
5. **Increase-to-close ausente** — `IOOpts.increase_to_close` existe mas engine nunca inverte output
6. **Over-range 10% ausente** — Output clampado estrito, sem allowance de 10%

### Telemetry Publisher (Phase 2) — CRITICO
7. **TELEMETRY.* NAO e bridgado para ZMQ externo** — `_BRIDGE_TOPICS` nao inclui `b"TELEMETRY."`. HMI NAO recebe telemetria real-time via ZMQ. So recebe STATUS, ACTION.CTRL e EVENT.ALARM
8. **LOG.AI.* e SYS.STATE nao bridgados** — HMI nao recebe log de IA nem estado do sistema
9. **ALARM.RECENT nao implementado** — HMI recem-conectada nao recebe alarmes ativos

### API (Phase 2)
10. **ControllerResponse retorna pv/sp/co = 0 sempre** — `_to_response()` hardcoda zeros em vez de buscar valores live do LoopManager
11. **Project Management totalmente ausente** — Nenhum endpoint `/project/*` (new, open, save, save-as). Nenhum ProjectManager
12. **UserCreate default role = "user"** nao bate com enum (ADMIN/SUPERVISOR/OPERATOR). Usuarios criados com default nao passam em nenhum RBAC

### OPC-UA (Phase 3b)
13. **Bumpless transfer apos reconnect ausente** — Reconexao OPC-UA nao reinicializa estado integral do PID, causa bump no output

### AI Engine (Phase 5) — CRITICO
14. **RL Engine e um stub** — Nenhuma reward function, nenhum Gymnasium env, nenhum training loop. `update()` so incrementa contadores e retorna gamma=0
15. **API de controle AI ausente** — Sem endpoints POST start/stop/pause por loop. Operador nao consegue controlar IA
16. **LOG.AI nao persiste no DB** — DBWorker nao subscreve LOG.AI.*, `Log_Sintonia_IA` sempre vazia
17. **DTO/Repo key mismatch** — AIRepository retorna keys em ingles mas DTO espera keys em portugues. Vai dar ValidationError

### Alarms (Phase 6)
18. **AlarmWorker NAO persiste alarmes no DB** — Publica no ZMQ mas nunca chama `AlarmRepository.insert_alarm()`. Alarmes sao perdidos se HMI desconectada
19. **Sem CRUD de alarm config via API** — Nao existe `PUT /controllers/{id}/alarm-config`. Impossivel mudar limites em runtime
20. **apply-tuning usa require_operator em vez de require_supervisor** — Escrever tuning no DCS deveria requerer Supervisor+

### Monitor+Supervisor Mode
21. **GET /commands/tuning-recommendations/{controller_id} ausente** — Endpoint especificado mas nao implementado
22. **IOWorker nao publica PARAMS.{id}** — Spec requer leitura de Kp/Ti/Td a cada 10s e publicacao no bus. Nao existe

### HMI (Phase 3a+7)
23. **Faceplate stats nunca atualizam** — Placeholder estatico "IAE: --- | 2sigma/Range: ---"
24. **Sem botoes RUN/PAUSE/STOP do otimizador** — Operador nao pode controlar estado da IA

---

## MEDIUM — Funcionalidade incompleta

### Domain
25. User model vive no adapter (user_repo.py), nao no domain — viola hexagonal
26. Modelo Project ausente no domain
27. `use_pv_for_bkcal_out` ausente no ControlOpts
28. `is_scaled` e `ai_thread_status` ausentes no schema SQLite
29. `Configuracao_Alarmes` schema diverge do spec (normalizado vs flat row)

### HMI - Dashboard Operacional
30. Sparklines nos cards ausentes — so tem analog bars
31. AI markers no trend ausentes — sem visual de onde IA atuou
32. Time window selection — so presets fixos, spec pede input numerico + dropdown unidade
33. Auto-scale checkbox ausente no trend
34. Manual scale fields ausentes (PV e CO)
35. CSV export button ausente no trend
36. Multi-Trend sem time-sync — 4 graficos independentes, spec requer zoom/pan sincronizado
37. Multi-Trend nao wired a dados — MainWindow nunca alimenta telemetria

### HMI - Dashboard Executivo
38. Bad Actors ranking ausente
39. AI ROI comparison ausente
40. Backend health (CPU/RAM/Uptime) ausente
41. KPIs e Performance Table nunca chamados (update_kpis/update_performance_table nao wired)

### HMI - Alarm Panel
42. Sem filtros (prioridade, tipo, intervalo)
43. AI Log Box terminal-style ausente
44. ACK individual nao wired (so ACK all funciona)
45. Sem retrieval de alarmes historicos do backend

### HMI - Settings Page
46. OPC-UA server config ausente
47. Project management (New/Open/Save/SaveAs) ausente

### HMI - General
48. apply_theme() ausente na maioria dos widgets — theme switch deixa widgets com estilos antigos
49. Add Controller Dialog incompleto — so ~10 campos de 30+

### RBAC
50. Audit trail nao captura valor antigo — spec requer "Valor Antigo -> Valor Novo"
51. HMI nao desabilita botoes por role — operator ve tudo habilitado
52. HMI API client sem metodos de user management (list/create/update/deactivate)

### Monitor+Supervisor
53. MonitorWorker STATUS message nao inclui campo `mode`
54. TuningRecommendation storage e ad-hoc (dict em app.state) sem lifecycle tracking

---

## LOW — Nice-to-have / Deferridos

55. Tag Binding update endpoint ausente (PUT /controllers/{id}/tag-bindings)
56. OPC-UA credential config via REST ausente (atualmente so env var)
57. Simulator: sem ramp disturbance type
58. Simulator: sem first-principles models (GEKKO/TCLab) — deferrido por design
59. Simulator: sem "Export Dynamics to Loop" — deferrido para Phase 7
60. Simulator: namespace path diverge do spec
61. Simulator: sem start/stop runtime control (so env flag)
62. Domain events AIActionComputed e StatsUpdated definidos mas nunca instanciados
63. ISE ausente do StatsUpdated event
64. AlarmBar sem blink animation (CRITICAL deveria piscar forte)
65. /system/status sem auth
66. PUT /config/pid/{id} dedicado ausente (tuning so via controller update geral)
67. Sem endpoint historico especifico (GET /history retorna dados mas pode ser incompleto)

---

## Acoes Recomendadas (Prioridade)

### Sprint 1 — Viabilidade minima
1. Fix Telemetry Publisher bridge topics (adicionar TELEMETRY.*, LOG.AI.*, SYS.STATE) — **sem isso HMI e cega**
2. Fix ControllerResponse para mostrar valores live (pv/sp/co)
3. Fix UserCreate default role
4. Implementar persistencia de alarmes no DB (AlarmWorker -> AlarmRepository)
5. Fix apply-tuning RBAC (require_supervisor)
6. Implementar GET /commands/tuning-recommendations

### Sprint 2 — PID Engine completo
7. PV filter, SP filter
8. Feedforward
9. Increase-to-close, low cutoff, over-range
10. Bumpless transfer on reconnect

### Sprint 3 — HMI funcional
11. Wire faceplate stats e executive dashboard KPIs
12. Optimizer state buttons (RUN/PAUSE/STOP)
13. Sparklines, AI markers, time window, auto-scale, export
14. Multi-trend time-sync
15. Alarm panel filters + historical retrieval
16. Add Controller Dialog completo
17. Settings page (OPC-UA config, project management)

### Sprint 4 — AI + RBAC completo
18. RL engine reward functions + Gymnasium env
19. AI control endpoints (start/stop/pause)
20. LOG.AI persistence pipeline
21. Alarm config CRUD API
22. Audit trail com old/new values
23. HMI role-based button disabling
24. PARAMS.{id} publishing + MonitorWorker mode field
