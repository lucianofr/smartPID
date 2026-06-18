# Design — Fatia 8: Temas + Faceplate (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.
**Autoridade de UI/design:** [design-system](2026-06-18-web-frontend-design-system-design.md) — fonte de tokens, componentes e temas desta fatia.

## Escopo
Paridade visual: temas de identidade e widget faceplate. Fecha a paridade total; após esta fatia a PySide6 pode ser aposentada.

## Backend
Nenhuma mudança.

## Frontend
- Temas via CSS custom properties (tokens): Dark Room, ISA-101, MD3 (dark/light), Ocean. Seletor de tema persistido.
- Widget faceplate: paridade funcional/visual (PV/SP/CO, modo, barra analógica, ações), consumindo `telemetry` (WS) e comandos (Fatia 2).

## REST/WS usados
- REST: comandos via routers existentes (faceplate reusa Fatia 2).
- WS: `telemetry`.
- Fonte de design: `docs/identidade_visual_Dark.md`, `docs/identidade_visual_ISA101.md`, `docs/identidade_visual_MD3.md`.

## Aceitação
- Troca de tema aplica tokens em toda a app; persiste entre sessões.
- Faceplate funcional: PV/SP/CO, modo, barra analógica e ações conferem com o quadro `status`/comandos; **AnalogBar instrumentado** (valor/escala/alarme refletem os dados, assert mensurável).
- Cada tema atende **contraste WCAG** (AA ≥ 4.5:1 texto normal) e **semântica de cor ISA-101** (cor reservada a estados anormais/alarmes), verificados por checagem objetiva — não "paridade visual" subjetiva.

## Páginas PySide6 (paridade)
`themes/*`, `faceplate`, `analog_bar`.

## Testes
- Vitest: troca/persistência de tema, render do faceplate por estado.
- Playwright/visual: snapshots por tema nos breakpoints chave.

## Riscos
- Drift da identidade visual → tokens derivados dos docs de identidade; revisão visual.
- Acessibilidade/contraste ISA-101 → checar contraste por tema.

## Dependências
Fatia 0+1 (shell) e Fatia 2 (comandos do faceplate).
