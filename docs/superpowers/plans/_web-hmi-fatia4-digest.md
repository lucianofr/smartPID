# Fatia 4 digest — Multi-trend + Stats + Export (merged main `4ea9df6`, 2026-06-19)

Multi-loop trend page (`/multitrend`) + per-loop performance stats + historian query + data export.
**Zero backend change** (verified `git diff main...HEAD -- '*.py'` empty). Forked main `4210142`;
merged `--no-ff` → `4ea9df6` (parents `4210142` + `9b34b24`). 17 commits. Gates: vitest 123/123,
tsc 0, vite build OK, e2e 2/2.

## Delivered (all under `packages/smart_pid_web/src/features/multitrend/` unless noted)
- `types.ts` — `Variable` ('pv'|'sp'|'co'), `SignalKey`, `SeriesSelection`, `WindowConfig`, `StatsRow` (camelCase UI alias).
- `signals.ts` — `signalId`/`parseSignalId`, `seriesColor`/`seriesStroke` (theme-token + per-loop tonal lightness via `color-mix`, NO new colors), `DEFAULT_WINDOW` (600 pts / 60 s).
- `multiTrendData.ts` — `valueAt(status,var)` = `status[var].value` (FFSignal), `LoopBuffer`, `AlignedSeries`, **`selectSeries`** (uPlot AlignedData; reconciles all selected rows + x to a COMMON newest-aligned window = min length, no nulls — prevents uPlot cross-loop misalignment).
- `decimate.ts` — `applyWindow` (time-window then point-cap, drop-from-left keeps newest), `minMaxDecimate` (min/max per pixel column, output ≤ `pxWidth*2`, peak-preserving).
- `useMultiTrendModel.ts` — ring buffers from `useRealtime().lastStatus`; `toEpochSeconds(ts: string|number)` (ISO→/1000, number→passthrough, NaN-guard); lockstep `HARD_BUFFER` trim (equal-length invariant); `series = selectSeries→applyWindow→minMaxDecimate`; `{series,paused,setPaused,setSelection,setWindow,setPxWidth}`.
- `format.ts` — `StatsDto` (real wire fields), `toStatsRow` (snake→camel: `std_dev→sigma`, `total_variation→tv`, `variability_range→varRange`, `variability_sp→varSp`), `formatMetric` (toFixed(3), '—' non-finite), `formatVariabilityPct` ((r*100).toFixed(1)+'%').
- `useStats.ts` — `['stats','all']` REST `GET /controllers/stats` seed (refetchInterval 5s) overlaid by live `useRealtime().lastStats` (live wins); rows sorted by loopId.
- `useHistory.ts` — `['history',params]` `GET /history/{controllerId}` (controller_id PATH; start/end/limit query; `enabled: params!==null`); `HistoryResponse{controller_id,frames:TelemetryFrame[],count}`, `TelemetryFrame{timestamp,pv,sp,co,mode,status}` (PLAIN numbers — historian flattens FFSignal).
- `useExport.ts` — create (`POST /export`) → poll (`GET /export/{id}`, refetchInterval stops on done/error) → `phase` state machine + `downloadHref`. `ExportJob{id,controller_id,start,end,format,status:pending|running|done|error,progress,file_path}`.
- `MultiTrendChart.tsx` — uPlot; aligned to canonical `src/components/RealtimeTrend.tsx` (theme `readToken('--trend-axis'/'--trend-grid')`, try/catch around `new uPlot` for jsdom, `--trend-bg`); PV/SP on `'pv'` scale + CO on `'co'` `range[0,100]`; SP dashed; no area-fill; `onPxWidth` report-up; shape-keyed re-create + separate `setData` effect.
- `SeriesSelector.tsx` — checkbox per loop×variable (`aria-label` `Loop {n} · {VAR}`), swatch via `seriesStroke`.
- `StatsPanel.tsx` — 8 metrics (IAE/ITAE/ISE/MSE/σ/TV/2σ-RANGE/2σ-SP) per loop, empty state.
- `HistoryQuery.tsx` — datetime-local start/end → ISO, limit, Query→onQuery; count + frames table (`numeric` class).
- `ExportButton.tsx` — generating→"Gerando…"; idle/error→button "Export"/"Retry export"; done→**authenticated blob download button** (`apiDownload('/export/{id}/download')`→Blob→objectURL→`<a download>`→revoke; try/catch/finally + "Download failed — retry").
- `src/pages/MultiTrendPage.tsx` — self-shells via `<AppShell opcDown>` (real `/opcua/status` query), bento layout; loops derived from stats rows.
- `src/App.tsx` — `/multitrend` route = `RequireAuth > MultiTrendPage` (self-shelled, like DashboardPage).
- `src/components/shell/NavRail.tsx` — **now functional**: `NavLink`s Dashboard `/` · Multi-trend `/multitrend` · Alarms `/alarms` (token-styled, active = `--text` + `--surface-container-high` + left-border; no `--accent` token exists).
- `src/api/client.ts` — `apiDownload(path): Promise<Blob>` (authenticated GET, reuses tokenGetter/ApiError/`/api` prefix).
- `src/realtime/envelope.ts` — `StatsData` CORRECTED to real wire (`iae,itae,ise,mse,std_dev,total_variation,variability_sp,variability_range`); `StatusData.timestamp: string|number`.
- `e2e/multitrend.spec.ts` — multi live series (StubWS loops 1&2) + authenticated export download. Docs: smartPIDv2 §Fatia4, identidade_visual_ISA101 (series distinguishability).

## Contract facts (for downstream fatias — verified vs real backend this session)
- **Stats wire (REST == WS, identical snake_case):** `GET /controllers/stats`→`list[StatsResponse]`, `GET /controllers/{id}/stats`→`StatsResponse` (both `response_model`, in `smart_pid_domain/dtos/ai.py`); WS `STATS.{id}` = `stats_worker.get_current_stats()`. Fields: `controller_id, iae, itae, ise, mse, std_dev, total_variation, variability_sp, variability_range, mean_abs_error, pk_pk_error, reversals, zero_crossings, recent_pk_pk_error, recent_reversals, tv_per_sample, osc, sample_count`. **There is NO `sigma/tv/var_range/var_sp` on the wire** — the INDEX cross-cutting "DIFFERENT keys, unify" premise was WRONG. **Fatia 6 `kpi.ts` MUST use the real snake_case names.**
- **STATS IS bridged to the web:** RealtimeWS (`realtime.py`) subscribes `b"STATS."` on the bus directly (the legacy tcp:5555 whitelist skips it; the web bridge does not) → envelope type `stats`, `useRealtime().lastStats` keyed by loop_id is LIVE.
- **STATUS timestamp is dual-typed:** `pid_worker.py:429/454` ISO-8601 string (execute mode); `monitor_worker.py:137` `time.time()` numeric epoch (monitor mode — the PRIMARY path). FE `StatusData.timestamp: string|number`; parse via `toEpochSeconds`.
- **History:** `GET /history/{controller_id}` (controller_id PATH required; `start`/`end` ISO datetime, `limit` 1..10000 default 1000) → `HistoryResponse` (has `response_model`); frames flatten pv/sp/co to plain floats + status "GOOD"/"BAD".
- **Export (GAP-4a):** `POST /export`→`ExportJob` (201), `GET /export/{id}`→`ExportJob`, `GET /export/{id}/download`→FileResponse (409 until done; legit NO response_model). NO `/export/list` — export-history listing scoped OUT. Models in `dtos/export.py`.
- **Auth for downloads:** REST auth = Bearer JWT header (sessionStorage `smart-pid-token`), NO cookie → plain `<a href>` to a protected endpoint 401s. Use `apiDownload` (Bearer-blob). All Fatia-4 routers gated (admin satisfies).
- **Canonical to REUSE:** `apiDownload` (client.ts) for any future authenticated file download; `format.ts` (toStatsRow/formatMetric/formatVariabilityPct); `MultiTrendChart`/RealtimeTrend uPlot theme conventions; `NavRail` NavLink pattern (add new routes there). Page convention: full pages self-shell via `<AppShell opcDown>` + own `/opcua/status` query.

## Deferred (non-blocking; full list in `.git/.../sdd/fatia4-minor-findings.md`)
HIGH series-misalignment was FIXED pre-merge (`9b34b24`). Remaining LOW: `.mono-tabular`↔`.numeric` dedup; dead `useExport.downloadHref` (cleanup — don't tempt an unauthenticated path); `apiDownload` no JSON-`detail` parse; export loop-0 fallback guard; `onPxWidth` resize via ResizeObserver; `useStats` refetchInterval redundancy; `--space-N` token scale undefined (pre-existing repo-wide); `sample_count`/no-data em-dash (deferred by decision); fireEvent→userEvent test nits. §10 design-system spec doc update pending on this docs branch.
