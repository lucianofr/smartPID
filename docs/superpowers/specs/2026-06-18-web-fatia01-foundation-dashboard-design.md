# Design — Fatia 0+1: Foundation + Live Dashboard (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.

## Escopo
Fundação ponta-a-ponta do web HMI: prova a ponte WebSocket com feature visível (dashboard ao vivo). É pré-requisito de todas as outras fatias.

## Backend
- `adapters/inbound/api/ws/realtime.py` — endpoint `GET /ws/realtime`, `ConnectionManager`, consumidor do `EventBus` (2º consumidor, análogo ao `TelemetryPublisher`).
- Registro do WS e injeção do `event_bus` no `create_app` (bus já é passado hoje).
- Auth no handshake: valida JWT existente; close `4401` se inválido/ausente/expirado.
- Política de último-valor por tópico; broadcast async resiliente.

## Frontend (novo pacote `packages/smart_pid_web/`)
- Scaffold Vite/React/TS; proxy dev `/api` e `/ws` → `:8000`.
- App shell: layout, rotas, tema base, guard de rota por JWT, logout.
- Tela de login (consome `login` REST).
- Dashboard: cards de loop + trend em tempo real (uPlot, janela deslizante); indicador de status OPC.
- Hook `useRealtime` (WS, reconexão com backoff, último estado por `loop_id`/tipo).

## REST/WS usados
- REST: `routers/auth` (`POST /login`); `routers/controllers` (list/get); `routers/opcua` (`GET /opcua/status`).
- WS: `telemetry`, `status`.

## Aceitação
- Login → dashboard recebe telemetria ao vivo via WS.
- Reconexão automática após queda do WS.
- Status OPC visível por loop.
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
