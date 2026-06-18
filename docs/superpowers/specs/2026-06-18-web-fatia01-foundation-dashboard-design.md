# Design — Fatia 0+1: Foundation + Live Dashboard (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.
**Autoridade de UI/design:** [design-system](2026-06-18-web-frontend-design-system-design.md).

## Escopo
Fundação ponta-a-ponta do web HMI: prova a ponte WebSocket com feature visível (dashboard ao vivo). É pré-requisito de todas as outras fatias.

## Backend
- `adapters/inbound/api/ws/realtime.py` — endpoint `GET /ws/realtime`, `ConnectionManager`, consumidor do `EventBus` (2º consumidor, análogo ao `TelemetryPublisher`).
- **Consumidor não-bloqueante** (`zmq.asyncio` ou single-flight em `run_in_executor`) — `recv()` é bloqueante; `await sub.recv()` ingênuo congela o daemon. Nunca recv por-cliente.
- Registro do WS e injeção do `event_bus` no `create_app` (bus já é passado hoje).
- Auth no handshake (ws-ticket/primeira-mensagem, não `?token=`); **valida `Origin`**; close `4401` se inválido/ausente/expirado.
- Coalescing de último-valor só para `STATUS`/`STATS`; eventos discretos sem perdas.
- **Servir SPA:** `StaticFiles(html=True)` montado após routers (single-origin, sem CORS); bind `127.0.0.1`.
- **`response_model` audit:** routers usados devem declarar Pydantic `response_model` (OpenAPI tipado).

## Frontend (novo pacote `packages/smart_pid_web/`)
- Scaffold Vite/React/TS; proxy dev `/api` e `/ws` → `:8000`.
- App shell: layout, rotas, tema base, guard de rota por JWT, logout.
- Tela de login (consome `login` REST).
- Dashboard: cards de loop + trend em tempo real (uPlot, janela deslizante); indicador de status OPC.
- Hook `useRealtime` (WS, reconexão com backoff, último estado por `loop_id`/tipo).

## REST/WS usados
- REST: `routers/auth` (`POST /auth/login`); `routers/controllers` (`GET /controllers` list, `GET /controllers/{id}`); `routers/opcua` (`GET /opcua/status` — status OPC é **polled via REST**, não via WS).
- WS: `status` (quadro `STATUS.{id}` **enriquecido** — este É o quadro do dashboard ao vivo).

## Aceitação
- Login → dashboard recebe o quadro ao vivo (`status`) via WS.
- Reconexão WS → **re-sync** (refetch `controllers`, `alarms/active`, `ai/status`).
- Status OPC visível por loop (via **REST poll** de `GET /opcua/status`, não via WS).
- WS rejeita token inválido/ausente (`4401`).

## Páginas PySide6 (paridade)
`dashboard_page`, `connection_page` (status).

## Testes
- pytest: RealtimeWS broadcast multi-cliente, rejeição de token, drop em desconexão, último-valor.
- Vitest: `useRealtime` (conexão/reconexão/parse de envelope), cards/gráfico.
- Playwright: login → dashboard recebe telemetria.

## Riscos
- WS bloquear event loop → consumidor não-bloqueante, broadcast async, último-valor.
- Contrato REST divergir → tipos do frontend gerados do OpenAPI do FastAPI.

## Dependências
Nenhuma (é a base). Branch dedicada nova a partir de `main`.
