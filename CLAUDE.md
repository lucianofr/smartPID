# Projeto: Smart PID Edge Platform

## Stack e padroes
- Python 3.13, uv workspace (hatchling), monorepo
- ZeroMQ (msgpack), aiosqlite (WAL mode)
- FastAPI + uvicorn (REST Backend -> Web frontend, OpenAPI-first)
- Web frontend: React 18 + Vite 5 + TypeScript, TanStack Query, Radix UI, Tailwind v4, uPlot (charts); Vitest + Playwright
- pydantic v2 + pydantic-settings (prefixo SPID_)
- PyJWT + bcrypt (auth, Phase 6)
- Ruff (lint, line-length=100), mypy strict, pytest + pytest-asyncio
- Codigo, commits e nomes de variaveis em ingles; comunicacao com usuario em portugues e aceitavel

## Comandos principais
- sync: `uv sync --all-packages`
- test: `uv run pytest tests/ -v`
- lint: `uv run --with ruff ruff check .`
- lint fix: `uv run --with ruff ruff check --fix .`
- mypy: `uv run mypy packages/`
- run backend: `uv run python -m smart_pid_core`

### Web frontend (`packages/smart_pid_web`, rodar de dentro do pacote)
- dev: `npm run dev` (Vite, porta 5173; override via `SPID_WEB_PORT`. Proxy segue a porta do daemon, nao hardcoda 8000)
- build: `npm run build` (tsc -b && vite build)
- test: `npm run test` (Vitest) / e2e: `npm run test:e2e` (Playwright)
- typecheck: `npm run typecheck` | lint: `npm run lint` (eslint)
- gerar tipos da API: `npm run gen:api` (dump OpenAPI do backend -> openapi-typescript)
- checar contrato API: `npm run gen:api:check` (falha se openapi.json/tipos estao dessincronizados)

## Arquitetura

Hexagonal + Event-Driven, cliente-servidor distribuido (Backend headless + Web frontend).

### Monorepo (3 pacotes)
- `packages/smart_pid_domain/` — Modelos, enums, eventos, excecoes (ZERO dependencias de infra)
- `packages/smart_pid_core/` — Backend daemon (PID engine, workers, event bus, SQLite, API)
- `packages/smart_pid_web/` — Frontend web React/Vite (UI atual). GOTCHA: excluido do uv workspace (pyproject.toml `exclude`), gerenciado via npm, NAO entra em `uv sync`.

### Estrutura do Backend (`smart_pid_core`)
- `domain/services/` — PID engine (velocity form), mode manager (8 modos)
- `domain/ports/` — Protocolos inbound/outbound (TelemetrySource, ControlWriter, etc.)
- `application/` — Event bus (ZMQ XPUB/XSUB), loop manager, workers (PID, DB)
- `adapters/outbound/` — SQLite repo (7 tabelas), historian (batch insert)
- `config.py` — CoreSettings via pydantic-settings (SPID_ prefix)
- `main.py` — Daemon entry point com signal handlers

### Estrutura do Domain (`smart_pid_domain`)
- `enums.py` — 14 StrEnums (ControllerMode, ExecutionMode, PIDStructure, etc.)
- `models/` — Controller (30+ campos), PIDParams, TelemetryFrame, ControlAction
- `events.py` — Frozen dataclasses com UUID (TelemetryReceived, ControlActionComputed, etc.)
- `exceptions.py` — Hierarquia: SmartPIDError -> Domain/Infra/Communication/Project/Auth errors

### PID Engine
- Velocity form: delta_cv = Kp * [(e-e1) + dt/Ti*e - Td*(pv-2pv1+pv2)/dt]
- Anti-windup com ARW limits separados + 16x reset recovery
- Bumpless transfer, SP ramp, derivative filter, integral deadband
- 8 modos: OOS, IMan, LO, Man, Auto, Cas, RCas, ROut

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
