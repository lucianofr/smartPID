# Design — Fatia 4: Multi-trend + Estatísticas + Export (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.

## Escopo
Tendência multi-sinal/multi-loop ao vivo, estatísticas de performance por loop e exportação.

## Backend
Nenhuma mudança — reusa `routers/stats`, `routers/history`, `routers/export`.

## Frontend
- Página multi-trend: uPlot multi-série (vários loops/variáveis: PV/SP/CO), seleção de sinais, escala/eixos, janela deslizante.
- Painel de estatísticas por loop: IAE, ITAE, ISE, MSE, sigma, TV, variabilidade (`2σ/RANGE`, `2σ/SP`).
- Consulta de histórico (janelas/períodos) servida pelo historian.
- Export: geração + download do arquivo.

## REST/WS usados
- REST: `routers/stats` (`GET /{controller_id}/stats`, `GET /stats`); `routers/history` (`GET /history`); `routers/export` (`GET /list`, `GET /{export_id}`, `GET /{export_id}/download`, criação de export).
- WS: `telemetry` (alimenta o multi-trend ao vivo).

## Aceitação
- Multi-trend plota múltiplos sinais ao vivo sem travar (~60 fps).
- Stats por loop exibidos e coerentes com o backend.
- History consultável; export baixa arquivo válido.

## Páginas PySide6 (paridade)
`multi_trend_page`, parte de `settings_page` (stats).

## Testes
- Vitest: agregação/seleção de séries, formatação de métricas.
- Playwright: multi-trend recebe múltiplas séries; export gera download.

## Riscos
- Volume de pontos travando o gráfico → janela deslizante limitada + decimação no frontend.
- Janela de history grande → limites/paginação na REST existente.

## Dependências
Fatia 0+1 (WS, shell). Recomendado após 2 (contexto de loop).
