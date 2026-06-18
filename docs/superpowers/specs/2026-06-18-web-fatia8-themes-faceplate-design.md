# Design — Fatia 8: Temas + Faceplate (Web HMI Smart PID v2)

**Data:** 2026-06-18 · **Status:** Proposto
**Parte de:** [guarda-chuva](2026-06-18-web-hmi-react-migration-design.md). Arquitetura, ponte WS, contrato JSON e stack: ver §2–3 do guarda-chuva.

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
- Faceplate com paridade visual/funcional vs PySide6.
- ISA-101 atende padrão industrial (contraste/semântica de cor).

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
