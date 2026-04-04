# Estado Atual — Smart PID Edge Platform

**Data:** 2026-04-03
**Branch:** main (HEAD: 55fb0e5 — merge Phase 6)

---

## O que foi concluido

### Phase 1 — Foundation + Domain + PID ✅
Monorepo uv 3 pacotes, 14 StrEnums, PID engine (velocity form, anti-windup, bumpless transfer, 8 modos), ZMQ event bus (XPUB/XSUB inproc://), SQLite WAL (7 tabelas), workers (PID+DB), Loop Manager, backend daemon com signal handlers.

### Phase 2 — REST API + Auth + Telemetry Publisher ✅
FastAPI REST (5 routers), JWT+bcrypt auth, TelemetryPublisher (inproc->tcp://5555), DTOs compartilhados no domain, httpx.AsyncClient testes.

### Phase 3a — PySide6 HMI Desktop ✅
MainWindow com toolbar, ConnectionPage (login), DashboardPage (controller cards com faceplate), BusBridge (telemetria real-time via ZMQ SUB), ISA-101 theme, APIClient sync (httpx), MockService para dev. 73 testes.

### Phase 4 — Simulator (Digital Twin) ✅
**Mergeado em 2026-04-03. 12 commits, 26 arquivos, +1719 linhas.**

**Entregas:**
1. **ProcessPresetName** enum (FLOW, PRESSURE, LEVEL, TEMPERATURE, CUSTOM)
2. **ProcessPreset** frozen dataclass + PRESETS registry (4 presets no domain)
3. **ProcessModel** — FOPTD/SOPTD step simulation via scipy.signal (Pade para dead time, state-space discreto ZOH)
4. **Simulator DTOs** — 5 pydantic models (PresetRequest, ParametersRequest, DisturbanceRequest, ControllerSimStatus, StatusResponse)
5. **SimulatorAdapter** — TelemetrySource + ControlWriter, daemon thread, SimpleQueue, thread-safe com Lock
6. **AdapterFactory** — DI condicional (simulator_enabled=True -> SimulatorAdapter, False -> NotImplementedError OPC-UA)
7. **REST /simulator** — 5 endpoints (GET status, POST preset, PUT parameters, POST disturbance, DELETE disturbance/{id})
8. **main.py wiring** — AdapterFactory lifecycle no daemon (start/stop, register controllers do DB)
9. **APIClient** — 5 novos metodos de simulador
10. **SimulatorPage** — Preset combo, parameter spinboxes (gain, tau1, tau2, dead_time), disturbance injection (step/noise/clear)
11. **MainWindow** — Toolbar navigation (Dashboard/Simulator), signal wiring, _check_simulator_available apos login

**Decisoes Phase 4:**
- scipy.signal.pade removido no scipy 1.17 -> usado scipy.interpolate.pade com serie Taylor de e^(-Ls)
- asyncua.Server deferido para Phase 4b (OPC-UA nao necessario para closed-loop via SimpleQueue)
- ProcessPreset no domain (zero deps) para compartilhar entre core e HMI sem violar hexagonal
- TC001 lint: imports usados pelo pydantic/FastAPI mantidos em runtime com noqa

### Phase 6 — Alarms + RBAC ✅
**Branch: feature/phase6-alarms-rbac. 16 tasks, 15 commits, ~60 novos testes.**

**Entregas:**
1. **Domain Enums**: AlarmState, AuditAction (18 action types) em enums.py
2. **AlarmConfig**: frozen dataclass (19 campos: 6 alarm groups x 3 + deadband_percent)
3. **Domain Events**: AlarmTriggered, AlarmCleared, AlarmAcknowledged frozen dataclasses
4. **AlarmEngine**: pure domain service com evaluate(), hysteresis via deadband, deviation suppression durante SP ramp
5. **AlarmRepository**: insert, mark_cleared, acknowledge, acknowledge_all, get_active, get_history (ISA-18.2 ACK workflow)
6. **AuditRepository**: record(), get_history() com filtros por user_id/action + pagination
7. **RBAC Dependencies**: _ROLE_LEVEL hierarchy (OPERATOR < SUPERVISOR < ADMIN), require_operator, require_supervisor
8. **Alarm REST**: GET /alarms/active, GET /alarms/history, POST /alarms/{id}/ack, POST /alarms/ack-all
9. **User Management**: GET/PUT/DELETE /users (admin-only), active field, deactivate
10. **Audit REST**: GET /audit (supervisor+), time-range + user_id/action filters
11. **RBAC Enforcement**: all existing routers updated (commands->operator, controllers CRUD->supervisor/admin, simulator->supervisor, etc.)
12. **Audit Logging**: login, SP/mode/output changes, controller CRUD, alarm ACK
13. **AlarmWorker**: daemon thread, ZMQ STATUS.* subscriber, evaluates via AlarmEngine, publishes EVENT.ALARM.{cid}
14. **HMI Session**: role extraction from JWT, role property
15. **HMI APIClient**: get_active_alarms, ack_alarm, ack_all_alarms, get_alarm_history
16. **AlarmPanel**: QTableWidget with ISA-101 colors, ACK Selected/ACK All, toolbar button
17. **AlarmBar**: priority counters (CRITICAL/WARNING/ADVISORY)
18. **MainWindow**: Alarms toolbar button, alarm_received -> alarm_panel.on_alarm, _send_ack_all

**Decisoes Phase 6:**
- reconhecido_por mudou de INTEGER FK para TEXT (username direto, evita JOIN)
- Log_Alarmes ganhou cleared_at TEXT e Log_Auditoria ganhou username TEXT
- RBAC hierarquico case-insensitive via _ROLE_LEVEL dict
- conftest.py role="OPERATOR" (antes "user") para compatibilidade RBAC

---

## Proximas fases (paralelizaveis)

| Phase | Escopo | Status |
|-------|--------|--------|
| 3b | OPC-UA I/O Worker (reads/writes reais) | Pendente |
| 4b | asyncua.Server embarcado no SimulatorAdapter | Pendente |
| 5 | AI (Fuzzy + RL) + Statistics | Concluido |
| 6 | Alarms + RBAC fine-grained | ✅ Concluido |
| 7 | Executive Dashboard + Multi-Trend + Export + Themes + SVG overlay | Pendente |

Phase 7 depende de 5+6 (ambos concluidos).

---

## Decisoes acumuladas

| Decisao | Escolha | Motivo |
|---------|---------|--------|
| Framework HMI | PySide6 (LGPL) | Licenciamento permissivo |
| Comunicacao interna | ZMQ inproc:// (XPUB/XSUB) | Baixa latencia entre threads |
| Comunicacao externa | ZMQ tcp://5555 PUB/SUB | Telemetria real-time Backend->HMI |
| Comandos HMI->Backend | FastAPI REST + httpx | API para cliente desktop |
| Organizacao | Monorepo uv, 3 pacotes | Domain compartilhado |
| Auth | PyJWT + bcrypt | python-jose deprecated |
| Serializacao bus | msgpack | Compacto para dados numericos |
| Simulacao | scipy.signal (state-space) | Preciso, sem deps externas pesadas |
| Process presets | Domain package | Compartilhar entre core/HMI |
| SimulatorAdapter threading | threading.Lock + SimpleQueue | Sync thread-safe, daemon thread |
| RBAC hierarchy | _ROLE_LEVEL dict case-insensitive | Flexivel, sem overhead |
| Alarm ACK user field | TEXT (username) ao inves de FK | Evita JOINs, simplifica audit trail |

---

## Documentos de referencia

- Spec V2: `docs/superpowers/specs/2026-04-02-smart-pid-v2-architecture-design.md`
- Spec Phase 2: `docs/superpowers/specs/2026-04-03-phase2-rest-api-auth-telemetry-design.md`
- Spec Phase 6: `docs/spec_ff.md`
- Plano Phase 1: `docs/superpowers/plans/2026-04-02-phase1-foundation-domain-pid-v2.md`
- Plano Phase 2: `docs/superpowers/plans/2026-04-03-phase2-rest-api-auth-telemetry.md`
- Plano Phase 3a: `docs/superpowers/plans/2026-04-03-phase3a-hmi-desktop.md`
- Plano Phase 4: `docs/superpowers/plans/2026-04-03-phase4-simulator.md`
- Plano Phase 6: `docs/superpowers/plans/2026-04-03-phase6-alarms-rbac.md`
- Review Phase 1: `docs/superpowers/reviews/2026-04-03-phase1-code-review.md`
- Requisitos originais: `docs/smartPIDv2.md`
- Referencia PID: `docs/bloco_pid.md`
