# Design — Fatia 6: Executive Dashboard (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.

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
- REST: `routers/stats` (`GET /stats`, `GET /{controller_id}/stats`); `routers/controllers` (`GET /active`); `routers/ai` (`GET /ai-history`, `GET /tuning-recommendations/{controller_id}`).
- WS: `telemetry` (atualização ao vivo dos cards).

## Aceitação
- Cards refletem dados ao vivo e agregações de período.
- Recomendações de sintonia exibidas por loop.
- Paridade visual com a versão PySide6 do executive dashboard.

## Páginas PySide6 (paridade)
`executive_dashboard`.

## Testes
- Vitest: cálculo/format de KPIs, seleção de janela de período.
- Playwright: dashboard executivo carrega e atualiza ao vivo.

## Riscos
- Agregações pesadas no cliente → preferir agregação no backend (REST existente).

## Dependências
Fatia 0+1 (WS, shell). Recomendado após 4 (stats) e 2 (IA).
