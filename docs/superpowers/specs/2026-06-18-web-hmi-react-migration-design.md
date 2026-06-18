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
- Assina no `EventBus` os mesmos tópicos que alimentam a PySide6:
  `TELEMETRY.{id}`, `STATUS.{id}`, `ACTION.CTRL.{id}`, `ACTION.AI.{id}`, `ALARM`, AI/stats.
- Serializa o evento (msgpack interno → **JSON**) e faz broadcast aos WS conectados.
- `ConnectionManager`: set de conexões ativas, lock async, remoção em desconexão, broadcast
  resiliente (falha de um socket não derruba os outros).
- **Política de fila:** mantém só o **último valor por tópico** (coerente com "sem histórico"
  e com a janela deslizante do gráfico). Sem backlog; consumidor lento perde quadros antigos,
  nunca trava o produtor.
- **Auth no handshake:** valida o JWT existente antes de aceitar a conexão (token via
  query param `?token=` ou primeira mensagem). Reusa `auth.py`/`dependencies.py`. Rejeita
  com close code `4401` se ausente/inválido/expirado.

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

---

## 3. Contrato WebSocket

Envelope JSON único, derivado dos eventos frozen do domínio:

```jsonc
{
  "type": "telemetry" | "status" | "action" | "alarm" | "ai",
  "loop_id": 12,        // null para eventos globais (ex.: alarme de sistema)
  "ts": 1718743200.123, // epoch seconds
  "data": { /* payload por tipo */ }
}
```

- `telemetry.data` — campos do `TelemetryFrame` (pv, sp, co, mode, …).
- `status.data` — conexão OPC, estado dos workers do loop (rodando/parado/erro).
- `action.data` — `ControlActionComputed` (cv, delta).
- `alarm.data` — alarm_id, severity, state.
- `ai.data` — gamma, ki, strategy, métricas de sintonia.

O cliente filtra por `loop_id`/`type`. O backend envia apenas o último valor por tópico.

---

## 4. Faseamento (8 fatias)

Paridade total decomposta. Cada fatia = **spec + plano de implementação próprios** e
**branch dedicada nova** (a partir de `main`). A Fatia 0+1 é a fundação ponta-a-ponta.

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
