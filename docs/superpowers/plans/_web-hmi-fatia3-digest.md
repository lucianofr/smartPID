# Fatia 3 digest — Alarms (merged main `4210142`, 2026-06-19)

Web alarm surface on the Live Dashboard + a dedicated `/alarms` page. **Zero backend change**
(verified `git diff main...HEAD -- '*.py'` empty). Forked main `3a77ae5`; merged `--no-ff` →
`4210142` (parents `3a77ae5` + `05eb3a1`). 9 commits.

## Delivered (all under `packages/smart_pid_web/src/features/alarms/` unless noted)
- `types.ts` — `ActiveAlarm` (REST row), `AlarmType`/`AlarmPriority`/`AlarmStatus` string-literal unions, and **hand-typed** `AlarmThreshold`/`AlarmConfigResponse`/`AlarmConfigUpdate` (NOT from generated OpenAPI — `src/api/generated/` is gitignored).
- `severity.ts` — `priorityRank`, `severityIcon` (octagon/triangle/diamond/dot), `severityClass` (`sev-<priority>`), `isUnacked`.
- `useAlarms.ts` — `alarmsKeys.active = ['alarms','active']`, `useActiveAlarms`, `useAckAlarm`, `useAckAllAlarms` (onSettled invalidate — revalidate, never optimistic), `useAlarmRealtimeSync` (WS `'alarm'` + `onResync` → invalidate active).
- `useAlarmConfig.ts` — `alarmConfigKey(id)=['alarms','config',id]`, `useAlarmConfig`, `useUpdateAlarmConfig` (full-array PUT, onSuccess setQueryData on the config key only).
- `AlarmPanel.tsx`/`.css` — virtualized (`@tanstack/react-virtual`) active list; dedupe by id; sort severity/time; filter state/loop; per-row ack + ack-all; ISA-101 icon+color+text; aria-live for new CRITICAL.
- `AlarmBar.tsx`/`.css` — persistent 36px footer; counts CRIT/WARN/DIAG; blink unacked; ACK ALL.
- `AlarmConfigForm.tsx`/`.css` — 6 alarm types (enabled/limit/priority); full-array PUT replace-all. **Mounted nowhere yet** (building block for a per-loop affordance / Fatia 7).
- `src/components/shell/AppShell.tsx` — EXTENDED: `<AlarmBar/>` mounted as persistent footer (children-shape, not Outlet). + `AppShell.test.tsx` smoke.
- `src/App.tsx` — `/alarms` protected route (mirrors dashboard: RequireAuth + AppShell + AlarmPanel).
- `src/theme/themes.css` — added `--alarm-diag-bg` (dark-room/isa101) to match critical/warning `-bg` convention.
- `e2e/alarms.spec.ts` — lifecycle e2e. specs: smartPIDv2 §9.3, identidade_visual_ISA101 §4.5.
- New dep: `@tanstack/react-virtual@^3.14.3`. Test infra: `src/test/setup.ts` got a guarded `ResizeObserver` no-op polyfill.

## Contract facts (for downstream fatias)
- **Alarm REST (all auth-required; admin satisfies the guards):** `GET /alarms/active` → bare `list[dict]` rows (`id,controller_id,controller_name,alarm_type,priority,value,limit,timestamp,cleared_at,acknowledged(0|1),ack_by_user,ack_at,status`); `POST /alarms/{id}/ack` (no body); `POST /alarms/ack-all` (no body); `GET|PUT /controllers/{id}/alarm-config` → `AlarmConfigResponse{controller_id,thresholds:AlarmThreshold[]}` (PUT body `AlarmConfigUpdate{thresholds}` replaces ALL). active/ack/ack-all have NO response_model (typed by hand).
- **GAP-3a:** `AlarmStatus` = `UNACKNOWLEDGED|ACKNOWLEDGED|CLEARED_UNACK` (3 values; ack≠clear; cleared+acked leaves the active list). `AlarmPriority`=CRITICAL|WARNING|ADVISORY|LOG; `AlarmType`=HIHI|HI|LO|LOLO|DV_HI|DV_LO.
- **GAP-3b:** WS `RealtimeEnvelope<…>{type:'alarm'}` payload = `{controller_id,controller_name,controller_description,alarm_type,priority,transition,value,limit,timestamp}` — NO id/status. It is a **refetch trigger** for `['alarms','active']`; never rendered as a row.
- **Canonical to reuse:** `alarmsKeys`, `useActiveAlarms`/`useAckAlarm`/`useAckAllAlarms`/`useAlarmRealtimeSync`, `severity.ts` helpers, `types.ts`. AlarmBar lives in the AppShell footer.
- **AUTH NOTE:** alarm routes on this branch are `require_operator` (active/ack/ack-all/get-config) + `require_supervisor` (put-config) — NOT `require_authenticated_admin`. Web unaffected (single admin = role level 2 satisfies all; no role gating; negative auth = 401). **Conflicts with PROGRESS P3/TD-007 "single gate, no route ungated" claim — investigate at Fatia 7.**

## Follow-ups deferred (non-blocking; full list in `.git/.../sdd/fatia3-minor-findings.md`)
F1 keyframes/glyph CSS duplicated across AlarmPanel.css+AlarmBar.css (consolidate); F2 `/alarms` hardcodes `opcDown={false}` → stale TopBar OPC (shared shell/opcDown hook); F3 NavRail is empty app-wide → `/alarms` undiscoverable (add nav entry); F4 AlarmConfigForm+config hooks unmounted (add TODO(fatia-7) mount marker); F5 useAlarms.ts doc comment EVENT.SYSTEM drift. Accepted: jsdom test shims, effect-seeds-draft, ^caret pin.
