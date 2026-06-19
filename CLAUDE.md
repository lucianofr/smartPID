# Projeto: Smart PID Edge Platform

## Agentes
- Todos os subagentes (Agent tool) DEVEM usar `model: "opus"` para garantir Claude Opus 4.6
- Nao usar haiku ou sonnet para subagentes neste projeto

## Stack e padroes
- Python 3.13, uv workspace (hatchling), monorepo
- **HMI atual (web):** React + Vite + TypeScript, TanStack Query (REST), uPlot (trends), WebSocket realtime
- **HMI legado (PySide6): CONGELADA** — sem features novas; mantida ate paridade web, depois removida do codigo
- ZeroMQ (msgpack), aiosqlite (WAL mode)
- FastAPI + httpx (REST + WebSocket `/ws/realtime` para Web->Backend)
- pydantic v2 + pydantic-settings (prefixo SPID_)
- PyJWT + bcrypt (auth, Phase 6)
- Ruff (lint, line-length=100), mypy strict, pytest + pytest-asyncio (backend); Vitest + Playwright (web)
- Codigo, commits e nomes de variaveis em ingles; comunicacao com usuario em portugues e aceitavel

## Comandos principais
- sync: `uv sync --all-packages`
- test: `uv run pytest tests/ -v`
- lint: `uv run --with ruff ruff check .`
- lint fix: `uv run --with ruff ruff check --fix .`
- mypy: `uv run mypy packages/`
- run backend: `uv run python -m smart_pid_core`
- web dev: `npm run dev` em `packages/smart_pid_web/` (Vite em `127.0.0.1:5173`, proxy `/api` e `/ws` -> backend `:8000`)
- web build: `npm run build` (build estatico servido pelo backend / aberto no browser em localhost)
- web test: `npm run test` (Vitest); E2E: `npm run e2e` (Playwright)

Nota: em ambientes Flatpak (VS Code) o binario uv pode estar em:
`/home/luciano/.var/app/com.visualstudio.code/bin/uv`

## Arquitetura

Hexagonal + Event-Driven, cliente-servidor distribuido (Backend headless + HMI web React; HMI desktop PySide6 congelada/legada).

### Monorepo (pacotes)
- `packages/smart_pid_domain/` — Modelos, enums, eventos, excecoes (ZERO dependencias de infra)
- `packages/smart_pid_core/` — Backend daemon (PID engine, workers, event bus, SQLite, API, RealtimeWS)
- `packages/smart_pid_web/` — **Cliente HMI atual: React/Vite/TS** (toolchain Node, paralelo ao hmi)
- `packages/smart_pid_hmi/` — **Cliente desktop PySide6: CONGELADO (legado)** — sem features novas, removido apos paridade web

> Refatoracao 2026-06-18: o cliente web React substitui a HMI PySide6. Backend v2 reusado quase
> intacto (unica adicao: ponte RealtimeWS). PySide6 congela ao lado ate a paridade total, depois e
> removida. Ver `docs/superpowers/specs/2026-06-18-web-hmi-react-migration-design.md`.

### Estrutura do Backend (`smart_pid_core`)
- `domain/services/` — PID engine (velocity form), mode manager (8 modos)
- `domain/ports/` — Protocolos inbound/outbound (TelemetrySource, ControlWriter, etc.)
- `application/` — Event bus (ZMQ XPUB/XSUB), loop manager, workers (PID, DB)
- `adapters/outbound/` — SQLite repo (7 tabelas), historian (batch insert)
- `adapters/inbound/api/ws/realtime.py` — **RealtimeWS** (`/ws/realtime`): 2o consumidor do EventBus + ConnectionManager + broadcast JSON ao cliente web (analogo ao TelemetryPublisher)
- `config.py` — CoreSettings via pydantic-settings (SPID_ prefix)
- `main.py` — Daemon entry point com signal handlers

### Estrutura do Domain (`smart_pid_domain`)
- `enums.py` — 14 StrEnums (ControllerMode, ExecutionMode, PIDStructure, etc.)
- `models/` — Controller (30+ campos), PIDParams, TelemetryFrame, ControlAction
- `events.py` — Frozen dataclasses com UUID (TelemetryReceived, ControlActionComputed, etc.)
- `exceptions.py` — Hierarquia: SmartPIDError -> Domain/Infra/Communication/Project/Auth errors

### Comunicacao
- ZeroMQ inproc:// — Bus interno entre threads do Backend (XPUB/XSUB proxy, msgpack)
- **WebSocket `/ws/realtime` — Backend->Web (telemetria em tempo real, cliente atual)**; auth JWT no handshake (ws-ticket ou 1a msg, nunca `?token=`), valida header `Origin`, fecha com `4401` se invalido
- ZeroMQ tcp://5555 — PUB/SUB Backend->PySide6 (**legado**, telemetria em tempo real)
- FastAPI REST — Web/HMI->Backend (comandos, historico, CRUD, project upload/download)
- Project management via REST: list, new, open (by name), import (multipart upload), download (FileResponse), delete
- Welcome Dialog/page mostrado pos-login (precisa de auth para listar projetos do backend)
- Topicos do bus (fonte do web): STATUS.{id} (enriquecido pelo MonitorWorker — pv/sp/co/mode/error/saturated/kp/ti/td), ACTION.CTRL.{id}, ACTION.AI.{id}, EVENT.ALARM.*, EVENT.SYSTEM, STATS.{id}. Tópico interno TELEMETRY.{id} **nao** e bridgeado ao web.
- Envelope WS (JSON): `{ type: status|action|alarm|ai|stats, loop_id, seq, ts, data }`. Coalescing de ultimo-valor so para `status`/`stats`; `alarm`/`ai`/`EVENT.SYSTEM` lossless (overflow fecha socket → re-sync via REST)
- Servir SPA single-origin: `app.mount("/", StaticFiles(dist, html=True))` apos os routers (sem CORS); bind em `127.0.0.1`. Routers devem declarar `response_model` (OpenAPI tipado p/ o frontend)

### PID Engine
- Velocity form: delta_cv = Kp * [(e-e1) + dt/Ti*e - Td*(pv-2pv1+pv2)/dt]
- Anti-windup com ARW limits separados + 16x reset recovery
- Bumpless transfer, SP ramp, derivative filter, integral deadband
- 8 modos: OOS, IMan, LO, Man, Auto, Cas, RCas, ROut

### Fuzzy Engine (Phase 5 — otimizacao de Ki)
- Objetivo: ajuste online de Ki via logica fuzzy, sem intervencao manual
- Entradas: error (E) e delta_error (ΔE), normalizados para -100%..+100% do span
- 7 niveis linguisticos: NB, NM, NS, ZO, PS, PM, PB
- Membership functions: triangulares (centro) + trapezoidais (extremos), 50% overlap
- Defuzzificacao: Centro de Gravidade (CoG), saida gamma ∈ [-1.0, +1.0]
- Atualizacao de Ki: `Ki_new = Ki * (1 + gamma * Sv)`, clamped a ai_limit_min/max
- Speed factor (Sv): SLOW=0.30, MEDIUM=0.15, FAST=0.05
- Cadencia: `T_cycle = dead_time_L * 3`
- 3 matrizes de regras por objetivo de controle:
  - **SP Tracking**: resposta rapida a mudancas de setpoint
  - **Disturbance Rejection**: agressivo proximo a erro zero, minimiza offset
  - **Surge Level**: foco em estabilidade da valvula
- Cada loop PID seleciona independentemente: NONE, FUZZY ou RL

### RL Engine (Phase 5 — otimizacao de Ki via Reinforcement Learning)
- Algoritmos: SAC (Soft Actor-Critic) ou PPO (Proximal Policy Optimization)
- Framework: stable-baselines3 (lazy import — so carrega quando habilitado)
- Observation space: [error, delta_error, CO, integral_val] normalizados
- Action space: gamma ∈ [-1.0, +1.0] (mesma interface do Fuzzy)
- Mesma formula de atualizacao de Ki e guardrails (ai_limit_min/max) do Fuzzy
- Reward functions por objetivo:
  - **SP Tracking / Disturbance Rejection**: minimizar IAE/ITAE, penalizar TV (valve chattering)
  - **Surge Level**: recompensar estabilidade da valvula, penalizar IAE apenas fora do deadband
- Treinamento online continuo durante operacao
- Telemetria de decisoes de tuning logada em `Log_Sintonia_IA`

### Estatisticas de Performance (Phase 5)
- Metricas computadas por loop: IAE, ITAE, ISE, MSE, desvio padrao, Total Variation (TV)
- Variabilidade: `2*sigma/RANGE` (relativa ao span) e `2*sigma/SP` (relativa ao setpoint)

## Variaveis de ambiente
- `SPID_JWT_SECRET` — Obrigatorio (auth)
- `SPID_LOG_LEVEL` — Default: INFO
- `SPID_OPCUA_ENDPOINT` — Default: opc.tcp://localhost:4840
- `SPID_API_PORT` / `SPID_API_HOST` — Default: 8000 / 0.0.0.0
- `SPID_ZMQ_PUBLISH_PORT` — Default: 5555
- `SPID_SIMULATOR_ENABLED` / `SPID_SIMULATOR_PORT` — Default: false / 4849
- `SPID_PROJECTS_DIR` — Default: ~/.smart-pid/projects/ (diretorio de projetos gerenciados pelo backend)

## Documentos de referencia
- **Migracao Web HMI (umbrella):** `docs/superpowers/specs/2026-06-18-web-hmi-react-migration-design.md` — fonte de arquitetura do cliente web
- **Design System Web:** `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md` — tokens, componentes, temas (autoridade de UI das 8 fatias)
- **Specs por fatia (web):** `docs/superpowers/specs/2026-06-18-web-fatia{01,2,3,4,5,6,7,8}-*-design.md`
- Spec V2: `docs/superpowers/specs/2026-04-02-smart-pid-v2-architecture-design.md`
- Plano Phase 1: `docs/superpowers/plans/2026-04-02-phase1-foundation-domain-pid-v2.md`
- Plano Phase 2: `docs/superpowers/plans/2026-04-03-phase2-rest-api-auth-telemetry.md`
- Plano Phase 3a: `docs/superpowers/plans/2026-04-03-phase3a-hmi-desktop.md`
- Review Phase 1: `docs/superpowers/reviews/2026-04-03-phase1-code-review.md`
- Requisitos originais: `docs/smartPIDv2.md`
- Referencia PID: `docs/bloco_pid.md`
- Identidade Visual Dark Room: `docs/identidade_visual_Dark.md`
- Identidade Visual ISA-101: `docs/identidade_visual_ISA101.md`
- Identidade Visual MD3: `docs/identidade_visual_MD3.md`

## Fases de implementacao (seguindo V2 Spec)
1. **Phase 1 — Foundation + Domain + PID** ✅ (merged to main)
2. **Phase 2 — REST API + Auth + Telemetry Publisher** ✅ (merged to main)
3. **Phase 3a — PySide6 HMI Desktop** ✅ (merged to main, 73 tests) — **CONGELADO/legado, sera removido apos paridade web**
4. Phase 3b — OPC-UA I/O Worker (reads/writes reais)
5. Phase 4 — Simulator (digital twin): backend (SimulatorAdapter + asyncua.Server) + UI basica no HMI (preset selector, param sliders, disturbance injection). SVG overlay e "Export Dynamics to Loop" deferidos para Phase 7.
6. Phase 5 — AI (Fuzzy + RL) + Statistics
7. Phase 6 — Alarms + RBAC fine-grained
8. Phase 7 — Executive Dashboard + Multi-Trend + Export + Themes + Simulator SVG overlay

Phases 4/5/6 sao paralelizaveis apos Phase 3a.

## Migracao Web HMI (8 fatias — refatoracao 2026-06-18)

Substituicao do cliente PySide6 por frontend web React/Vite, reusando o backend v2. Paridade
total faseada. Cada fatia = spec + plano proprios + **branch dedicada nova a partir de `main`**.
Ordem: `0+1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8` (Fatia 0+1 e a fundacao ponta-a-ponta).

- **Fatia 0+1** — Foundation + Live Dashboard (RealtimeWS + scaffold `smart_pid_web` + login + dashboard ao vivo)
- **Fatia 2** — Comandos + config por loop (PID/fuzzy/RL params, SP/modo/CO, apply-tuning, AI start/stop)
- **Fatia 3** — Alarmes (painel + barra, ack/ack-all, alarm-config)
- **Fatia 4** — Multi-trend + estatisticas + export
- **Fatia 5** — Simulador (preset, sliders, distURbio, output/modo)
- **Fatia 6** — Executive Dashboard (KPIs, saude de loops)
- **Fatia 7** — Settings + Users (RBAC) + Conexao OPC + Projetos `.spid`
- **Fatia 8** — Temas (Dark Room / ISA-101 / MD3 / Ocean) + Faceplate

> Nao-objetivos: reescrever PID/fuzzy/RL/OPC, trocar EventBus, mudar persistencia, wrapper desktop
> (Tauri/Electron). Empacotamento: so browser (localhost). PySide6 nao muda contrato REST/eventos.

## Convencoes
- **PySide6 congelada:** NAO adicionar features novas em `smart_pid_hmi/`; toda UI nova vai no cliente web `smart_pid_web/`. PySide6 e mantida so ate a paridade web e depois removida.
- **Specs obrigatorias ao alterar UI**: Toda modificacao na interface (widgets, layout, cards, paginas, temas) DEVE ser acompanhada da atualizacao dos documentos de especificacao em `docs/` que descrevem o componente alterado. Para a UI web, a autoridade de tokens/componentes/temas e `docs/superpowers/specs/2026-06-18-web-frontend-design-system-design.md` + a spec da fatia correspondente. Isso inclui ainda: `docs/smartPID.md`, `docs/smartPIDv2.md`, `docs/identidade_visual_*.md`, e as specs em `docs/superpowers/specs/`. Nao commitar codigo de UI sem atualizar as specs correspondentes.
- TDD: write failing test -> implement -> green -> commit
- Commits convencionais: feat(scope), fix(scope), chore(scope)
- Hexagonal: domain NUNCA importa de adapters/application
- Protocol classes para ports (sem ABC)
- Frozen dataclasses para eventos e telemetria
- StrEnum para todos os enumerados
- SQLite WAL mode, .spid files, 7-day retention

## Compact Instructions
Ao compactar, preserve:
- Fase atual e quais fases/fatias ja foram concluidas (inclui fatia web em progresso)
- Decisoes de arquitetura (hexagonal, monorepo, EventBus dual bus ZMQ + RealtimeWS WebSocket, **HMI web React substitui PySide6 congelada/a-remover**, backend v2 reusado intacto)
- Estado das tarefas em progresso (task number, o que falta)
- Variaveis de ambiente obrigatorias (SPID_*)
- Caminho do uv em Flatpak se relevante
- Issues de code review pendentes (se houver)
- Branch atual e se esta em worktree

## OBRIGATÓRIO: Salvar estado entre tarefas

**REGRA INVIOLÁVEL:** Ao concluir QUALQUER tarefa (step de um plano, feature, bugfix, etc.), o Claude DEVE:
1. **Salvar o estado atual** em `.claude/docs/estado-atual.md` com: o que foi concluído, decisões tomadas, próximos passos, arquivos modificados

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
