# Design — Fatia 5: Simulador (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.
**Autoridade de UI/design:** [design-system](2026-06-18-web-frontend-design-system-design.md).

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
- REST `routers/simulator`:
  - output/modo: `POST /simulator/{controller_id}/co`, `POST /simulator/{controller_id}/pid/mode` (não `/simulator/output`, `/simulator/mode`).
  - preset: `POST /simulator/preset`; start/stop.
  - distúrbio: `POST /simulator/disturbance`, `DELETE /simulator/disturbance/{controller_id}`.
  - auto: `PUT /simulator/{controller_id}/auto-disturbance`, `PUT /simulator/{controller_id}/auto-sp`.
- WS: `status` (resposta do twin ao vivo).

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
