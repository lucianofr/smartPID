# Estado atual — Web HMI Fatia 2 (Commands + Loop Config)

_Atualizado: 2026-06-19 — Fatia 2 COMPLETA, READY TO MERGE (aguardando aprovação do usuário)._

## Situação
- Branch `feat/web-fatia2-commands-loop-config` (forked de main `427b670`), worktree `.worktrees/main-web-hmi`.
- 8/8 tasks concluídas via subagent-driven-development (opus). HEAD = `9abd81a` (+ commit de state save).
- Final whole-branch review (code-reviewer opus): **READY TO MERGE** — 9/9 binding constraints MET,
  0 Critical / 0 Important, 6 Minors não-bloqueantes (ver `.git/.../sdd/fatia2-minor-findings.md`).
- **Merge para main NÃO feito** — exige aprovação explícita do usuário (regra inviolável).

## Commits da fatia (main..HEAD)
- b3d8836 docs(web): investigation GAP-2a/2b + ai_config persist discovery
- 2bc72fb feat(web): loop-config types + validation
- e76ce8e feat(web): command REST wrappers + mutation hooks (+ apiPut/apiDelete em client.ts)
- 48f0aaa feat(web): AI control hooks (start/stop/pause/status, recommendation)
- a1665c4 feat(core): expose optimization_enabled in ControllerResponse  [único toque backend, aditivo]
- c9d3dbb feat(web): inline card controls (SP/mode/CO/optimizer toggle) + card ⚙
- f1977c0 feat(web): LoopConfigDialog (PID/IA/Limites) + Dialog primitive
- 286a190 feat(web): AI panel + apply-tuning confirmation guard
- 8ecc104 fix(web): surface apply-tuning errors (mutation; dialog stays open on fail)
- 9abd81a feat(web): wire dashboard + e2e fatia2-commands + specs (smartPIDv2 §13, ISA101 §4.3)

## Decisões tomadas (não re-litigar)
- **Seletor de engine de IA HABILITADO** (decisão do usuário 2026-06-19): persiste via
  PUT /controllers/{id} ai_config (controllers.py:330-447 aceita+persiste+hot-reload). Corrige a
  "AI-engine persistence GAP" do contrato (premissa desatualizada).
- **ai_config round-trip clobber-safe**: LoopConfigDialog envia os 9 campos completos (merge sobre
  initial.ai) — update_controller reconstrói o AIConfig inteiro; parcial resetaria rl_*/defaults.
- **optimization_enabled** adicionado ao ControllerResponse (+_to_response +5 testes) para o card
  ler o estado do toggle numa única query GET /controllers.
- Todas as rotas de comando/IA gated por `require_authenticated_admin` (P3 single-admin), NÃO
  operator/supervisor. Sem toast (erros via mutation.error.detail inline). Sem endpoints inventados.

## Verificação
- Vitest 63/63; Playwright e2e fatia2-commands 1/1 (REST mockado + WS stub, confirm-gate por
  contagem de rota); build limpo; ruff 0 novos (25 pré-existentes); mypy 541 (baseline, sem regressão).

## Próximos passos
1. **Aguardar aprovação de merge.** Ao aprovar: merge --no-ff em main, marcar Fatia 2 DONE no
   INDEX/PROGRESS (docs branch), salvar digest, deletar branch.
2. Minors M1-M6 → follow-up (não bloqueiam). M1 (casing AiStatus) e M2 (prop morto) os mais úteis.
3. Próxima: Fatia 3 (Alarmes) — nova branch de main.
