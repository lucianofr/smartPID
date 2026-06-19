# Estado atual — Web HMI migration

_Atualizado: 2026-06-19 — Fatia 3 (Alarms) concluída e mergeada._

## Onde paramos
- **Fatia 3 (Alarms) — ✅ COMPLETA, mergeada em main `4210142`** (`--no-ff`, parents `3a77ae5` + `05eb3a1`, 9 commits).
  Pós-merge verde: vitest 84/84 (19 files), e2e alarms 1/1, build limpo. Zero mudança de backend.
  Review final (code-reviewer opus): 0 Critical/0 High; 1 Important corrigido (`05eb3a1`, token CSS advisory).
- Branch `feat/web-fatia3-alarms` mergeada e **deletada**.

## Fatias concluídas
- 0+1 (merge `427b670`), 2 (`3a77ae5`), **3 (`4210142`)**. Preconditions P1–P4 em main.

## Próximo
- **Fatia 4 — Multi-trend + Stats + Export** — nova branch a partir de main `4210142`.
  Ordem restante: 4 → 5 → 6 → 7 → 8. Cada fatia: branch nova de main, subagent-driven (implementer →
  review → fix), TDD, subagents opus, commits convencionais sem attribution, merge só com aprovação.

## Fonte de verdade (docs branch `docs/web-hmi-implementation-plans`, worktree `.worktrees/web-hmi-plans`)
- `docs/superpowers/plans/_web-hmi-PROGRESS.md` — estado centralizado.
- `_web-hmi-INDEX.md` — checkboxes por tarefa + reconciliações cross-cutting (GAP register).
- `_web-hmi-fatia3-digest.md` — contratos FE a reusar + follow-ups F1–F5.
- `_web-hmi-backend-surface.md` / `_web-hmi-foundation-contract.md` — superfície backend + contrato canônico.

## Worktrees
- `.worktrees/main-web-hmi` @ `main` (`4210142`) — host de merge / fork das branches de fatia.
- `.worktrees/web-hmi-plans` @ `docs/web-hmi-implementation-plans` — planos/estado.
- Repo principal em `feat/windows-installers` — NÃO TOCAR.

## Flags em aberto (não bloqueantes)
- Rotas de alarme ainda usam `require_operator/require_supervisor` (web indiferente: admin satisfaz tudo, negative=401).
  Conflita com a alegação P3/TD-007 ("um único gate require_authenticated_admin") — revisar na Fatia 7.
- Follow-ups F1–F5 da Fatia 3 (CSS dedup, opcDown em `/alarms`, NavRail sem nav entry, AlarmConfigForm não montado, comentário) — em `_web-hmi-fatia3-digest.md`.
