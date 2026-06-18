# Design — Web HMI (React/Vite) sobre o backend Smart PID v2

**Documento:** Design / Spec (saída de brainstorming)
**Data:** 2026-06-18
**Autor:** Luciano França Rocha — LFR Automação
**Status:** Proposto (aguardando revisão)

---

## 1. Contexto e decisões travadas

O repositório já é a **Smart PID Edge Platform v2**: monorepo hexagonal com
`smart_pid_domain`, `smart_pid_core` (daemon headless — PID engine velocity-form/8 modos,
fuzzy + RL, EventBus interno, OPC-UA via `asyncua`, historian, auth JWT, FastAPI REST,
projetos `.spid`) e `smart_pid_hmi` (HMI desktop PySide6).

Este design cobre a substituição do cliente **HMI PySide6** por um **frontend web
React/Vite**, reusando o backend v2 praticamente intacto.

> Nota: o PRD original descrevia um app "PyQt6 fino" com apenas `pid_optimizer` +
> `opc_client` a encapsular, e propunha recriar do zero o modelo multi-worker + barramento.
> Isso **já existe** no backend v2 (EventBus + PID/IO/DB workers + OPC-UA adapter). Portanto
> este design **não** reconstrói o backend; só adiciona uma ponte WebSocket e o frontend.

**Decisões do usuário (brainstorming 2026-06-18):**

1. **Escopo base:** web HMI sobre o v2 atual — manter o backend, mudança mínima.
2. **Recorte:** paridade total com a HMI PySide6 (faseada).
3. **Transição:** o web **substitui** a PySide6 — PySide6 congela (sem features novas),
   mantida só até a paridade, depois aposentada.
4. **Empacotamento:** só browser — usuário abre `localhost` manualmente; backend serve a API.
5. **Spec:** este documento cobre **todas as 8 fatias** (cada fatia vira spec/plano de
   implementação próprios depois).

**Não-objetivos:** reescrever PID/fuzzy/RL/OPC; trocar o EventBus por outro barramento;
mudar o modelo de persistência (historian + `.spid` + `users.db` permanecem); acesso remoto/
multiusuário além do RBAC já existente; empacotar wrapper desktop (Tauri/Electron).

---

## 2. Arquitetura

### 2.1 Visão geral

```
                 ┌──────────────────── smart_pid_core (1 processo asyncio) ───────────────────┐
 OPC-UA ─asyncua─┤ IO Worker → EventBus ┬→ PID/AI/Alarm/Stats/DB workers (engine, fuzzy, RL)  │
 (DCS/PLC)       │                       ├→ TelemetryPublisher → ZMQ tcp://5555 → PySide6 (legado)
                 │                       └→ RealtimeWS (NOVO)  → WS /ws/realtime ─┐            │
                 │ FastAPI REST (auth, controllers, commands, ai, alarms, opcua,  │            │
                 │   project, history, stats, export, simulator, users, …)        │            │
                 └────────────────────────────────────────────────────────────────┼───────────┘
                                                              REST /api/* ──────────┤
                                                                                    ▼
                                                       ┌──────────── smart_pid_web (React/Vite) ──────────┐
                                                       │ TanStack Query (REST) · useRealtime (WS) · uPlot │
                                                       │ login/JWT · rotas · temas · páginas de paridade   │
                                                       └───────────────────────────────────────────────────┘
```

A única adição no backend é o **RealtimeWS**: um segundo consumidor do `EventBus`, análogo
direto ao `TelemetryPublisher` já existente. Nenhuma mudança em engine, workers, OPC, fuzzy/RL,
auth ou persistência.

### 2.2 Onde mora o código

- **`packages/smart_pid_web/`** — novo pacote no monorepo, toolchain Node (Vite/React/TS),
  paralelo a `smart_pid_hmi`. PySide6 congela ao lado, sem remoção até a paridade.
- **Backend (adições mínimas):**
  - `adapters/inbound/api/ws/realtime.py` — endpoint WS + `ConnectionManager` + consumidor do bus.
  - registro do endpoint e injeção do `event_bus` no `create_app` (o bus já é passado hoje).
  - sem novos workers, sem mudança de schema.

### 2.3 Ponte WebSocket (RealtimeWS)

- Endpoint `GET /ws/realtime` (FastAPI WebSocket) no mesmo app/processo do daemon.
- Assina no `EventBus` os **tópicos realmente publicados** que alimentam o cliente:
  `STATUS.{id}`, `ACTION.CTRL.{id}`, `ACTION.AI.{id}`, `EVENT.ALARM.*`, `EVENT.SYSTEM`, `STATS.{id}`.
  - O quadro do **dashboard ao vivo** é o `STATUS.{id}` **enriquecido** pelo MonitorWorker
    (pv/sp/co/mode/error/saturated/kp/ti/td), **não** o `TELEMETRY.{id}` (que é interno ao
    backend, não bridgeado). O envelope mapeia `type: "status"` (ex-`telemetry`) → `STATUS.{id}`.
  - **Não** assinar `TELEMETRY.{id}` nem um tópico genérico `ALARM` (não existem como fonte web).
- **Consumidor não-bloqueante (CRÍTICO):** `BusSubscriber.recv()` é uma chamada ZMQ
  **bloqueante** — um `await sub.recv()` ingênuo congela o event loop do daemon. Usar
  `zmq.asyncio` (preferido) **ou** um único consumidor compartilhado em `run_in_executor`
  (single-flight) que faz fan-out para todos os clientes. **Nunca** um loop `recv` por cliente;
  **nunca** `recv` concorrente no mesmo socket.
- Serializa o evento (msgpack interno → **JSON**) e faz broadcast aos WS conectados.
- `ConnectionManager`: set de conexões ativas, lock async, remoção em desconexão, broadcast
  resiliente (falha de um socket não derruba os outros).
- **Política de fila (SEPARADA por classe de tópico):**
  - **Coalescing de último-valor** apenas para `STATUS`/`STATS` (coerente com "sem histórico"
    e com a janela deslizante do gráfico). Consumidor lento perde quadros antigos, nunca trava
    o produtor.
  - **Fila por-cliente limitada e sem perdas (lossless bounded)** para eventos discretos
    `EVENT.ALARM`/`ACTION.AI`/`EVENT.SYSTEM` — coalescê-los perderia transições de alarme
    (regressão de segurança). Em overflow da fila, **fecha o socket** para o cliente reconectar
    e re-sincronizar via REST.
- **Auth no handshake:** valida o JWT existente antes de aceitar a conexão. **Não** usar
  `?token=` em query param (vaza em log/history): preferir **ws-ticket de curta duração** OU
  **auth na primeira mensagem**. Reusa `auth.py`/`dependencies.py`. Rejeita com close code
  `4401` se ausente/inválido/expirado. Validar o header `Origin` em `/ws/realtime`.

### 2.4 Frontend

- **Stack:** React + Vite + TypeScript.
- **Estado servidor:** TanStack Query (cache/revalidação da REST existente).
- **Tempo real:** hook `useRealtime` — abre o WS, reconexão automática com backoff,
  expõe o último estado por `loop_id`/tipo. Sem persistência (recarregar reinicia a janela).
- **Gráficos:** **uPlot** (janela deslizante de N pontos/segundos, configurável; alvo ~60 fps).
- **Auth:** token JWT no header `Authorization` (REST) e no handshake WS; guard de rota; logout.
- **Dev:** Vite em `127.0.0.1:5173`, proxy `/api` e `/ws` → backend `:8000`.
- **Prod:** usuário abre o app no browser em localhost (build estático servido localmente).
  Sem launcher/installer dedicado (decisão "só browser").

### 2.5 Empacotamento e serviço do SPA (precondições de backend)

- O app **hoje não monta `StaticFiles` e não tem CORS**. Para servir o build do SPA,
  montar `app.mount("/", StaticFiles(directory=dist, html=True))` **depois** dos routers
  (fallback SPA single-origin → **sem necessidade de CORS**). Alternativa: CORS com
  allow-list explícita. Recomenda-se **bind em `127.0.0.1`**.
- Validar o header `Origin` no handshake de `/ws/realtime`.
- **Precondição de OpenAPI tipado:** os routers devem declarar `response_model` (Pydantic)
  para o frontend gerar tipos a partir do OpenAPI. Auditar nas Fatias 0+1 (e seguintes).

---

## 3. Contrato WebSocket

Envelope JSON único, derivado dos eventos frozen do domínio:

```jsonc
{
  "type": "status" | "action" | "alarm" | "ai" | "stats",
  "loop_id": 12,        // null para eventos globais (ex.: EVENT.SYSTEM)
  "seq": 42,            // sequência por conexão, para detecção de gap
  "ts": 1718743200.123, // epoch seconds — tempo do servidor
  "data": { /* payload por tipo */ }
}
```

- `status.data` — quadro do dashboard ao vivo: `STATUS.{id}` **enriquecido** pelo MonitorWorker
  (pv, sp, co, mode, error, saturated, kp, ti, td) + conexão OPC / estado de workers.
- `action.data` — `ControlActionComputed` (`ACTION.CTRL.{id}`: cv, delta).
- `alarm.data` — `EVENT.ALARM.*`: alarm_id, severity, state (lossless, sem coalescing).
- `ai.data` — `ACTION.AI.{id}`: gamma, ki, strategy, métricas de sintonia.
- `stats.data` — `STATS.{id}`: IAE/ITAE/ISE/MSE/sigma/TV/variabilidade.

O cliente filtra por `loop_id`/`type` e usa `seq` para detectar gaps. Coalescing de
último-valor só para `status`/`stats`; eventos discretos (`alarm`/`ai`/`EVENT.SYSTEM`) são
entregues sem perdas (em overflow, o socket é fechado para re-sync via REST).

---

## 4. Faseamento (8 fatias)

Paridade total decomposta. Cada fatia = **spec + plano de implementação próprios** e
**branch dedicada nova** (a partir de `main`). A Fatia 0+1 é a fundação ponta-a-ponta.

> **Autoridade de UI/design:** todas as fatias seguem
> [2026-06-18-web-frontend-design-system-design.md](2026-06-18-web-frontend-design-system-design.md)
> como fonte de tokens, componentes e temas.

**Specs dedicados por fatia** (detalhe completo de cada uma):
- Fatia 0+1 — [Foundation + Live Dashboard](2026-06-18-web-fatia01-foundation-dashboard-design.md)
- Fatia 2 — [Comandos + Config por Loop](2026-06-18-web-fatia2-commands-loop-config-design.md)
- Fatia 3 — [Alarmes](2026-06-18-web-fatia3-alarms-design.md)
- Fatia 4 — [Multi-trend + Stats + Export](2026-06-18-web-fatia4-multitrend-stats-export-design.md)
- Fatia 5 — [Simulador](2026-06-18-web-fatia5-simulator-design.md)
- Fatia 6 — [Executive Dashboard](2026-06-18-web-fatia6-executive-dashboard-design.md)
- Fatia 7 — [Settings + Users + Conexão + Projetos](2026-06-18-web-fatia7-settings-users-projects-design.md)
- Fatia 8 — [Temas + Faceplate](2026-06-18-web-fatia8-themes-faceplate-design.md)

As subseções abaixo são o resumo; o detalhe vive nos specs dedicados.

### Fatia 0+1 — Foundation + Live Dashboard
- **Backend:** RealtimeWS (`/ws/realtime`) + auth no handshake + testes.
- **Frontend:** scaffold do pacote `smart_pid_web`; app shell (layout, rotas, tema base);
  tela de login (JWT); dashboard ao vivo — cards de loop + trend em tempo real (uPlot);
  indicador de status OPC.
- **REST usada:** `login`, `controllers` (list/get), `opcua/status`.
- **WS:** telemetry, status.
- **Aceitação:** login → dashboard recebe telemetria ao vivo via WS; reconexão automática;
  status OPC visível; WS rejeita token inválido.
- **Páginas PySide6 cobertas:** `dashboard_page`, `connection_page`.

### Fatia 2 — Comandos + configuração por loop
- Diálogo de configuração do loop (params PID, fuzzy, RL); ações SP/modo/CO; enable PID;
  apply-tuning; AI start/stop/pause.
- **REST:** `commands` (`pid/mode`, `pid/sp`, `pid/params`, `co`, `pid/enable`),
  `apply-tuning`, `ai` (start/stop/pause/status), `controllers` (CRUD).
- **Aceitação:** alterar SP/modo/params reflete no backend e na telemetria; apply-tuning
  escreve no controlador com confirmação explícita.
- **Páginas:** `controller_dialog`, parte de `dashboard_page`.

### Fatia 3 — Alarmes
- Painel de alarmes + barra; ack individual e ack-all; alarm-config por loop.
- **REST:** `alarms` (list/active, `{id}/ack`, `ack-all`, `{id}/alarm-config`).
- **WS:** alarm.
- **Aceitação:** alarmes aparecem em tempo real; ack reflete estado; config persiste.
- **Páginas:** `alarm_panel`, `alarm_bar`.

### Fatia 4 — Multi-trend + estatísticas + export
- Página multi-trend (vários loops/variáveis); estatísticas por loop; consultas de histórico;
  export.
- **REST:** `stats`, `history`, `export` (incl. download).
- **Aceitação:** multi-trend plota múltiplos sinais ao vivo; stats e history exibidos; export baixa arquivo.
- **Páginas:** `multi_trend_page`, parte de `settings_page` (stats).

### Fatia 5 — Simulador
- UI do simulador (digital twin): seletor de preset, sliders de parâmetros, injeção de distúrbio,
  controle de output/modo.
- **REST:** `simulator` (`preset`, `disturbance`, `output`, `mode`, `start/stop`).
- **Aceitação:** preset aplicado; distúrbio injetado reflete na telemetria; output/modo controláveis.
- **Páginas:** `simulator_page`.

### Fatia 6 — Executive Dashboard
- Cards executivos / visão consolidada (KPIs, saúde de loops, janelas de período AI/stats).
- **REST:** `stats`, `controllers/active`, agregações existentes.
- **Aceitação:** cards executivos refletem dados ao vivo, paridade visual com a versão PySide6.
- **Páginas:** `executive_dashboard`.

### Fatia 7 — Settings + Users (RBAC) + Conexão + Projetos `.spid`
- Página de settings; gestão de usuários (RBAC fino existente); página de conexão OPC;
  gestão de projetos `.spid` (list/new/open/import/download/delete) + welcome pós-login.
- **REST:** `users` (CRUD), `auth` (register), `opcua` (connect/disconnect/endpoint/start/stop,
  tag browse), `project` (list/new/open/import/download/delete), `system`.
- **Aceitação:** CRUD de usuários respeitando RBAC; conexão OPC configurável; projetos
  gerenciáveis; welcome lista projetos do backend.
- **Páginas:** `settings_page`, `user_management_page`, `connection_page`, welcome/project.

### Fatia 8 — Temas + Faceplate
- Temas de identidade visual (Dark Room, ISA-101, MD3/Ocean) no web; widget faceplate.
- **Aceitação:** troca de tema; faceplate com paridade funcional/visual.
- **Páginas:** `themes`, `faceplate`.

---

## 5. Testes

- **Backend (pytest + pytest-asyncio):** RealtimeWS — broadcast a múltiplos clientes,
  rejeição de token inválido, drop limpo em desconexão, política de último-valor.
- **Frontend (Vitest):** hook `useRealtime` (conexão, reconexão, parsing de envelope),
  componentes de gráfico/cards.
- **E2E (Playwright):** login → dashboard recebe telemetria; por fatia, o fluxo principal.
- Contrato REST reusado; sem reescrever testes de backend existentes.

---

## 6. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| WS bloqueando o event loop do daemon | RealtimeWS é consumidor não-bloqueante do bus; broadcast async; só último valor. |
| Consumidor (browser) mais lento que a taxa de telemetria | Política de último-valor por tópico; sem backlog. |
| Divergência de contrato entre REST atual e frontend | Frontend tipado a partir do OpenAPI gerado pelo FastAPI. |
| Paridade visual (temas industriais ISA-101) | Fatia 8 dedicada; docs de identidade visual como fonte. |
| Regressão no cliente PySide6 durante a transição | PySide6 congela; REST/eventos não mudam de contrato. |
| Perda de conexão WS | Reconexão automática com backoff no `useRealtime`. |

---

## 7. Convenções do projeto (CLAUDE.md)

- **Branch:** cada fatia em **branch dedicada nova a partir de `main`** (regra inviolável).
  Não usar a branch atual `feat/windows-installers` nem outras de tarefas diferentes.
- **Specs de UI:** ao alterar UI, atualizar `docs/smartPIDv2.md` e os
  `docs/identidade_visual_*.md` correspondentes; este design é a fonte de arquitetura web.
- **TDD:** teste que falha → implementação → verde → commit.
- **Subagentes:** `model: opus`.
- **Estado entre tarefas:** salvar `.claude/docs/estado-atual.md` ao concluir cada fatia e parar.

---

## 8. Próximo passo

Após aprovação deste design, criar o **plano de implementação da Fatia 0+1**
(Foundation + Live Dashboard) via skill `writing-plans`, em branch dedicada nova.
As demais fatias seguem o mesmo ciclo spec/plano/implementação, uma a uma.
