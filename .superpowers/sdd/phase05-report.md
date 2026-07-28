# Phase 5 — Loop Configuration, Commands and AI — Completion Report

**Status:** COMPLETE — all 5 tasks shipped, phase gate green.
**Plan:** `docs/superpowers/plans/2026-07-26-phase05-loop-config-commands-ai.md`
**Worktree:** `.worktrees/web-frontend-rewrite`

## Commits

| SHA | Subject |
|---|---|
| `fa0cfc9` | `feat(web): add typed loop command mutations` |
| `6dcb7b1` | `feat(web): restore operator loop controls` |
| `dcd5ba7` | `feat(web): add AI lifecycle and tuning confirmation` |
| `021dc0f` | `feat(web): add role-gated loop configuration` |
| `a7590d3` | `test(web): cover commands and user role gating` |

(A concurrent backend agent owns `tests/` and `packages/smart_pid_core/` on this
branch; nothing under those paths was staged by this phase.)

## Gate results

| Gate | Result |
|---|---|
| `npm run test -- --run` | **337 passed / 50 files** (was 292 / 45 at phase 4) |
| `npm run typecheck` | exit 0 |
| `npm run lint` | exit 0 |
| `npm run test:e2e -- e2e/fatia2-commands.spec.ts e2e/user-role.spec.ts` | **6 passed** |
| 6 phase-4 E2E specs | **34 passed** — no regression |
| `npm run build:budget` | exit 0 — 161.8 KB gzip JS (budget 300), delta +6.1 KB |

E2E commands run:

```
npx playwright test e2e/fatia2-commands.spec.ts e2e/user-role.spec.ts
npx playwright test e2e/faceplate.spec.ts e2e/target-size.spec.ts \
  e2e/responsive.spec.ts e2e/login-dashboard.spec.ts \
  e2e/themes.spec.ts e2e/fatia7-auth-negative.spec.ts
```

## What shipped

### Task 1 — validation and command mutations
- `features/loop-config/types.ts`: `CONTROLLER_MODES`, `AI_ENGINES`, `OBJECTIVES`,
  `PROCESS_SPEEDS`, `EXECUTION_MODES`, `PID_STRUCTURES`, `INTEGRAL_TYPES`,
  `SHED_OPTIONS` — each a 1:1 mirror of a `smart_pid_domain.enums` StrEnum.
- `validation.ts`: `validateSetpoint(value, range?)`, `validateOutput`,
  `validateTuning`, `validatePidParams`, `validateLimits`, `validateAiConfig`,
  `hasErrors`. Messages are pt-BR and exactly the strings the plan pinned
  (`Setpoint deve estar entre 0 e 100`, `Saída deve estar entre 0 e 100`,
  `Kp deve ser maior que 0` / `Ti deve ser maior que 0` / `Td não pode ser negativo`).
  `Td = 0` is a PI controller, not an error; `alpha` is clamped to 0..1.
- `commandApi.ts`: `setSetpoint`/`setMode`/`setOutput`/`applyTuning` **delegate to
  `endpoints`** rather than restating the request bodies — one definition per
  write and one spy seam, which is why the phase-4 `Faceplate` unit tests keep
  intercepting the calls now issued from `CardControls`. New here:
  `setOptimization`, `writeTuning`, `getTuningRecommendation`, `sendAiAction`,
  `updateController`, `createController`, `deleteController`.
- `useCommands.ts` / `useAiControls.ts`: typed mutations invalidating
  `queryKeys.controllers` + `queryKeys.aiStatus(id)`. Error routing is
  deliberately absent — `apiClient` already dispatches 401/403 to the auth hooks
  (§11), and 409/422 stay on the mutation as `error` so the form keeps its input.
  `useAiStatus` reuses `queryKeys.aiStatus`, the key the §7 resync primes.
- `api/types.ts` gained `CommandResponse`, `AiConfigDto`, `ScaleConfigDto`,
  `TagBindingsDto`, and `endpoints` now returns the real `CommandResponse`
  instead of `Record<string, unknown>`.

### Task 2 — card controls
- `CardControls.tsx`: `Setpoint` spinbutton + `Set setpoint`, native
  `<select aria-label="Mode">` carrying the full nine-member block enum, `Saída`
  spinbutton + `Set output` enabled only in `MAN`. Whole component behind
  `useCan('loop.operate')`. A `controls` prop selects which of the three render
  (default: all three).
- Mounted twice, disjointly (see *Decisions* #1): `controls={['mode']}` through
  the selected `LoopCard`'s `controlsSlot`, composed with the phase-4 `Abrir`
  button; `controls={['setpoint']}` and `controls={['output']}` inside the
  faceplate, where the CO field shares the draft with the `Manual CO` slider.

### Task 3 — loop configuration dialog
- `LoopConfigDialog.tsx`. Always rendered: `Nome`, `Descrição`,
  `Modo de execução`, `Taxa de varredura (s)`, `NodeID PV/SP/CO/Ti`.
- `DDC_SECTIONS` is exported and pinned by a test: `PID Tuning`,
  `Scaling & Limits`, `Filters & IO`, `Shed & Safety`, `PID Structure`,
  `Integral Type` — each a `<section aria-label>` (role `region`), rendered only
  when the execution mode is `DDC`. Under `SUPERVISORY` the DCS owns those
  values, so offering them would invite a write the DCS immediately overrides.
- Writes gated by `useCan('controllers.manage')`: without it the fields render
  **disabled** and `Salvar` / `Excluir` are absent. Delete opens a nested
  `alertdialog` whose `Excluir definitivamente` unlocks only once the tag is
  typed back verbatim.
- `NewLoopDialog` (same file) covers the create leg of CRUD — name, description
  and execution mode, since `ControllerCreate` defaults every other field. Its
  `Nova malha` trigger sits in the `Malhas` strip and in the empty state, both
  admin-only.

### Task 4 — AI panel and tuning confirmation
- `AiPanel.tsx` mounts inside the faceplate as `region "Otimização IA"`.
  `tuning.edit` gates engine/objective/process-speed/dead-time/guardrail editing
  (`Salvar IA` → `PUT /controllers/{id}`) and `Apply tuning`; `ai.control` gates
  `Start` / `Pause` / `Stop`, which post `/controllers/{id}/ai/{action}` and
  never touch the block mode — the optimizer lifecycle is independent of AUTO/MAN.
- The form is `persisted ?? draft`: the baseline comes from the cached controller
  roster, `draft` holds only the fields the operator touched, and a successful
  save clears it — a resync shows through without stomping an edit.
- `role="log"` terminal box, `aria-label="LOG.AI"`, fed by
  `useRealtime(controllerId, 'ai')`, capped at 100 lines and auto-scrolled.
- `ConfirmApplyTuningDialog.tsx`: current-vs-recommended Kp/Ti/Td table, the
  engine's stated reason, and a destructive `Confirm Write`. Nothing is posted
  until that button; a rejection keeps the dialog open and renders the detail.
- `Apply tuning` is disabled unless the recommendation status is `pending`.

### Task 5 — E2E
- `fatia2-commands.spec.ts`: `/api/auth/me` added, the complete §7 resync set
  stubbed (`alarms/active`, `alarms/history**`, `ai/status`, `opcua/status`,
  `simulator/status`), and the WS stub now advances `seq` monotonically instead
  of pinning `seq: 1`. `FULL_CONTROLLER` gained the wire fields the phase-3
  schema actually carries (`pv_scale`, `sp_lo_lim`/`sp_hi_lim`, `process_speed`,
  `mode`). Every command assertion and accessible name is unchanged.
- `user-role.spec.ts` (new, 5 tests): a `user` keeps setpoint, mode, manual
  output, the CO slider and `ACK ALL`; `Apply tuning`, `Start`/`Pause`/`Stop`,
  the AI region, `Salvar IA` and `Nova malha` are all absent; the config dialog
  is read-only with no `Salvar`/`Excluir`; the admin counterpart sees all of it;
  and a forced `403` on `POST /commands/setpoint` raises the `sem permissão`
  toast **and** triggers a second `GET /auth/me` (§11 role-changed recovery).

## Decisions worth carrying forward

1. **`CardControls` is split across two mounts, not duplicated.** The plan asks
   for it in `controlsSlot`; four retained phase-4 assertions bind `Setpoint`,
   `Set setpoint` and `Set output` *inside* `complementary "Faceplate {tag}"`
   (`faceplate.spec.ts:29-31,54`, `responsive.spec.ts:97-98`,
   `target-size.spec.ts:37-38`), while `fatia2-commands.spec.ts` addresses all of
   them with page-level locators that break under Playwright strict mode if two
   copies exist. A single instance therefore cannot satisfy both. Resolution:
   the card strip carries the quick mode switch (`controls={['mode']}`, only on
   the selected card, composed with `Abrir`), the faceplate carries numeric
   SP/CO entry. Both mount points are explicit; the default (all three) is what
   the unit test exercises. **Do not add a second SP box to the card strip.**
2. **`Apply tuning` moved from the faceplate body into `AiPanel`**, which is
   itself mounted inside the faceplate. `target-size.spec.ts:39` measures it
   inside the faceplate subtree and `faceplate.spec.ts:32` asserts it is absent
   for `user`, so both still hold — but it is now guarded by
   `ConfirmApplyTuningDialog` instead of writing on the first click.
3. **The faceplate `<aside>` scrolls at ≥1024** (`lg:overflow-y-auto`). The AI
   panel makes the column taller than the viewport on short screens and the
   parent detail row is `lg:overflow-hidden`.
4. **`ai/status` and `tuning-recommendations` are `require_user`**, verified in
   `routers/ai.py:57` and `routers/commands.py:290` — a `user` session does not
   403 on them. They are still `enabled`-gated on the capability so a user-role
   dashboard issues no pointless fetch.
5. **`endpoints.set*` are typed `CommandResponse` now.** Two phase-4 mocks moved
   from `mockResolvedValue({})` to `mockResolvedValue({ ok: true })`.
6. **The harness controller payload is fuller**: `ai_config`, `process_speed`,
   `sp_lo_lim`/`sp_hi_lim`. Reading `controller.ai_config.engine` off the old
   partial payload crashed `AiPanel`; the component is defensive now *and* the
   fixture is honest.

## Concerns / follow-ups

- **The faceplate misses the very first status frame after a resync.**
  `useRealtime` has no last-value replay, and `flushResyncBuffer()` dispatches in
  the same microtask in which the resync's `setQueryData(controllers)` first
  renders the faceplate — so its subscribe effect has not run yet. Live systems
  paper over this (the next frame lands within one scan), but on a slow loop the
  faceplate shows `—` for a scan period after reconnect. It predates phase 5
  (`fatia2-commands.spec.ts` therefore scopes its mode-badge assertion to the
  card, which is fed by the page-level `useLoopStatuses`). A `lastPerTopic` map
  in `RealtimeProvider` would fix it; that is a phase-3 contract change.
- **`alarms.spec.ts` and `multitrend.spec.ts` are still red — pre-existing.**
  They address `data-testid="alarm-row-*"` and `Loop 1 · PV` signal checkboxes,
  neither of which exists anywhere in `src/` at the phase-4 HEAD (`cbf1ce9`) —
  verified with `git grep 'data-testid="alarm-row' cbf1ce9`. Phases 6 and 8 own
  them. `npm run test:e2e` with no arguments remains red by design.
- **`Salvar IA` writes `process_speed` + `ai_config` through the generic
  controller PUT.** There is no dedicated AI-config endpoint; if one appears,
  move it off `updateController`.
- **`pv_decimals` is still absent from the wire.** The faceplate and cards keep
  defaulting to 1 decimal; a per-loop decimals field would belong in
  `LoopConfigDialog`'s `Scaling & Limits` section once the backend carries it.
