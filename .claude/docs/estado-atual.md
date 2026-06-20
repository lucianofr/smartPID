# Estado atual — Web HMI

## 🧪 TestSprite frontend run + fix TC003 (2026-06-20)

**Ambiente de teste (não óbvio — registrar):**
- Web Vite dev `:5173` (worktree) + backend `:8000`.
- Backend correto = **código do worktree (main)** rodado em **py3.13** via venv principal:
  `PYTHONPATH=<wt>/packages/smart_pid_core/src:<wt>/packages/smart_pid_domain/src SPID_JWT_SECRET=... SPID_API_PORT=8000 SPID_SIMULATOR_ENABLED=true .venv/bin/python -m smart_pid_core`
  (venv do worktree é py3.14 → `issubclass()` quebra asyncua/OPC; py3.13 resolve).
- Login: `admin` / `admin` (`~/.smart-pid/users.db`).
- Fix de proxy (dev): `vite.config.js` proxy `/api` ganhou `rewrite: /^\/api/ -> ''` (backend serve `/auth`, sem prefixo `/api`).

**Resultado TestSprite (dev mode, 15 de 33 high-priority): 11 pass / 4 not-pass.**
- **TC003 (bug real)** — abrir projeto pela lista `/projects` não dava feedback. **FIXED** + re-testado PASSED.
  - Fix: `src/features/projects/ProjectList.tsx` — `useNavigate` + `navigate('/')` no sucesso do open (espelha `WelcomeDialog`). Branch: `fix/projects-open-feedback` (criada de main, **não commitada**).
- TC007 / TC012 / TC014 — artefatos (faceplate sem Kp/Ki/Kd by design; sandbox rejeita `.spid`; sem alarme não-ack semeado). Sem mudança de código.

**Follow-ups antes de commitar o fix:**
- Atualizar spec fatia7 (`docs/superpowers/specs/2026-06-18-web-fatia7-*`) com "open na lista → navega p/ dashboard" (regra UI do CLAUDE.md). Spec fica no repo principal, não no worktree.
- WS `/ws/realtime` 403 era backend errado (sem RealtimeWS) — resolvido pareando backend main; não é bug de código.

---

## ✅ FATIA 8 (Themes + Faceplate) COMPLETA — merge main `814f902` (2026-06-20)
**TODAS AS 8 FATIAS DA MIGRAÇÃO WEB ESTÃO COMPLETAS.** Paridade visual + funcional total atingida.
A HMI PySide6 (`packages/smart_pid_hmi/`) pode ser aposentada (trabalho separado, ver follow-up abaixo).

### O que foi concluído (Fatia 8)
- 5 temas como blocos `[data-theme]` (Dark Room, ISA-101, MD3 dark, MD3 light, Ocean) + `ThemeSwitcher` persistido (`localStorage['spid.theme']`) no TopBar.
- `AnalogBar` instrumentado (valor/escala/alarme reais, `role=meter`, null-safe, `pv_decimals` por loop).
- Gate de contraste por tema (`themeContrast.ts`): texto ≥4.5:1; alarme não-textual ≥3:1 (WCAG 1.4.11; §8.4 reconciliado).
- uPlot tematizado por paleta (RealtimeTrend + MultiTrendChart re-init em troca de tema via MutationObserver).
- `Faceplate` (PV/SP/CO, modos, barras, SP stepper, CO manual gated MAN, apply-tuning) montado via Dialog no Dashboard (botão ⤢ no ControllerCard), reusando comandos da Fatia 2.
- 21 snapshots Playwright (5 temas × 4 breakpoints + faceplate).

### Merge / gates
- main HEAD = `814f902` (parents `2a17c78` + `95d4806`). **Frontend-only** (diff `*.py` vazio).
- Gates (HEAD `95d4806`): vitest 274/274, tsc -b 0, build OK (119.9 kB gz), e2e 21/21, lint 0 err (2 warns pré-existentes).
- Final review (code-reviewer opus): MERGE, 0 Crit/0 High. 1 MEDIUM (regressão pv_decimals) corrigido `95d4806`. 1 LOW (botão BYPASS) deferido.

### Decisões-chave
1. Contraste de alarme = 3:1 (não-textual WCAG 1.4.11), não 4.5/5:1 — cores de identidade preservadas; segurança daltônica via forma (ISA-101 §8.2).
2. Faceplate montado via Dialog (entry point definido nesta fatia; spec/plano eram silentes).
3. CO manual = input numérico validado (não slider).
4. `pv_decimals` por loop preservado (CO sempre %@1).

### Branch
- `feat/web-fatia8-themes-faceplate` merjado e **deletado**. Trabalho na worktree `.worktrees/main-web-hmi` (agora em `main`).
- Docs/trackers no branch `docs/web-hmi-implementation-plans` (commit `3c6ea8f`): INDEX/PROGRESS ✅, `_web-hmi-fatia8-digest.md`, specs reconciliadas (§8.4 `c1a1230`).

## Próximo (trabalho SEPARADO — não desta fatia)
**Aposentadoria da PySide6:** remover `packages/smart_pid_hmi/` do workspace e o caminho do publisher ZMQ tcp://5555 (se web-only).
Planejar + aprovar em branch dedicada. Follow-ups do spec owner em `.git/worktrees/main-web-hmi/sdd/fatia8-minor-findings.md`
(principal: adicionar `pv_scale {eu_min,eu_max,unit,decimals}` ao `ControllerResponse` — fecha a escala hardcoded 0-100 + decimals).
