# Design — Fatia 3: Alarmes (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.
**Autoridade de UI/design:** [design-system](2026-06-18-web-frontend-design-system-design.md).

## Escopo
Visualização e reconhecimento de alarmes em tempo real, e configuração de alarmes por loop.

## Backend
Nenhuma mudança — reusa `routers/alarms` (+ alarm-config no `routers/controllers`). Eventos de alarme já trafegam no `EventBus`; a ponte WS (Fatia 0+1) os encaminha como `EVENT.ALARM.*` (`type: "alarm"`), **sem coalescing** (lossless).

## Frontend
- Painel de alarmes (lista ativa, severidade, estado, timestamp, ordenação/filtro).
- Barra de alarmes (resumo persistente no shell, contagem por severidade, blink/ack).
- Ack individual e ack-all.
- Configuração de alarmes por loop (limites/severidades).

## REST/WS usados
- REST `routers/alarms`: `GET /alarms/active`, `POST /alarms/{alarm_id}/ack`, `POST /alarms/ack-all`.
- REST `routers/controllers` (alarm-config): `GET /controllers/{controller_id}/alarm-config`, `PUT /controllers/{controller_id}/alarm-config`.
- WS: `EVENT.ALARM.*` (`type: "alarm"`) + `EVENT.SYSTEM`.

## Aceitação
- Alarmes aparecem em tempo real via WS.
- **Ack ≠ clear:** máquina de **4 estados** (active / ack / cleared-unack / cleared+acked).
  Ack reconhece, **não** limpa o alarme; clear ocorre quando a condição cessa.
- Ack (individual e all) reflete estado no backend e na UI.
- Config de alarme persiste e altera o disparo.

## Páginas PySide6 (paridade)
`alarm_panel`, `alarm_bar`.

## Testes
- Vitest: render por severidade, ação de ack, estado ack-all.
- Playwright: alarme dispara → aparece → ack muda para estado `ack` (não limpa); clear só após cessar a condição.

## Riscos
- Flood de alarmes na UI → virtualização da lista + dedupe por alarm_id.
- Estado de ack dessincronizado → fonte de verdade no backend, UI revalida via REST após ack.

## Dependências
Fatia 0+1 (shell, WS, auth).
