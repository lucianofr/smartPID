# Design — Fatia 5: Simulador (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.

## Escopo
UI do simulador (digital twin): preset, parâmetros de dinâmica, injeção de distúrbio, controle de output/modo. (SVG overlay e "Export Dynamics to Loop" ficam fora — diferidos pela spec do projeto.)

## Backend
Nenhuma mudança — reusa `routers/simulator`.

## Frontend
- Seletor de preset de processo.
- Sliders de parâmetros de dinâmica.
- Injeção/remoção de distúrbio.
- Controle de output e modo do simulador; start/stop.
- Toggles auto-disturbance / auto-sp.

## REST/WS usados
- REST: `routers/simulator` (`POST /preset`, `POST /disturbance`, `DELETE /disturbance/{controller_id}`, `POST /output`, `POST /mode`, `PUT /{controller_id}/auto-disturbance`, `PUT /{controller_id}/auto-sp`, start/stop).
- WS: `telemetry` (resposta do twin ao vivo).

## Aceitação
- Preset aplicado altera a dinâmica visível na telemetria.
- Distúrbio injetado reflete no trend; remoção volta ao normal.
- Output/modo do simulador controláveis; auto-toggles funcionam.

## Páginas PySide6 (paridade)
`simulator_page`.

## Testes
- Vitest: controles de preset/sliders/distúrbio.
- Playwright: preset → resposta no trend; injeta distúrbio → degrau visível.

## Riscos
- Confusão simulador vs processo real → rótulo/contexto claro de modo simulação.

## Dependências
Fatia 0+1 (WS, trend). Recomendado após 2 (controles de loop/output).
