# Fatia 6 digest — Executive Dashboard (merged main `0961c7c`, 2026-06-19)

Executive overview page (`/executive`): aggregate KPI bento cards + per-loop health/OPC pill +
configurable period window + per-loop tuning recommendations, with live WS overlay. **Zero backend
change** (verified `git diff main...HEAD -- '*.py'` empty). Forked main `4a4472e`; merged `--no-ff`
→ `0961c7c` (parents `4a4472e` + `fd5847b`). 10 commits. Gates: vitest 183/183 (48 files), tsc 0,
vite build OK, e2e 2/2, lint 0 err (2 pre-existing warns).

## Delivered (packages/smart_pid_web/src/ unless noted)
- `lib/period.ts` — `PeriodKey` 15m/1h/8h/24h/7d; `periodRange(key,now?)->{startIso,endIso,key}`; `PERIOD_OPTIONS`.
- `lib/kpi.ts` — `StatsResponseLike` (REST snake_case subset), internal `LoopKpis` (camelCase), `fromRestStats`/`fromWsStats` (THE single snake->camel mapping point), `aggregate` (loopCount/avgVariabilityRange/totalTv/avgIae/autoPct; empty->zeros, no NaN), `isAutoMode` (AUTO/CAS/RCAS), `formatKpi` (pct/index/count), `variabilityOutOfTarget` (default 0.05).
- `api/executive.ts` — 6 RQ hooks: `useAllStats`(['controllers','stats']), `useControllers`(['controllers']), `useAiStatus`/`useTuningRecommendation` (REUSE commandApi queryFns+types+keys ['ai','status',id]/['tuning','rec',id]; enabled-gated + retry:false = 404-as-null), `useAiHistory`(range[,id]) (start+end ISO), `useOpcuaStatus`(['opcua-status']). Hand-typed `ControllerSummary` + `AiHistoryEntry` (generated/ gitignored).
- `components/ExecutiveKPICard.{tsx,css}` — big mono-tabular value (`.numeric` + `--text-2xl`), label, out-of-target delta (neutral default; `--alarm-warning` only via `data-out-of-target`), optional neutral range bar. Plain `.css` + `exec-kpi-*` (NO CSS modules), real tokens.
- `components/{LoopHealthRow,PeriodSelector,TuningRecommendationCard}.tsx` — presentational (data-attrs; null rec = "No tuning recommendation"; PeriodSelector from PERIOD_OPTIONS).
- `pages/ExecutiveDashboardPage.{tsx,css}` — self-shells `<AppShell opcDown>` (reuse `useOpcuaStatus`); 5 aggregate KPI cards + loop-health section + per-loop `LoopTuningDetail` CHILD (isolates per-loop hooks — Rules-of-Hooks safe); page-level `useAiHistory` once. Live overlay: REST seed then `lastStats`/`lastStatus` win per id; `onResync` invalidates ['controllers']/['controllers','stats']/['opcua-status']. Route `/executive` (RequireAuth) + NavRail "Executive".
- `e2e/executive-dashboard.spec.ts` — StubWS (`__pushStats`) + stateful route doubles; load (kpi-iae 12.50, variability 4.0%, OPC ONLINE) + live stats frame -> Avg IAE 12.50->9.00 NO reload. Docs: `docs/smartPIDv2.md` §16.

## Contract facts (for downstream — verified vs real backend)
- **Stats wire = identical snake_case REST+WS** (`std_dev/total_variation/variability_sp/variability_range/sample_count`); NO `sigma/tv/var_sp/var_range` on the wire. The earlier INDEX "different keys, unify" premise was WRONG (now corrected in INDEX cross-cutting). `kpi.ts` is the single snake->camel mapping point.
- Loop list `GET /controllers` (NOT `/active`) -> `ControllerResponse` (executive reads id/name/mode; live error/saturated come from WS STATUS, not REST).
- AI per-loop: `GET /controllers/{id}/ai/status` (`AIStatusResponse`), `/ai/history` (`AIHistoryResponse`, has response_model). Tuning rec `GET /commands/tuning-recommendations/{id}` 404=none (`TuningRecommendationResponse`). AI log range `GET /alarms/ai-history` (start+end ISO REQUIRED, NO response_model -> `list[dict]`). The 2 no-response_model endpoints reused-as-is (NOT patched — frontend-only).
- REUSE canon: Fatia2 `commandApi.ts` `getAiStatus`/`getTuningRecommendation` (shared cache, no fragmentation); Fatia4 `useStats`/`format.ts` pattern; shared `['opcua-status']` key + page self-shell convention; `--sp-N`/`--surface*`/`--alarm-warning` tokens; `.numeric` mono class.

## Deferred (non-blocking; full list in `.git/worktrees/main-web-hmi/sdd/fatia6-minor-findings.md`)
12 minors, all DEFER per final review: kpi/format snake->camel overlap (plan-mandated separate module); `as`-casts in enabled-gated hooks; `AiHistoryEntry.timestamp` string guess (count-only, no field rendered); ExecutiveKPICard nits (JSX.Element annotation, bare aria-hidden, range-bar aria-hidden, delta testid when no testId); `<p>` direct child of `<dl>` (brief-mandated); opcState union cast; static kpi-variability delta arrow. L13 duplicate `<main>` landmark FIXED pre-merge (`e4f43db`).
