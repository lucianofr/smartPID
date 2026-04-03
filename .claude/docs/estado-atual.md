# Estado Atual — Smart PID Edge Platform

**Data:** 2026-04-03
**Branch:** main (HEAD: cbe7fa9)

---

## O que foi concluido

### Phase 1 — Foundation + Domain + PID ✅
17 commits merged to main (fast-forward de `feat/phase1-v2-foundation`, branch deletada).
70 testes passando, ruff lint clean. Code review final completo — todos os issues resolvidos.

**Entregas:**
1. **Monorepo uv** com 3 pacotes: `smart_pid_domain`, `smart_pid_core`, `smart_pid_hmi` (stub)
2. **Domain layer** — 14 StrEnums, Controller (30+ campos), PIDParams, TelemetryFrame, ControlAction, eventos frozen com UUID, hierarquia de excecoes
3. **PID engine** — Velocity form com anti-windup (ARW limits separados + 16x reset recovery), bumpless transfer, SP ramp, derivative filter, integral deadband, direct/reverse acting
4. **Mode manager** — 8 modos (OOS/IMan/LO/Man/Auto/Cas/RCas/ROut) com transicoes forcadas (bad PV->MAN, tracking->LO, shed timeout)
5. **ZeroMQ event bus** — XPUB/XSUB proxy (inproc://), msgpack, linger=0 para shutdown limpo
6. **SQLite WAL** — 7 tabelas DDL, CRUD completo de Controller, historian (batch insert/query/cleanup)
7. **Workers** — DB worker (TELEMETRY.*->SQLite via deque), PID worker (scan rate loop via monotonic, publica ACTION.CTRL.{id} e STATUS.{id})
8. **Loop Manager** — Orquestra lifecycle de PID+DB workers por controlador
9. **Backend daemon** — Entry point async com signal handlers (SIGINT/SIGTERM), structlog
10. **CoreSettings** — pydantic-settings com prefixo SPID_, jwt_secret obrigatorio

### Phase 2 — Design Spec ✅
Design spec escrita e aprovada: `docs/superpowers/specs/2026-04-03-phase2-rest-api-auth-telemetry-design.md`

---

## Trabalho em progresso

### Phase 2 — REST API + Auth + Telemetry Publisher
**Status:** Design spec aprovada, aguardando revisao final do usuario antes de criar plano de implementacao.

**Escopo definido (seguindo V2 Spec, sem HMI nesta phase):**
1. **FastAPI REST API** — app factory, layered routers, DI, error handling, uvicorn embarcado
2. **Auth (JWT + bcrypt)** — login, register, middleware, RBAC basico (admin vs user)
3. **Telemetry Publisher** — bridge inproc:// -> tcp://5555 PUB (asyncio task)
4. **REST routes:** `/auth/login`, `/auth/register`, `/config/controllers` (CRUD), `/history/{id}`, `/command/{setpoint,mode,output}`, `/system/status`
5. **Commands com efeito local** — SP/mode/CO changes via LoopManager (sem OPC-UA)
6. **DTOs no `smart_pid_domain`** — schemas compartilhados em `dtos/` subpackage
7. **Testes com httpx.AsyncClient** — consistente com padrao pytest-asyncio da Phase 1

**Decisoes tomadas na Phase 2:**

| Decisao | Escolha | Motivo |
|---------|---------|--------|
| Escopo Phase 2 | V2 Spec (sem HMI) | Backend-first, fundacao solida |
| Auth | Real JWT + bcrypt | Infraestrutura pronta desde o inicio |
| RBAC | admin vs user | Granularidade fina adiada para Phase 6 |
| Commands | Efeito local (sem OPC-UA) | LoopManager + ModeManager ja existem |
| DTOs | `smart_pid_domain/dtos/` | Compartilhado entre core e futuro HMI |
| API structure | Layered routers | FastAPI idiomatico, separacao limpa |
| Uvicorn | Embarcado no main loop | Event loop unico, DI simples, shutdown graceful |
| Testes | httpx.AsyncClient | Consistente com pytest-asyncio existente |

**Proximo passo:** Usuario revisa spec -> invocar writing-plans skill para plano de implementacao

---

## Decisoes tomadas (acumulado)

| Decisao | Escolha | Motivo |
|---------|---------|--------|
| Framework HMI | PySide6 (LGPL) | Licenciamento mais permissivo que PyQt6 |
| Comunicacao interna | ZMQ inproc:// (XPUB/XSUB) | Baixa latencia entre threads do backend |
| Comunicacao externa | ZMQ tcp://5555 PUB/SUB | Telemetria real-time Backend->HMI |
| Comandos HMI->Backend | FastAPI REST + httpx | NAO e web frontend, e API para cliente desktop |
| Organizacao | Monorepo uv, 3 pacotes | Domain compartilhado entre core e hmi |
| Deploy | Linux-first (systemd) | Ambiente industrial |
| Auth lib | PyJWT + bcrypt | python-jose esta deprecated |
| Topico telemetria enriquecida | STATUS.{id} | Evita feedback loop no PID worker |
| Serializacao bus | msgpack | Compacto e rapido para dados numericos |

---

## Fases do projeto (atualizado)

| Phase | Escopo | Status |
|-------|--------|--------|
| 1 | Foundation + Domain + PID | ✅ Merged to main |
| 2 | REST API + Auth + Telemetry Publisher (sem HMI) | Spec aprovada, plano pendente |
| 3 | PySide6 HMI + OPC-UA I/O Worker | Pendente |
| 4 | Simulator (digital twin) | Pendente |
| 5 | AI (Fuzzy + RL) + Statistics | Pendente |
| 6 | Alarms + RBAC fine-grained | Pendente |
| 7 | Executive Dashboard + Multi-Trend + Export + Themes | Pendente |

Nota: Phases 4/5/6 sao paralelizaveis apos Phase 3.

---

## Documentos de referencia

- Spec V2: `docs/superpowers/specs/2026-04-02-smart-pid-v2-architecture-design.md`
- **Spec Phase 2:** `docs/superpowers/specs/2026-04-03-phase2-rest-api-auth-telemetry-design.md`
- Plano Phase 1: `docs/superpowers/plans/2026-04-02-phase1-foundation-domain-pid-v2.md`
- Review Phase 1: `docs/superpowers/reviews/2026-04-03-phase1-code-review.md`
- Requisitos originais: `docs/smartPIDv2.md`
- Referencia PID: `docs/bloco_pid.md`
