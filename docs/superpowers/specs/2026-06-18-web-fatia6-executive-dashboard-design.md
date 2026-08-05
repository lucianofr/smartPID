# Design — Fatia 6: Executive Dashboard (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.
**Autoridade de UI/design:** [design-system](2026-06-18-web-frontend-design-system-design.md).

## Escopo
Visão consolidada/executiva: KPIs, saúde dos loops, janelas de período de IA/estatísticas, recomendações de sintonia.

## Backend
Nenhuma mudança — reusa `routers/stats`, `routers/controllers`, `routers/ai`.

## Frontend
- Cards executivos: KPIs por loop e agregados (variabilidade, TV, IAE, estado de IA).
- Saúde de loops (rodando/parado/erro, OPC).
- Janela de período configurável (stats/IA agregados).
- Recomendações de sintonia por loop.

## REST/WS usados
- REST `routers/stats`: `GET /controllers/stats`, `GET /controllers/{controller_id}/stats`.
- REST `routers/controllers`: `GET /controllers` (lista — **NÃO** `/active`).
- REST `routers/alarms`: `GET /alarms/ai-history` (ai-history vive no router de alarms).
- REST `routers/commands`: `GET /commands/tuning-recommendations/{controller_id}`.
- WS: `status` (atualização ao vivo dos cards).

## Aceitação
- Cards refletem dados ao vivo e agregações de período.
- Recomendações de sintonia exibidas por loop.
- KPIs renderizados conferem com os valores da REST (assert numérico, não "paridade visual"); cards seguem tokens/componentes do design-system.

## Páginas PySide6 (paridade)
`executive_dashboard`.

## Testes
- Vitest: cálculo/format de KPIs, seleção de janela de período.
- Playwright: dashboard executivo carrega e atualiza ao vivo.

## Riscos
- Agregações pesadas no cliente → preferir agregação no backend (REST existente).

## Dependências
Fatia 0+1 (WS, shell). Recomendado após 4 (stats) e 2 (IA).
