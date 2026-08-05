# Design — Fatia 4: Multi-trend + Estatísticas + Export (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.
**Autoridade de UI/design:** [design-system](2026-06-18-web-frontend-design-system-design.md).

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
- REST `routers/stats`: `GET /controllers/stats`, `GET /controllers/{controller_id}/stats`.
- REST `routers/history`: `GET /history/{controller_id}` (path param **OBRIGATÓRIO**).
- REST `routers/export`: usar rotas existentes `GET /export/{export_id}`, `GET /export/{export_id}/download` (+ criação de export). **GAP:** NÃO há `GET /export/list` (sem endpoint de listagem) → confirmar/criar mecanismo de listagem antes de expor histórico de exports.
- WS: `status` (alimenta o multi-trend ao vivo).

## Aceitação
- Multi-trend plota múltiplos sinais ao vivo respeitando **frame-budget** (≤ 16 ms/frame),
  **cap de janela** (N pontos/segundos configurável) e **decimação** quando excede o cap —
  sem travar a UI.
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
