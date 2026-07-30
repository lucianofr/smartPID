# Projeto: Smart PID Edge Platform

## Agentes
- Todos os subagentes (Agent tool) DEVEM usar `model: "opus"` para garantir Claude Opus 4.6
- Nao usar haiku ou sonnet para subagentes neste projeto

## Stack e padroes
- Python 3.13, uv workspace (hatchling), monorepo
- ZeroMQ (msgpack), aiosqlite (WAL mode)
- FastAPI + httpx (REST para HMI->Backend, NAO e web frontend)
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

Nota: em ambientes Flatpak (VS Code) o binario uv pode estar em:
`/home/luciano/.var/app/com.visualstudio.code/bin/uv`

## Arquitetura

Hexagonal + Event-Driven, cliente-servidor distribuido (Backend headless + HMI desktop).

### Monorepo (3 pacotes)
- `packages/smart_pid_domain/` — Modelos, enums, eventos, excecoes (ZERO dependencias de infra)
- `packages/smart_pid_core/` — Backend daemon (PID engine, workers, event bus, SQLite, API)

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

### Comunicacao
- ZeroMQ inproc:// — Bus interno entre threads do Backend (XPUB/XSUB proxy, msgpack)
- ZeroMQ tcp://5555 — PUB/SUB Backend->HMI (telemetria em tempo real)
- FastAPI REST — HMI->Backend (comandos, historico, CRUD, project upload/download)
- Project management via REST: list, new, open (by name), import (multipart upload), download (FileResponse), delete
- Welcome Dialog mostrado pos-login (precisa de auth para listar projetos do backend)
- Topicos: TELEMETRY.{id}, ACTION.CTRL.{id}, ACTION.AI.{id}, STATUS.{id}

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
- Algoritmo: SAC (Soft Actor-Critic) apenas — suporte a PPO foi removido (caminho de treino invalido, nunca usado em producao)
- Framework: stable-baselines3 (extra opcional `ai`, lazy import — so carrega quando habilitado)
- Observation space (5 dims): [error, delta_error, CO, integral_val, ti_norm] normalizados — `ti_norm` e a posicao log-escala do Ti/Ki atual dentro de [limit_min, limit_max], necessaria para preservar a propriedade de Markov
- Action space: gamma ∈ [-1.0, +1.0] (mesma interface do Fuzzy)
- Mesma formula de atualizacao de Ki e guardrails (ai_limit_min/max) do Fuzzy
- Reward: preferencialmente calculado a partir da janela de KPIs do StatsWorker (IAE, oscilacao, TV) quando disponivel; cai para o reward pontual (instantaneo) por objetivo quando a janela ainda nao tem amostras suficientes:
  - **SP Tracking / Disturbance Rejection**: minimizar IAE/ITAE, penalizar TV (valve chattering)
  - **Surge Level**: recompensar estabilidade da valvula, penalizar IAE apenas fora do deadband
- Portao de politica: a rede neural so assume o controle de Ti/Ki apos 3 rodadas de treino online bem-sucedidas (ou ao carregar um modelo ja treinado de uma sessao anterior); antes disso, e sempre que o modelo falha ao prever, usa a politica de fallback P+D
- Treinamento online continuo durante operacao (SAC off-policy, replay buffer)
- Telemetria de decisoes de tuning logada em `Log_Sintonia_IA`

### Estatisticas de Performance (Phase 5)
- Metricas computadas por loop: IAE, ITAE, ISE, MSE, desvio padrao, Total Variation (TV)
- Variabilidade: `2*sigma/RANGE` (relativa ao span) e `2*sigma/SP` (relativa ao setpoint)

## Variaveis de ambiente
- `SPID_JWT_SECRET` — Obrigatorio (auth)
- `SPID_LOG_LEVEL` — Default: INFO
- `SPID_OPCUA_ENDPOINT` — Default: opc.tcp://localhost:4840
- `SPID_API_PORT` / `SPID_API_HOST` — Default: 8000 / 127.0.0.1 (loopback por padrao, TD-004; exponha com `SPID_API_HOST=0.0.0.0` apenas de forma explicita)
- `SPID_ZMQ_PUBLISH_PORT` — Default: 5555
- `SPID_SIMULATOR_ENABLED` / `SPID_SIMULATOR_PORT` — Default: false / 4849
- `SPID_PROJECTS_DIR` — Default: ~/.smart-pid/projects/ (diretorio de projetos gerenciados pelo backend)

## Documentos de referencia
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
3. **Phase 3a — PySide6 HMI Desktop** ✅ (merged to main, 73 tests)
4. Phase 3b — OPC-UA I/O Worker (reads/writes reais)
5. Phase 4 — Simulator (digital twin): backend (SimulatorAdapter + asyncua.Server) + UI basica no HMI (preset selector, param sliders, disturbance injection). SVG overlay e "Export Dynamics to Loop" deferidos para Phase 7.
6. Phase 5 — AI (Fuzzy + RL) + Statistics
7. Phase 6 — Alarms + RBAC fine-grained
8. Phase 7 — Executive Dashboard + Multi-Trend + Export + Themes + Simulator SVG overlay

Phases 4/5/6 sao paralelizaveis apos Phase 3a.

## Convencoes
- **Branching obrigatorio — REGRA INVIOLAVEL**: Toda e qualquer modificacao de codigo, correcao de bug, melhoria ou introducao de novo recurso DEVE ser feita em uma **nova branch dedicada** criada especificamente para aquela tarefa. **NUNCA utilize branches ja existentes** de outras tarefas. **NUNCA faca modificacoes diretamente na main.** O fluxo obrigatorio e:
  1. Fazer `git checkout main && git pull` para partir da main atualizada
  2. Criar branch nova com nome descritivo (ex: `feat/controller-tooltips`, `fix/pid-gain-validation`)
  3. **ANTES de qualquer modificacao de arquivo**, executar `git branch --show-current` e VERIFICAR que o output e EXATAMENTE o nome da branch que voce acabou de criar. Se o output for `main`, outra branch de outro agente, ou qualquer branch que voce NAO criou nesta sessao, **PARE IMEDIATAMENTE** e corrija antes de prosseguir. Esta verificacao e obrigatoria e deve ser logada no output.
  4. Fazer as modificacoes e commits nessa branch
  5. Aguardar aprovacao explicita do usuario
  6. So entao executar o merge para main
  
  **ATENCAO — MISTURA DE BRANCHES ENTRE AGENTES**: Multiplos agentes/subagentes podem estar trabalhando simultaneamente. Cada agente so pode modificar arquivos na branch que ELE PROPRIO criou. Se ao verificar `git branch --show-current` o agente detectar que esta em uma branch que nao criou, deve fazer `git stash` (se houver mudancas), voltar para main, e criar sua propria branch. **Esta regra se aplica a TODOS os agentes e subagentes sem excecao.**
- **Specs obrigatorias ao alterar UI**: Toda modificacao na interface (widgets, layout, cards, paginas, temas) DEVE ser acompanhada da atualizacao dos documentos de especificacao em `docs/` que descrevem o componente alterado. Isso inclui: `docs/smartPID.md`, `docs/smartPIDv2.md`, `docs/identidade_visual_*.md`, e as specs em `docs/superpowers/specs/`. Nao commitar codigo de UI sem atualizar as specs correspondentes.
- TDD: write failing test -> implement -> green -> commit
- Commits convencionais: feat(scope), fix(scope), chore(scope)
- Hexagonal: domain NUNCA importa de adapters/application
- Protocol classes para ports (sem ABC)
- Frozen dataclasses para eventos e telemetria
- StrEnum para todos os enumerados
- SQLite WAL mode, .spid files, 7-day retention

## Compact Instructions
Ao compactar, preserve:
- Fase atual e quais fases ja foram concluidas
- Decisoes de arquitetura (hexagonal, ZMQ dual bus, monorepo 3 pacotes)
- Estado das tarefas em progresso (task number, o que falta)
- Variaveis de ambiente obrigatorias (SPID_*)
- Caminho do uv em Flatpak se relevante
- Issues de code review pendentes (se houver)
- Branch atual e se esta em worktree

## OBRIGATÓRIO: Salvar estado entre tarefas

**REGRA INVIOLÁVEL:** Ao concluir QUALQUER tarefa (step de um plano, feature, bugfix, etc.), o Claude DEVE:
1. **Salvar o estado atual** em `.claude/docs/estado-atual.md` com: o que foi concluído, decisões tomadas, próximos passos, arquivos modificados
2. **PARAR COMPLETAMENTE** e aguardar o usuário dar o próximo comando

NÃO prossiga para a próxima tarefa automaticamente. NÃO encadeie tarefas. Cada tarefa é uma unidade isolada: terminou → salvou estado → parou.

## Como passar o estado entre sessões (o "onde parou")

Antes de dar `/clear`, peça ao Claude para salvar o contexto importante em um arquivo markdown. Crie um diretório `.claude/docs/` no projeto e peça para ele registrar: decisões de arquitetura, o que foi feito, o que falta fazer, e qualquer detalhe crítico da implementação atual. 

Fluxo prático:
```
1. Antes de limpar:
   "Salve o estado atual em .claude/docs/estado-atual.md:
    - o que foi concluído
    - decisões tomadas
    - próximos passos
    - arquivos modificados"

2. /clear

3. Na nova sessão:
   "Leia .claude/docs/estado-atual.md e continue de onde paramos."
   
4. **PARAR e aguardar o usuário iniciar uma nova janela de contexto.** NÃO prossiga para a próxima tarefa automaticamente.