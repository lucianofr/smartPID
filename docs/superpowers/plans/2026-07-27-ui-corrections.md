# UI Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the six UI corrections of `docs/superpowers/specs/2026-07-27-ui-corrections-design.md` §4–§9 — a non-scrolling full-height faceplate rail, the AI configuration form relocated into the loop config dialog, the command palette removed, icons replacing `[cfg]`, the executive dashboard in the top bar, and Trends gaining persisted selection plus titled cells.

**Architecture:** Frontend-only, inside `packages/smart_pid_web`. The faceplate height budget only closes after the ~417 px AI configuration form leaves the rail, so Task 1 (the move) strictly precedes Task 2 (the layout and compaction). The remaining tasks are independent of each other: palette removal, icon swaps, the nav entry, the trend-selection store, and trend titles each touch disjoint files. Task 8 updates the `TEST_E2E.md` gate and Task 9 is the verification sweep.

**Tech Stack:** React 18, TypeScript 5.5, Vite 5, Tailwind CSS v4, `radix-ui`, `lucide-react`, `@tanstack/react-query` v5, `uplot`, Vitest 2 + `@testing-library/react`, Playwright 1.46.

## Global Constraints

- UI copy is **pt-BR**. Code, identifiers, comments and commit messages are **English**. Commits follow **Conventional Commits**.
- Accessible names that existing tests bind to **MUST NOT change**. Frozen verbatim: the `SeriesSelector` checkbox `aria-label` `Loop {id} · {SIGNAL}`, `Configurações`, `Configurar {tag}`, `Usuário`, `Senha`, `Entrar`, `Salvar`, `Fechar`.
- Every interactive target stays **≥ 44×44 CSS px** (E2E-050). Any compaction lever that would breach this is rejected; reduce the LOG.AI floor instead.
- WCAG floors are hard: **4.5:1** for text (1.4.3), **3:1** for non-text (1.4.11). `src/theme/themeContrast.test.ts` enforces them in CI. No floor may be relaxed.
- `TEST_E2E.md` assertions may be **re-specified or strengthened, never weakened**.
- **Frontend only.** No Python, no backend change. The full backend suite is not re-run.
- Playwright is the only sanctioned browser verification: `cd packages/smart_pid_web && env -u CI npx playwright test`. **Never** use the omp `browser` tool for input — it does not deliver CDP mouse/keyboard events to the page and has produced false "dead control" reports.
- Out of scope for this plan (owned by the sibling `neon` theme plan): everything under `src/theme/`, `src/index.css` glow utilities, `index.html`, `src/assets/fonts/`, and `TEST_E2E.md` procedures **E2E-045** and **E2E-046**. Do not touch them.
- `Faceplate.tsx` and `DashboardPage.tsx` are owned by **this** plan. The sibling theme plan only consumes tokens from them.

---

## File Structure

**Created**

| File | Responsibility |
|---|---|
| `src/features/loop-config/AiConfigSection.tsx` | The six AI configuration fields as a controlled, presentational fragment. Owns no state and no mutation. |
| `src/features/multitrend/trendSelectionStore.ts` | Two pure functions over `localStorage['spid.multitrend']`: `readTrendSelection()` / `writeTrendSelection()`. |
| `src/features/multitrend/trendSelectionStore.test.ts` | Round-trip, defensive-parse and write-failure coverage for the store. |

**Modified**

| File | Change |
|---|---|
| `src/features/loop-config/AiPanel.tsx` | Loses the config form, the standalone `Salvar IA` button and the `updateController` mutation. Its LOG.AI box becomes the elastic element. |
| `src/features/loop-config/LoopConfigDialog.tsx` | `Draft` gains `process_speed` + `ai`; one new `<Section label="AI Optimization">`; `save()` and `blocked` extend. `NewLoopDialog` copy stops naming `[cfg]`. |
| `src/pages/DashboardPage.tsx` | Two-column layout: faceplate rail on the left at `lg`+, card strip + trend in a right column. |
| `src/features/dashboard/Faceplate.tsx` | `gap-3`→`gap-2`, `p-3`→`p-2`, `lg:border-l`→`lg:border-r`, `lg:order-first`. |
| `src/app/AppShell.tsx` | Palette removed; `<Settings>` icon; wordmark → `/`. |
| `src/app/routes.tsx` | `AppRoute.command` / `commandRoutes()` deleted; `/executive` gains a nav entry. |
| `src/features/dashboard/LoopCard.tsx` | `<SlidersHorizontal>` icon. |
| `src/features/multitrend/useMultiTrendModel.ts` | `useMultiTrendModel(roster)`, lazy init from storage, persist effect, one-shot roster reconciliation. |
| `src/features/multitrend/SeriesSelector.tsx` | New required `loopLabel` prop drives the visible row text; checkbox `aria-label` untouched. |
| `src/pages/MultiTrendPage.tsx` | `useControllers()` id→name lookup, cell headers, roster passed to the model. |
| `package.json` | `cmdk` dependency dropped. |
| `TEST_E2E.md` | E2E-006 repurposed, E2E-036 restated, E2E-049 strengthened. |

**Deleted**

- `src/components/Command.tsx`
- `src/components/Command.test.tsx`

---

### Task 1: Move the AI configuration form into the loop config dialog

Implements spec §5. `AiPanel` keeps lifecycle, log and tuning-apply; the six configuration
fields plus their save move into `LoopConfigDialog`'s single draft/save/blocked flow.

**Files:**
- Create: `packages/smart_pid_web/src/features/loop-config/AiConfigSection.tsx`
- Modify: `packages/smart_pid_web/src/features/loop-config/LoopConfigDialog.tsx:1-42`, `:197-252`, `:261-322`, `:555-565`, `:656`
- Modify: `packages/smart_pid_web/src/features/loop-config/AiPanel.tsx:1-34`, `:86-143`, `:201-328`
- Test: `packages/smart_pid_web/src/features/loop-config/__tests__/LoopConfigDialog.test.tsx`
- Test: `packages/smart_pid_web/src/features/loop-config/__tests__/AiPanel.test.tsx:238-257`

**Interfaces:**
- Consumes: `validateAiConfig(ai: AiConfigForm): FieldErrors` and `hasErrors(errors: FieldErrors): boolean` from `./validation`; `AI_ENGINES`, `OBJECTIVES`, `PROCESS_SPEEDS` and the types `AiEngine`, `ControlObjective`, `ProcessSpeed`, `FieldErrors` from `./types`; `Field`, `Input` from `@/components/Field`.
- Produces:
  - `export interface AiSectionForm { engine: AiEngine; objective: ControlObjective; speed: ProcessSpeed; dead_time_l: number; limit_min: number; limit_max: number }`
  - `export interface AiConfigSectionProps { value: AiSectionForm; errors: FieldErrors; disabled: boolean; onChange(patch: Partial<AiSectionForm>): void }`
  - `export function AiConfigSection(props: AiConfigSectionProps): JSX.Element`
  - `LoopConfigDialog`'s `Draft` type gains `process_speed: ProcessSpeed` and `ai: { engine: AiEngine; objective: ControlObjective; dead_time_l: number; limit_min: number; limit_max: number }`.

- [ ] **Step 1: Write the failing test for the AI section living in the dialog**

Append to `packages/smart_pid_web/src/features/loop-config/__tests__/LoopConfigDialog.test.tsx`:

```tsx
describe('LoopConfigDialog — AI Optimization section', () => {
  it('offers the three engines and the guardrail band', async () => {
    renderDialog();
    const engine = await screen.findByLabelText('Motor');
    expect(within(engine).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'NONE',
      'FUZZY',
      'RL',
    ]);
    expect(screen.getByLabelText('Tempo morto L')).toBeInTheDocument();
    expect(screen.getByLabelText('Limite mín.')).toBeInTheDocument();
    expect(screen.getByLabelText('Limite máx.')).toBeInTheDocument();
    expect(screen.getByLabelText('Velocidade do processo')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'AI Optimization' })).toBeVisible();
  });

  it('has no second save button of its own', async () => {
    renderDialog();
    await screen.findByLabelText('Motor');
    expect(screen.queryByRole('button', { name: 'Salvar IA' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Salvar' })).toHaveLength(1);
  });

  it('refuses to save an inverted guardrail band', async () => {
    renderDialog({ ai_config: { dead_time_l: 1, engine: 'FUZZY', limit_max: 100, limit_min: 0.1 } });
    fireEvent.change(await screen.findByLabelText('Limite mín.'), { target: { value: '500' } });
    expect(await screen.findByText('Limite mínimo deve ser menor que o máximo')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('disables the AI fields for a read-only user', async () => {
    renderDialog({}, 'user');
    expect(await screen.findByLabelText('Motor')).toBeDisabled();
    expect(screen.getByLabelText('Objetivo')).toBeDisabled();
    expect(screen.getByLabelText('Velocidade do processo')).toBeDisabled();
    expect(screen.getByLabelText('Tempo morto L')).toBeDisabled();
    expect(screen.getByLabelText('Limite mín.')).toBeDisabled();
    expect(screen.getByLabelText('Limite máx.')).toBeDisabled();
  });

  it('sends ai_config and process_speed in the single PATCH', async () => {
    const { onClose } = renderDialog();
    fireEvent.change(await screen.findByLabelText('Motor'), { target: { value: 'FUZZY' } });
    fireEvent.change(screen.getByLabelText('Objetivo'), { target: { value: 'SP_TRACKING' } });
    fireEvent.change(screen.getByLabelText('Velocidade do processo'), { target: { value: 'FAST' } });
    fireEvent.change(screen.getByLabelText('Tempo morto L'), { target: { value: '4' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(fetchMock.mock.calls).toHaveLength(1);
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string) as {
      process_speed: string;
      ai_config: Record<string, unknown>;
    };
    expect(body.process_speed).toBe('FAST');
    expect(body.ai_config).toEqual({
      engine: 'FUZZY',
      objective: 'SP_TRACKING',
      dead_time_l: 4,
      limit_min: 0.1,
      limit_max: 100,
    });
  });
});
```

- [ ] **Step 2: Run the new tests and watch them fail**

Run: `cd packages/smart_pid_web && npx vitest run src/features/loop-config/__tests__/LoopConfigDialog.test.tsx -t "AI Optimization"`
Expected: FAIL — 5 failing tests, the first reporting `TestingLibraryElementError: Unable to find a label with the text of: Motor`.

- [ ] **Step 3: Create the AI configuration section component**

Create `packages/smart_pid_web/src/features/loop-config/AiConfigSection.tsx`:

```tsx
import { useId } from 'react';
import { Field, Input } from '@/components/Field';
import { cn } from '@/lib/utils';
import {
  AI_ENGINES,
  OBJECTIVES,
  PROCESS_SPEEDS,
  type AiEngine,
  type ControlObjective,
  type FieldErrors,
  type ProcessSpeed,
} from './types';

/**
 * The optimizer's configuration surface (§5). It lives in the loop config
 * dialog rather than the faceplate: configuration belongs where configuration
 * already is, and the 417 px it used to occupy is what made the rail scroll.
 *
 * Presentational on purpose — the dialog owns the draft, the validation and the
 * single PATCH, so there is exactly one save button for one write.
 */

export interface AiSectionForm {
  engine: AiEngine;
  objective: ControlObjective;
  speed: ProcessSpeed;
  dead_time_l: number;
  limit_min: number;
  limit_max: number;
}

export interface AiConfigSectionProps {
  value: AiSectionForm;
  errors: FieldErrors;
  disabled: boolean;
  onChange(patch: Partial<AiSectionForm>): void;
}

const SELECT_CLASS = cn(
  'numeric min-h-11 w-full rounded-control border border-rule-strong bg-surface-sunk px-3 py-2',
  'text-sm text-text outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
  'disabled:cursor-not-allowed disabled:text-text-disabled',
);

export function AiConfigSection({ value, errors, disabled, onChange }: AiConfigSectionProps) {
  const engineId = useId();
  const objectiveId = useId();
  const speedId = useId();
  const deadTimeId = useId();
  const limitMinId = useId();
  const limitMaxId = useId();

  return (
    <>
      <Field label="Motor" htmlFor={engineId}>
        <select
          id={engineId}
          className={SELECT_CLASS}
          value={value.engine}
          disabled={disabled}
          onChange={(e) => onChange({ engine: e.target.value as AiEngine })}
        >
          {AI_ENGINES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Objetivo" htmlFor={objectiveId}>
        <select
          id={objectiveId}
          className={SELECT_CLASS}
          value={value.objective}
          disabled={disabled}
          onChange={(e) => onChange({ objective: e.target.value as ControlObjective })}
        >
          {OBJECTIVES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Velocidade do processo" htmlFor={speedId}>
        <select
          id={speedId}
          className={SELECT_CLASS}
          value={value.speed}
          disabled={disabled}
          onChange={(e) => onChange({ speed: e.target.value as ProcessSpeed })}
        >
          {PROCESS_SPEEDS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Tempo morto L" htmlFor={deadTimeId} error={errors.dead_time_l}>
        <Input
          id={deadTimeId}
          type="number"
          inputMode="decimal"
          className="numeric"
          value={value.dead_time_l}
          disabled={disabled}
          invalid={errors.dead_time_l !== undefined}
          onChange={(e) => onChange({ dead_time_l: Number(e.target.value) })}
        />
      </Field>

      <Field label="Limite mín." htmlFor={limitMinId} error={errors.limit_min}>
        <Input
          id={limitMinId}
          type="number"
          inputMode="decimal"
          className="numeric"
          value={value.limit_min}
          disabled={disabled}
          invalid={errors.limit_min !== undefined}
          onChange={(e) => onChange({ limit_min: Number(e.target.value) })}
        />
      </Field>

      <Field label="Limite máx." htmlFor={limitMaxId} error={errors.limit_max}>
        <Input
          id={limitMaxId}
          type="number"
          inputMode="decimal"
          className="numeric"
          value={value.limit_max}
          disabled={disabled}
          invalid={errors.limit_max !== undefined}
          onChange={(e) => onChange({ limit_max: Number(e.target.value) })}
        />
      </Field>
    </>
  );
}
```

- [ ] **Step 4: Extend the dialog's imports and Draft type**

In `packages/smart_pid_web/src/features/loop-config/LoopConfigDialog.tsx`, replace the
`./types` import block at lines 21-29 with:

```tsx
import {
  EXECUTION_MODES,
  INTEGRAL_TYPES,
  PID_STRUCTURES,
  SHED_OPTIONS,
  type AiEngine,
  type ControlObjective,
  type ExecutionMode,
  type LimitsForm,
  type PidParamsForm,
  type ProcessSpeed,
} from './types';
```

Replace the `./validation` import at line 35 with:

```tsx
import { hasErrors, validateAiConfig, validateLimits, validatePidParams } from './validation';
```

Add immediately after the `./TagPicker` import block (currently ending at line 42):

```tsx
import { AiConfigSection } from './AiConfigSection';
```

Replace the `Draft` type at lines 197-213 with:

```tsx
type Draft = {
  name: string;
  description: string;
  execution_mode: ExecutionMode;
  scan_rate_s: number;
  pid: PidParamsForm;
  limits: LimitsForm;
  pv_scale: ScaleConfigDto;
  bindings: Pick<TagBindingsDto, 'node_id_pv' | 'node_id_sp' | 'node_id_co' | 'node_id_ti'>;
  pid_structure: string;
  integral_type: string;
  shed_opt: string;
  shed_time_s: number;
  max_tuning_change_pct: number;
  low_cut: number;
  ff_gain: number;
  process_speed: ProcessSpeed;
  ai: {
    engine: AiEngine;
    objective: ControlObjective;
    dead_time_l: number;
    limit_min: number;
    limit_max: number;
  };
};
```

- [ ] **Step 5: Default the new draft fields in `toDraft`**

In the same file, add `AiConfigDto` to the `@/api/types` import block at lines 14-19 so it
reads:

```tsx
import type {
  AiConfigDto,
  ControllerResponse,
  OpcuaNode,
  ScaleConfigDto,
  TagBindingsDto,
} from '@/api/types';
```

Then inside `toDraft` (lines 215-252), add one local next to the existing `pid` / `pv` / `tags`
locals — the same `Partial` narrowing `AiPanel` uses today, because a roster row may predate
`ai_config`:

```tsx
  const ai = c.ai_config as Partial<AiConfigDto> | undefined;
```

and insert these two properties immediately after `ff_gain: c.ff_gain ?? 1,` and before the
closing `};`:

```tsx
    process_speed: (c.process_speed as ProcessSpeed | undefined) ?? 'MEDIUM',
    ai: {
      engine: (ai?.engine as AiEngine | undefined) ?? 'NONE',
      objective: (ai?.objective as ControlObjective | undefined) ?? 'DISTURBANCE_REJECTION',
      dead_time_l: ai?.dead_time_l ?? 1,
      limit_min: ai?.limit_min ?? 0.1,
      limit_max: ai?.limit_max ?? 100,
    },
```

- [ ] **Step 6: Extend `blocked` and `save()`**

In `LoopConfigDialog`, replace lines 273-275 with:

```tsx
  const pidErrors = isDdc ? validatePidParams(draft.pid) : {};
  const limitErrors = isDdc ? validateLimits(draft.limits) : {};
  const aiErrors = validateAiConfig({
    engine: draft.ai.engine,
    dead_time_l: draft.ai.dead_time_l,
    limit_min: draft.ai.limit_min,
    limit_max: draft.ai.limit_max,
  });
  const blocked =
    hasErrors(pidErrors) ||
    hasErrors(limitErrors) ||
    hasErrors(aiErrors) ||
    draft.name.trim() === '';
```

In `save()`, insert these two properties immediately after
`tag_bindings: { ...controller.tag_bindings, ...draft.bindings },` (line 303) and before the
`...(isDdc` spread:

```tsx
          process_speed: draft.process_speed,
          ai_config: {
            engine: draft.ai.engine,
            objective: draft.ai.objective,
            dead_time_l: draft.ai.dead_time_l,
            limit_min: draft.ai.limit_min,
            limit_max: draft.ai.limit_max,
          },
```

- [ ] **Step 7: Mount the section after the DDC block**

In the same file, immediately after the `{isDdc ? ( … ) : null}` block closes (line 565) and
before the `{update.error !== null ? (` block, insert:

```tsx
        {/* Not DDC-gated: these fields are what SETS the optimizer state, and
            the optimizer runs for a SUPERVISORY loop too. */}
        <Section label="AI Optimization">
          <AiConfigSection
            value={{ ...draft.ai, speed: draft.process_speed }}
            errors={aiErrors}
            disabled={readOnly}
            onChange={(patch) =>
              setDraft((p) => {
                const { speed, ...ai } = patch;
                return {
                  ...p,
                  process_speed: speed ?? p.process_speed,
                  ai: { ...p.ai, ...ai },
                };
              })
            }
          />
        </Section>
```

- [ ] **Step 8: Run the dialog tests and watch them pass**

Run: `cd packages/smart_pid_web && npx vitest run src/features/loop-config/__tests__/LoopConfigDialog.test.tsx`
Expected: PASS — every test in the file green, including the five new `AI Optimization` cases.

- [ ] **Step 9: Delete the moved block from `AiPanel`**

In `packages/smart_pid_web/src/features/loop-config/AiPanel.tsx`, delete lines 201-328 in
full — the entire `{canTune ? ( <div className="flex flex-col gap-2"> … </div> ) : null}`
expression that holds `Motor`, `Objetivo`, `Velocidade do processo`, `Tempo morto L`,
`Limite mín.`, `Limite máx.`, the `Salvar IA` button and the `updateController.error` alert.
Leave the `{canControl ? (` lifecycle group that follows it untouched.

- [ ] **Step 10: Strip the now-dead imports and state from `AiPanel`**

Replace lines 1-34 of `AiPanel.tsx` with:

```tsx
import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/api/queryKeys';
import { useCan } from '@/auth/useCan';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import { toast } from '@/components/Toast';
import type { AiStatus } from '@/api/types';
import type { AiData } from '@/lib/envelope';
import { useRealtime } from '@/realtime/useRealtime';
import { ConfirmApplyTuningDialog } from './ConfirmApplyTuningDialog';
import { applyTuning, type AiAction } from './commandApi';
import { tuningRecommendationKey, useAiAction, useAiStatus, useTuningRecommendation } from './useAiControls';

export interface AiPanelProps {
  controllerId: number;
  tag: string;
}
```

Delete `SELECT_CLASS` entirely — lines 67-71 of the original file, the
`const SELECT_CLASS = cn( … );` declaration.

- [ ] **Step 11: Strip the dead form state from the `AiPanel` body**

In `AiPanel`, delete these lines from the original body:

- lines 92 (`const controllers = useControllers();`)
- lines 100-105 (the six `useId()` declarations: `engineId`, `objectiveId`, `speedId`, `deadTimeId`, `limitMinId`, `limitMaxId`)
- line 96 (`const updateController = useUpdateControllerMutation();`)
- line 109 and its comment at 107-108 (`const [draft, setDraft] = useState<Partial<AiForm>>({});`)
- lines 131-143 (the `// Schema defaults …` comment through `const errors = validateAiConfig(form);`)

Then re-add the two lines the surviving body still needs, in place of the deleted 131-143 block:

```tsx
  const rec = recommendation.data;
  const pendingRecommendation = rec !== undefined && rec.status === 'pending';
```

- [ ] **Step 12: Run the AiPanel suite and read the two expected failures**

Run: `cd packages/smart_pid_web && npx vitest run src/features/loop-config/__tests__/AiPanel.test.tsx`
Expected: FAIL — exactly two failures:
`AiPanel > offers the three engines and the guardrail band` with `Unable to find a label with the text of: Motor`, and
`AiPanel > refuses to save an inverted guardrail band` with `Unable to find a label with the text of: Limite mín.`.

- [ ] **Step 13: Delete the two moved cases from the AiPanel suite**

In `packages/smart_pid_web/src/features/loop-config/__tests__/AiPanel.test.tsx`, delete lines
238-257 — the two `it('offers the three engines and the guardrail band', …)` and
`it('refuses to save an inverted guardrail band', …)` blocks. Keep the closing `});` of the
`describe('AiPanel', …)`.

Then remove `within` from the `@testing-library/react` import on line 1 if no other case in the
file uses it. Confirm first:

Run: `cd packages/smart_pid_web && grep -c "within(" src/features/loop-config/__tests__/AiPanel.test.tsx`
If the count is `1` (the import alone), line 1 becomes:

```tsx
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
```

- [ ] **Step 14: Run both suites and watch them pass**

Run: `cd packages/smart_pid_web && npx vitest run src/features/loop-config`
Expected: PASS — every file under `src/features/loop-config` green.

- [ ] **Step 15: Update the `NewLoopDialog` copy that names `[cfg]`**

In `LoopConfigDialog.tsx`, line 656 currently reads:

```tsx
            O restante da configuração fica disponível no [cfg] da malha criada.
```

Replace it with:

```tsx
            O restante da configuração fica disponível em Configurar na malha criada.
```

- [ ] **Step 16: Typecheck and lint**

Run: `npm --prefix packages/smart_pid_web run typecheck && npm --prefix packages/smart_pid_web run lint`
Expected: both exit 0, no output beyond the `tsc -b` / `eslint .` invocations.

- [ ] **Step 17: Commit**

```bash
git add packages/smart_pid_web/src/features/loop-config/AiConfigSection.tsx packages/smart_pid_web/src/features/loop-config/LoopConfigDialog.tsx packages/smart_pid_web/src/features/loop-config/AiPanel.tsx packages/smart_pid_web/src/features/loop-config/__tests__/LoopConfigDialog.test.tsx packages/smart_pid_web/src/features/loop-config/__tests__/AiPanel.test.tsx
git commit -m "refactor(web): move AI configuration into the loop config dialog"
```

---

### Task 2: Faceplate as a full-height left rail

Implements spec §4. Depends on Task 1: the height budget only closes once the ~417 px
configuration form has left the rail.

**Files:**
- Modify: `packages/smart_pid_web/src/pages/DashboardPage.tsx:87-158`
- Modify: `packages/smart_pid_web/src/features/dashboard/Faceplate.tsx:86-89`
- Modify: `packages/smart_pid_web/src/features/loop-config/AiPanel.tsx` (panel root class, action row, log box class)
- Test: `packages/smart_pid_web/e2e/responsive.spec.ts:32-42`, `:101-113`

**Interfaces:**
- Consumes: `AiConfigSection` is already extracted (Task 1); `Faceplate` keeps its existing `FaceplateProps` signature `{ controllerId: number; tag: string; description?: string; scale: Scale; decimals?: number; spRange?: Range }` unchanged.
- Produces: no new exported symbol. The DOM contract other tasks and specs bind to: `aside[aria-label="Faceplate {tag}"]` is the first flex item of `div[data-testid="dashboard-detail"]` at `lg`+, and `section[aria-label="Malhas"]` plus `section[aria-label="Painel de tendência {tag}"]` share a right-hand column.

- [ ] **Step 1: Write the failing rail-geometry test**

In `packages/smart_pid_web/e2e/responsive.spec.ts`, replace the whole
`test('trend and faceplate split at >=1024 and stack below it', …)` block (lines 32-42) with:

```ts
  test('faceplate is the left rail at >=1024 and stacks under the trend below it', async ({
    page,
  }) => {
    await gotoDashboard(page, { loops: LOOPS, width: 1280, height: 900 });
    let t = await box(trend(page));
    let fp = await box(faceplate(page, 'FIC-101'));
    expect(fp.x + fp.width, 'faceplate sits to the left of the trend').toBeLessThan(t.x + 1);

    await page.setViewportSize({ width: 900, height: 900 });
    t = await box(trend(page));
    fp = await box(faceplate(page, 'FIC-101'));
    expect(fp.y, 'faceplate stacks under the trend').toBeGreaterThanOrEqual(t.y + t.height - 1);
  });

  test('the faceplate rail never scrolls at any supported desktop viewport', async ({ page }) => {
    const sizes = [
      { width: 1920, height: 1080 },
      { width: 1600, height: 900 },
      { width: 1440, height: 900 },
      { width: 1024, height: 768 },
    ];
    for (const role of ['admin', 'user'] as const) {
      for (const { width, height } of sizes) {
        await gotoDashboard(page, { loops: LOOPS, width, height, role });
        const railOverflow = await faceplate(page, 'FIC-101').evaluate(
          (el) => el.scrollHeight - el.clientHeight,
        );
        expect(railOverflow, `rail scroll at ${role} ${width}x${height}`).toBeLessThanOrEqual(0);

        const pageOverflow = await page.evaluate(
          () => document.documentElement.scrollHeight - document.documentElement.clientHeight,
        );
        expect(pageOverflow, `page scroll at ${role} ${width}x${height}`).toBeLessThanOrEqual(0);
      }
    }
  });
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd packages/smart_pid_web && env -u CI npx playwright test e2e/responsive.spec.ts -g "faceplate is the left rail"`
Expected: FAIL with `Error: faceplate sits to the left of the trend` — the received value is the current right-hand `x + width`, which exceeds the trend's `x`.

- [ ] **Step 3: Restructure `DashboardPage` into two columns**

In `packages/smart_pid_web/src/pages/DashboardPage.tsx`, replace lines 92-158 — the
`<section aria-label="Malhas">` band through the closing `</div>` of `dashboard-detail` — with:

```tsx
      <div
        data-testid="dashboard-detail"
        className="flex min-h-0 flex-1 flex-col overflow-y-auto lg:flex-row lg:overflow-hidden"
      >
        {/* Right-hand column in DOM order so the stacked (<1024) reading order
            stays cards → trend → faceplate; `lg:order-first` on the rail is what
            puts the faceplate on the left once the row exists. */}
        <div className="flex min-w-0 flex-col max-lg:shrink-0 lg:min-h-0 lg:flex-1 lg:overflow-hidden">
          <section
            aria-label="Malhas"
            className={cn(
              'relative shrink-0 border-b border-rule',
              'after:pointer-events-none after:absolute after:inset-y-0 after:right-0 after:w-8',
              'after:bg-[linear-gradient(to_right,transparent,var(--bg))]',
            )}
          >
            {newLoopButton !== null ? (
              <div className="flex justify-end px-3 pt-2">{newLoopButton}</div>
            ) : null}
            <ul className="flex flex-nowrap gap-3 overflow-x-auto p-3">
              {controllers.data.map((controller) => {
                const status = statuses.get(controller.id) ?? null;
                const selectedHere = controller.id === selected.id;
                return (
                  <li
                    key={controller.id}
                    className={cn('flex', selectedHere && 'outline outline-2 outline-focus-ring')}
                  >
                    <LoopCard
                      controller={controller}
                      status={status}
                      onOpenConfig={setConfigId}
                      stale={stale}
                      controlsSlot={
                        <div className="flex flex-col gap-2">
                          <Button
                            variant="secondary"
                            size="sm"
                            aria-label={`Abrir ${controller.name}`}
                            aria-pressed={selectedHere}
                            onClick={() => setSelectedId(controller.id)}
                          >
                            Abrir
                          </Button>
                          {/* Only the open loop carries the mode switch: the strip
                              must not offer the same command on every card. */}
                          {selectedHere ? (
                            <CardControls
                              controllerId={controller.id}
                              mode={status?.mode ?? controller.mode}
                              controls={['mode']}
                            />
                          ) : null}
                        </div>
                      }
                    />
                  </li>
                );
              })}
            </ul>
          </section>

          <TrendPanel controllerId={selected.id} scale={pvScale(selected)} />
        </div>

        <Faceplate
          controllerId={selected.id}
          tag={selected.name}
          description={selected.description}
          scale={pvScale(selected)}
          spRange={{ min: selected.sp_lo_lim, max: selected.sp_hi_lim }}
        />
      </div>
```

- [ ] **Step 4: Update the `DashboardPage` layout doc comment**

In the same file, replace the doc comment at lines 22-25:

```tsx
 * Layout contract: a single non-wrapping card strip on top — wrapping would
 * push the trend below the fold — then trend + ~320 px faceplate side by side
 * at ≥1024 (trend keeps ≥65% at 1440) and stacked below it, over a persistent
 * alarm footer that collapses to a count chip under 768.
```

with:

```tsx
 * Layout contract (§4): at ≥1024 the page is two columns — a full-height
 * ~320 px faceplate rail on the left, the non-wrapping card strip and the trend
 * stacked in the right column (trend keeps ≥65% at 1440). Below 1024 the three
 * bands stack in DOM order (cards, trend, faceplate) and the page scrolls. The
 * simulation banner and the alarm footer stay full width: they are page-level
 * bands, not loop detail. The alarm footer collapses to a count chip under 768.
```

- [ ] **Step 5: Apply the three static compaction levers to `Faceplate`**

In `packages/smart_pid_web/src/features/dashboard/Faceplate.tsx`, replace line 88:

```tsx
      className="flex w-full shrink-0 flex-col gap-3 border-rule bg-surface p-3 lg:w-80 lg:overflow-y-auto lg:border-l"
```

with:

```tsx
      className="flex w-full shrink-0 flex-col gap-2 border-rule bg-surface p-2 lg:order-first lg:w-80 lg:overflow-y-auto lg:border-r"
```

That is three of the four §4.3 levers: `gap-3`→`gap-2` (24 px over 6 gaps), `p-3`→`p-2` (8 px),
and the rail moving to the left edge (`lg:border-l`→`lg:border-r`, plus `lg:order-first`).

- [ ] **Step 6: Make the AI panel the elastic child and merge its two action rows**

In `packages/smart_pid_web/src/features/loop-config/AiPanel.tsx`, replace the panel root
`className` (originally line 178) with:

```tsx
      className="flex min-h-0 flex-1 flex-col gap-2 border-t border-rule pt-3"
```

Then replace the two separate action blocks — the `{canControl ? ( … ) : null}` lifecycle group
and the `{canTune ? ( <Button … >Apply tuning</Button> ) : null}` block that sits after the log
box — with a single row placed where the lifecycle group is today (immediately after the
`</header>`), and delete the standalone `Apply tuning` block:

```tsx
      {/* One row, not two: the second row cost 52 px of a rail that must not
          scroll (§4.3). Every button keeps the Button base min-h-11 floor. */}
      {canControl || canTune ? (
        <div className="flex gap-2">
          {canControl ? (
            <div role="group" aria-label="Ciclo do otimizador" className="flex flex-1 gap-2">
              {AI_ACTIONS.map(({ action, label }) => (
                <Button
                  key={action}
                  size="sm"
                  className="flex-1"
                  disabled={aiAction.isPending}
                  onClick={() =>
                    aiAction.mutate(
                      { id: controllerId, action },
                      {
                        onError: () =>
                          toast({
                            title: 'Comando de IA recusado',
                            description: `Malha ${tag}`,
                            tone: 'crit',
                          }),
                      },
                    )
                  }
                >
                  {label}
                </Button>
              ))}
            </div>
          ) : null}
          {canTune ? (
            <Button
              variant="secondary"
              size="sm"
              className="flex-1"
              disabled={!pendingRecommendation}
              onClick={() => {
                setApplyError(undefined);
                setConfirmOpen(true);
              }}
            >
              Apply tuning
            </Button>
          ) : null}
        </div>
      ) : null}
```

- [ ] **Step 7: Turn the LOG.AI box into the flexible element with a 32 px floor**

In the same file, replace the log box `className` (originally line 363):

```tsx
        className="numeric max-h-32 overflow-y-auto rounded-control bg-surface-sunk p-2 text-2xs text-text-soft"
```

with:

```tsx
        className={cn(
          'numeric min-h-8 flex-1 overflow-y-auto rounded-control bg-surface-sunk p-2',
          // Stacked (<1024) the rail has no bounded height, so the log needs its
          // own cap or 100 buffered lines would push the page open.
          'max-lg:max-h-32 text-2xs text-text-soft',
        )}
```

`min-h-8` is the 32 px floor §4.3 derives (580 + 32 = 612 ≤ 614 at 1024×768 with the twin
banner). Re-add `cn` to the `@/lib/utils` import at the top of `AiPanel.tsx`:

```tsx
import { cn } from '@/lib/utils';
```

- [ ] **Step 8: Replace the `Comandos` target assertion in the responsive suite**

`Comandos` is deleted by Task 3, but this task already re-runs the suite. In
`packages/smart_pid_web/e2e/responsive.spec.ts` line 105, replace:

```ts
    await assertMinTarget(page.getByRole('button', { name: 'Comandos' }), TARGET_MIN);
```

with:

```ts
    await assertMinTarget(page.getByRole('button', { name: 'Configurações' }), TARGET_MIN);
```

- [ ] **Step 9: Run the responsive suite and watch it pass**

Run: `cd packages/smart_pid_web && env -u CI npx playwright test e2e/responsive.spec.ts`
Expected: PASS — 7 passed, including `faceplate is the left rail at >=1024 and stacks below it`
and all 8 role×viewport combinations of `the faceplate rail never scrolls at any supported
desktop viewport`.

- [ ] **Step 10: Run the Vitest suite for the touched features**

Run: `cd packages/smart_pid_web && npx vitest run src/features/dashboard src/features/loop-config src/pages`
Expected: PASS — all files green. `Faceplate.test.tsx` in particular asserts none of the moved
field labels and must not need an edit.

- [ ] **Step 11: Typecheck and lint**

Run: `npm --prefix packages/smart_pid_web run typecheck && npm --prefix packages/smart_pid_web run lint`
Expected: both exit 0.

- [ ] **Step 12: Commit**

```bash
git add packages/smart_pid_web/src/pages/DashboardPage.tsx packages/smart_pid_web/src/features/dashboard/Faceplate.tsx packages/smart_pid_web/src/features/loop-config/AiPanel.tsx packages/smart_pid_web/e2e/responsive.spec.ts
git commit -m "feat(web): make the faceplate a full-height non-scrolling left rail"
```

---

### Task 3: Remove the command palette

Implements spec §6. `k` as a bare shortcut over a live process is hostile, and with §8 the
palette reaches no destination the visible chrome does not.

**Files:**
- Modify: `packages/smart_pid_web/src/app/AppShell.tsx:1-47`, `:51-76`, `:107-117`, `:166-182`
- Modify: `packages/smart_pid_web/src/app/routes.tsx:30-45`, `:47-111`, `:113-139`
- Modify: `packages/smart_pid_web/package.json:26`
- Delete: `packages/smart_pid_web/src/components/Command.tsx`
- Delete: `packages/smart_pid_web/src/components/Command.test.tsx`
- Test: `packages/smart_pid_web/src/app/AppShell.test.tsx:7`, `:46-66`, `:72`, `:85-107`
- Test: `packages/smart_pid_web/e2e/login-dashboard.spec.ts:37-57`
- Test: `packages/smart_pid_web/e2e/target-size.spec.ts:19`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `AppRoute` narrows to `{ path: string; element: ComponentType; adminOnly?: boolean; nav?: { label: string; order: number }; cfg?: { label: string; order: number } }`. `routes.tsx` exports exactly two projections after this task: `navRoutes(routes?: readonly AppRoute[]): WithNav[]` and `cfgRoutes(routes?: readonly AppRoute[]): WithCfg[]`. `commandRoutes` no longer exists.

- [ ] **Step 1: Write the failing test that the palette is gone**

In `packages/smart_pid_web/src/app/AppShell.test.tsx`, replace the whole
`describe('appRoutes registry', …)` block (lines 46-66) with:

```tsx
describe('appRoutes registry', () => {
  it('registers the dashboard as the nav-visible root route', () => {
    const root = appRoutes.find((r) => r.path === '/');
    expect(root).toBeDefined();
    expect(root?.nav).toEqual({ label: 'Loops', order: 10 });
  });

  it('sorts nav and cfg projections by order', () => {
    const routes = [
      { path: '/b', element: () => null, nav: { label: 'B', order: 20 } },
      { path: '/a', element: () => null, nav: { label: 'A', order: 10 } },
      { path: '/c', element: () => null, cfg: { label: 'C', order: 30 } },
      { path: '/d', element: () => null, cfg: { label: 'D', order: 5 } },
    ];
    expect(navRoutes(routes).map((r) => r.nav.label)).toEqual(['A', 'B']);
    expect(cfgRoutes(routes).map((r) => r.cfg.label)).toEqual(['D', 'C']);
  });

  it('carries no command-palette metadata on any route', () => {
    for (const route of appRoutes) {
      expect(route).not.toHaveProperty('command');
    }
  });
});
```

Replace the import on line 7 with:

```tsx
import { appRoutes, cfgRoutes, navRoutes } from './routes';
```

Delete lines 85-107 — the three palette cases `opens the command palette with the bare k key`,
`ignores k typed inside an editable field` and `ignores k when it carries a modifier`.

Replace line 72 with:

```tsx
    expect(screen.queryByRole('button', { name: 'Comandos' })).not.toBeInTheDocument();
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd packages/smart_pid_web && npx vitest run src/app/AppShell.test.tsx`
Expected: FAIL — `AppShell > renders registry-backed top navigation and logout` fails with
`expect(element).not.toBeInTheDocument()` (the `Comandos` button is still rendered), and
`appRoutes registry > carries no command-palette metadata on any route` fails with
`expected { path: '/', … } not to have property "command"`.

- [ ] **Step 3: Strip the palette out of `routes.tsx`**

In `packages/smart_pid_web/src/app/routes.tsx`, replace lines 30-45 with:

```tsx
/**
 * Single route/navigation registry (§6.9). Every later phase appends ONE
 * literal here — the top bar and the configuration menu are both projections of
 * this array, so nothing has to be wired in two places.
 */
export interface AppRoute {
  path: string;
  element: ComponentType;
  adminOnly?: boolean;
  /** Top-bar entry (`Loops · Trends · Alarms · Sim · Executivo`). */
  nav?: { label: string; order: number };
  /** Configuration-menu entry (Projects, Settings, Connection, Users). */
  cfg?: { label: string; order: number };
}
```

Replace lines 47-111 with:

```tsx
export const appRoutes: AppRoute[] = [
  {
    path: '/',
    element: DashboardPage,
    nav: { label: 'Loops', order: 10 },
  },
  {
    path: '/multitrend',
    element: MultiTrendPage,
    nav: { label: 'Trends', order: 20 },
  },
  {
    path: '/alarms',
    element: AlarmsPage,
    nav: { label: 'Alarms', order: 30 },
  },
  {
    path: '/simulator',
    element: SimulatorPage,
    nav: { label: 'Sim', order: 40 },
  },
  {
    path: '/executive',
    element: ExecutiveDashboardPage,
  },
  // The configuration-menu administration group. Every entry is `adminOnly`:
  // the routers behind them are `require_admin`, so a `user` who reached one
  // would only collect 403s. RouteGuard sends them back to the dashboard and
  // AppShell drops the menu entries entirely.
  {
    path: '/projects',
    element: ProjectsPage,
    adminOnly: true,
    cfg: { label: 'Projects', order: 10 },
  },
  {
    path: '/settings',
    element: SettingsPage,
    adminOnly: true,
    cfg: { label: 'Settings', order: 20 },
  },
  {
    path: '/connection',
    element: ConnectionPage,
    adminOnly: true,
    cfg: { label: 'Connection', order: 30 },
  },
  {
    path: '/users',
    element: UsersPage,
    adminOnly: true,
    cfg: { label: 'Users', order: 40 },
  },
];
```

Replace lines 113-139 with:

```tsx
type WithNav = AppRoute & { nav: NonNullable<AppRoute['nav']> };
type WithCfg = AppRoute & { cfg: NonNullable<AppRoute['cfg']> };

/** Top-bar entries, ascending `nav.order`. */
export function navRoutes(routes: readonly AppRoute[] = appRoutes): WithNav[] {
  return routes.filter((r): r is WithNav => r.nav !== undefined).sort((a, b) => a.nav.order - b.nav.order);
}

/** Configuration-menu entries, ascending `cfg.order`. */
export function cfgRoutes(routes: readonly AppRoute[] = appRoutes): WithCfg[] {
  return routes.filter((r): r is WithCfg => r.cfg !== undefined).sort((a, b) => a.cfg.order - b.cfg.order);
}
```

Finally, the comment at lines 14-19 mentions the palette. Replace the phrase
``the `[cfg]` menu and the `[k]` palette`` wherever it appears in that block with
``the configuration menu``.

- [ ] **Step 4: Strip the palette out of `AppShell.tsx`**

In `packages/smart_pid_web/src/app/AppShell.tsx`:

Replace lines 1-11 with:

```tsx
import { type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Button } from '@/components/Button';
```

Replace line 26 with:

```tsx
import { appRoutes, cfgRoutes, navRoutes } from './routes';
```

Delete lines 33-39 — the `isEditableTarget` helper and its doc comment.

Replace lines 51-57 with:

```tsx
  // An `adminOnly` route redirects a user back to `/`, so offering it in the
  // configuration menu would only advertise a dead end (phase 10).
  const visible = appRoutes.filter((r) => r.adminOnly !== true || user?.role === 'admin');
  const nav = navRoutes(visible);
  const cfg = cfgRoutes(visible);
```

Delete lines 59-76 — the `useEffect` keydown listener and the `runCommand` callback.

Delete lines 108-117 — the `Comandos` `Button` element in full.

Delete lines 166-182 — the `<CommandDialog> … </CommandDialog>` block in full.

- [ ] **Step 5: Delete the orphaned component and its test**

```bash
rm packages/smart_pid_web/src/components/Command.tsx packages/smart_pid_web/src/components/Command.test.tsx
```

- [ ] **Step 6: Drop the `cmdk` dependency**

In `packages/smart_pid_web/package.json`, delete line 26:

```json
    "cmdk": "^1.1.1",
```

Then refresh the lockfile:

Run: `npm --prefix packages/smart_pid_web install`
Expected: exits 0 and `packages/smart_pid_web/package-lock.json` no longer contains a
`node_modules/cmdk` entry. Verify with
`grep -c '"node_modules/cmdk"' packages/smart_pid_web/package-lock.json` → `0`.

- [ ] **Step 7: Update the two Playwright specs that name `Comandos`**

In `packages/smart_pid_web/e2e/login-dashboard.spec.ts`, replace the whole test at lines 37-57
with:

```ts
test('the shell exposes registry navigation and logout', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Usuário').fill('admin');
  await page.getByLabel('Senha').fill('pw');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.getByText('PIC-005').first()).toBeVisible();

  await expect(page.getByRole('link', { name: 'Loops' })).toHaveAttribute('href', '/');
  await expect(page.getByRole('button', { name: 'Configurações' })).toBeVisible();

  // The palette is gone: a bare `k` over a live process must do nothing.
  await page.getByText('PIC-005').first().click();
  await page.keyboard.press('k');
  await expect(page.getByRole('dialog')).toHaveCount(0);

  await page.getByRole('button', { name: 'Sair' }).click();
  await expect(page).toHaveURL(/\/login/);
});
```

In `packages/smart_pid_web/e2e/target-size.spec.ts`, delete line 19:

```ts
    await assertMinTarget(page.getByRole('button', { name: 'Comandos' }), SPEC_MIN);
```

- [ ] **Step 8: Run the unit suite and watch it pass**

Run: `cd packages/smart_pid_web && npx vitest run src/app`
Expected: PASS — `AppShell.test.tsx` green with the three palette cases gone and the
`carries no command-palette metadata on any route` case passing.

- [ ] **Step 9: Confirm no import of the deleted module survives**

Run: `cd packages/smart_pid_web && grep -rn "cmdk\|components/Command\|commandRoutes\|CommandDialog" src e2e package.json`
Expected: no output (exit status 1).

- [ ] **Step 10: Typecheck, lint and run the affected e2e specs**

Run: `npm --prefix packages/smart_pid_web run typecheck && npm --prefix packages/smart_pid_web run lint`
Expected: both exit 0.

Run: `cd packages/smart_pid_web && env -u CI npx playwright test e2e/login-dashboard.spec.ts e2e/target-size.spec.ts`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add packages/smart_pid_web/src/app/AppShell.tsx packages/smart_pid_web/src/app/routes.tsx packages/smart_pid_web/src/app/AppShell.test.tsx packages/smart_pid_web/src/components/Command.tsx packages/smart_pid_web/src/components/Command.test.tsx packages/smart_pid_web/package.json packages/smart_pid_web/package-lock.json packages/smart_pid_web/e2e/login-dashboard.spec.ts packages/smart_pid_web/e2e/target-size.spec.ts
git commit -m "feat(web): remove the command palette"
```

---

### Task 4: Icons instead of `[cfg]`

Implements spec §7. Two destinations, two glyphs, both accessible names unchanged.

**Files:**
- Modify: `packages/smart_pid_web/src/app/AppShell.tsx` (the `Configurações` dropdown trigger)
- Modify: `packages/smart_pid_web/src/features/dashboard/LoopCard.tsx:106-116`
- Test: `packages/smart_pid_web/src/app/AppShell.test.tsx`
- Test: `packages/smart_pid_web/src/features/dashboard/LoopCard.test.tsx`

**Interfaces:**
- Consumes: `Settings` and `SlidersHorizontal` from `lucide-react` (already a dependency at `^1.21.0`, already imported by `Dialog`, `DropdownMenu`, `Select` and `Toast`). Existing icon convention is `className="h-4 w-4"` with `aria-hidden="true"`.
- Produces: no exported symbol. The button accessible names `Configurações` and `Configurar {tag}` remain exactly as they are — every test locating by role + name stays valid.

- [ ] **Step 1: Write the failing test that no bracketed glyph remains**

Append to `packages/smart_pid_web/src/app/AppShell.test.tsx`, inside the
`describe('AppShell', …)` block:

```tsx
  it('labels the configuration trigger with a gear icon, not a bracketed glyph', () => {
    renderShell();
    const trigger = screen.getByRole('button', { name: 'Configurações' });
    expect(trigger).toHaveTextContent('');
    expect(trigger.querySelector('svg')).not.toBeNull();
    expect(trigger.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });
```

Append to `packages/smart_pid_web/src/features/dashboard/LoopCard.test.tsx`, inside its
top-level `describe`:

```tsx
  it('labels the config button with a slider icon, not a bracketed glyph', () => {
    renderCard();
    const config = screen.getByRole('button', { name: 'Configurar FIC-101' });
    expect(config).toHaveTextContent('');
    expect(config.querySelector('svg')).not.toBeNull();
    expect(config.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });
```

If `LoopCard.test.tsx` has no `renderCard()` helper, use whatever render helper the file
already defines and keep the loop tag matching that helper's controller name.

- [ ] **Step 2: Run both and watch them fail**

Run: `cd packages/smart_pid_web && npx vitest run src/app/AppShell.test.tsx src/features/dashboard/LoopCard.test.tsx -t "bracketed glyph"`
Expected: FAIL — two failures, each `expect(element).toHaveTextContent('')` reporting the
received text content `[cfg]`.

- [ ] **Step 3: Swap the AppShell glyph for `<Settings>`**

In `packages/smart_pid_web/src/app/AppShell.tsx`, add to the import block:

```tsx
import { Settings } from 'lucide-react';
```

Replace the dropdown trigger button body (originally lines 120-124):

```tsx
              <Button variant="ghost" aria-label="Configurações">
                <span aria-hidden="true" className="numeric text-xs">
                  [cfg]
                </span>
              </Button>
```

with:

```tsx
              <Button variant="ghost" aria-label="Configurações">
                <Settings className="h-4 w-4" aria-hidden="true" />
              </Button>
```

- [ ] **Step 4: Swap the LoopCard glyph for `<SlidersHorizontal>`**

In `packages/smart_pid_web/src/features/dashboard/LoopCard.tsx`, add after line 1:

```tsx
import { SlidersHorizontal } from 'lucide-react';
```

Replace lines 106-116:

```tsx
      <Button
        variant="ghost"
        size="sm"
        className="self-end"
        aria-label={`Configurar ${controller.name}`}
        onClick={() => onOpenConfig(controller.id)}
      >
        <span aria-hidden="true" className="numeric text-xs">
          [cfg]
        </span>
      </Button>
```

with:

```tsx
      {/* A distinct glyph from the top bar's gear: both are on screen at once
          and they configure different things (the app vs this loop). */}
      <Button
        variant="ghost"
        size="sm"
        className="self-end"
        aria-label={`Configurar ${controller.name}`}
        onClick={() => onOpenConfig(controller.id)}
      >
        <SlidersHorizontal className="h-4 w-4" aria-hidden="true" />
      </Button>
```

- [ ] **Step 5: Run the two suites and watch them pass**

Run: `cd packages/smart_pid_web && npx vitest run src/app/AppShell.test.tsx src/features/dashboard/LoopCard.test.tsx`
Expected: PASS — both files green, including every existing `Configurações` menu case.

- [ ] **Step 6: Confirm no bracketed glyph is left in the chrome**

Run: `cd packages/smart_pid_web && grep -rn "\[cfg\]" src`
Expected: no output (exit status 1). Task 1 Step 15 already removed the `NewLoopDialog` copy
that named it; if this grep hits `LoopConfigDialog.tsx`, apply that step now.

- [ ] **Step 7: Verify the 44 px floor survives**

Run: `cd packages/smart_pid_web && env -u CI npx playwright test e2e/target-size.spec.ts`
Expected: PASS — `Configurações` and `Configurar FIC-101` both clear 44×44. The floor is a
property of `buttonVariants` (`min-h-11 min-w-11`), not of the glyph.

- [ ] **Step 8: Typecheck, lint and commit**

Run: `npm --prefix packages/smart_pid_web run typecheck && npm --prefix packages/smart_pid_web run lint`
Expected: both exit 0.

```bash
git add packages/smart_pid_web/src/app/AppShell.tsx packages/smart_pid_web/src/app/AppShell.test.tsx packages/smart_pid_web/src/features/dashboard/LoopCard.tsx packages/smart_pid_web/src/features/dashboard/LoopCard.test.tsx
git commit -m "feat(web): replace the [cfg] glyphs with lucide icons"
```

---

### Task 5: Executive dashboard in the top bar

Implements spec §8. The `/executive` route gains a nav entry and the wordmark points at `/`.

**Files:**
- Modify: `packages/smart_pid_web/src/app/routes.tsx` (the `/executive` literal)
- Modify: `packages/smart_pid_web/src/app/AppShell.tsx:82-94`
- Test: `packages/smart_pid_web/src/app/AppShell.test.tsx`

**Interfaces:**
- Consumes: `navRoutes(routes?: readonly AppRoute[]): WithNav[]` and the `AppRoute` shape produced by Task 3 (no `command` member).
- Produces: `appRoutes` entry `{ path: '/executive', element: ExecutiveDashboardPage, nav: { label: 'Executivo', order: 50 } }`. The rendered nav becomes `Loops · Trends · Alarms · Sim · Executivo` for both roles.

- [ ] **Step 1: Write the failing test**

Append to `packages/smart_pid_web/src/app/AppShell.test.tsx`, inside the
`describe('AppShell', …)` block:

```tsx
  it('offers the executive dashboard in the top bar and points the wordmark at the root', () => {
    renderShell();
    const nav = screen.getByRole('navigation', { name: 'Navegação principal' });
    expect(within(nav).getAllByRole('link').map((l) => l.textContent)).toEqual([
      'Loops',
      'Trends',
      'Alarms',
      'Sim',
      'Executivo',
    ]);
    expect(within(nav).getByRole('link', { name: 'Executivo' })).toHaveAttribute(
      'href',
      '/executive',
    );
    expect(screen.getByRole('link', { name: 'Smart PID' })).toHaveAttribute('href', '/');
  });

  it('keeps the executive entry for a user role', async () => {
    renderShellAs('user');
    await waitFor(() => expect(endpoints.me).toHaveBeenCalled());
    const nav = screen.getByRole('navigation', { name: 'Navegação principal' });
    expect(within(nav).getByRole('link', { name: 'Executivo' })).toBeVisible();
  });
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd packages/smart_pid_web && npx vitest run src/app/AppShell.test.tsx -t "executive"`
Expected: FAIL — the first case reports
`expected [ 'Loops', 'Trends', 'Alarms', 'Sim' ] to deeply equal [ 'Loops', 'Trends', 'Alarms', 'Sim', 'Executivo' ]`.

- [ ] **Step 3: Add the nav entry**

In `packages/smart_pid_web/src/app/routes.tsx`, replace the `/executive` literal:

```tsx
  {
    path: '/executive',
    element: ExecutiveDashboardPage,
  },
```

with:

```tsx
  {
    // Last in the bar: Loops is the operator's routine surface, the executive
    // view is consultative. Not `adminOnly` — both roles keep it, as today.
    path: '/executive',
    element: ExecutiveDashboardPage,
    nav: { label: 'Executivo', order: 50 },
  },
```

- [ ] **Step 4: Repoint the wordmark**

In `packages/smart_pid_web/src/app/AppShell.tsx`, replace lines 81-83:

```tsx
        {/* The wordmark is the plant-wide entry point (phase 9 executive view). */}
        <NavLink
          to="/executive"
```

with:

```tsx
        {/* With `Executivo` visible in the nav the wordmark link is redundant as
            a route to it; the brand points at the landing route instead. */}
        <NavLink
          to="/"
```

- [ ] **Step 5: Run the suite and watch it pass**

Run: `cd packages/smart_pid_web && npx vitest run src/app/AppShell.test.tsx`
Expected: PASS — every case green, both new ones included.

- [ ] **Step 6: Measure the 320 px floor**

Run: `cd packages/smart_pid_web && env -u CI npx playwright test e2e/responsive.spec.ts -g "320 keeps monitoring"`
Expected: PASS — the fifth link takes nav `scrollWidth` to 236 px inside the same window while
`overflow-x-auto` absorbs it; the page gains no horizontal scrollbar. Task 9 Step 5 re-measures
this explicitly.

- [ ] **Step 7: Typecheck, lint and commit**

Run: `npm --prefix packages/smart_pid_web run typecheck && npm --prefix packages/smart_pid_web run lint`
Expected: both exit 0.

```bash
git add packages/smart_pid_web/src/app/routes.tsx packages/smart_pid_web/src/app/AppShell.tsx packages/smart_pid_web/src/app/AppShell.test.tsx
git commit -m "feat(web): put the executive dashboard in the top bar"
```

---

### Task 6: Persist the trend selection and reconcile it against the roster

Implements spec §9.1 and §9.2.

**Files:**
- Create: `packages/smart_pid_web/src/features/multitrend/trendSelectionStore.ts`
- Create: `packages/smart_pid_web/src/features/multitrend/trendSelectionStore.test.ts`
- Modify: `packages/smart_pid_web/src/features/multitrend/useMultiTrendModel.ts:1-13`, `:65-80`
- Modify: `packages/smart_pid_web/src/pages/MultiTrendPage.tsx:28`
- Test: `packages/smart_pid_web/src/features/multitrend/useMultiTrendModel.test.tsx:12-18`
- Test: `packages/smart_pid_web/src/realtime/multiLoopFanout.test.tsx:157`

**Interfaces:**
- Consumes: `TrendSlot` (`{ controllerId: number | null; series: Record<Signal, boolean> }`), `freeSlot(): TrendSlot`, `MAX_SLOTS = 4` and `SIGNALS` from `./types`; `UseStatsResult.loops: number[]` and `UseStatsResult.isPending: boolean` from `./useStats`.
- Produces:
  - `export const TREND_SELECTION_KEY = 'spid.multitrend'`
  - `export function readTrendSelection(): TrendSlot[]`
  - `export function writeTrendSelection(slots: readonly TrendSlot[]): void`
  - `export function useMultiTrendModel(roster: readonly number[] | null): MultiTrendModel` — the `MultiTrendModel` return shape is unchanged.

- [ ] **Step 1: Write the failing store test**

Create `packages/smart_pid_web/src/features/multitrend/trendSelectionStore.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { freeSlot, MAX_SLOTS, type TrendSlot } from './types';
import {
  readTrendSelection,
  TREND_SELECTION_KEY,
  writeTrendSelection,
} from './trendSelectionStore';

const occupied = (controllerId: number): TrendSlot => ({
  controllerId,
  series: { pv: true, sp: false, co: true },
});

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe('trendSelectionStore', () => {
  it('falls back to four free slots when nothing is stored', () => {
    expect(readTrendSelection()).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
  });

  it('round-trips a written layout', () => {
    const slots = [occupied(3), freeSlot(), occupied(7), freeSlot()];
    writeTrendSelection(slots);
    expect(readTrendSelection()).toEqual(slots);
  });

  it('writes under the spid.multitrend key and nothing else', () => {
    writeTrendSelection([occupied(1), freeSlot(), freeSlot(), freeSlot()]);
    expect(Object.keys(localStorage)).toEqual([TREND_SELECTION_KEY]);
    expect(TREND_SELECTION_KEY).toBe('spid.multitrend');
  });

  it('discards unparseable storage wholesale', () => {
    localStorage.setItem(TREND_SELECTION_KEY, 'not json {');
    expect(readTrendSelection()).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
  });

  it('discards a payload that is not exactly four slots', () => {
    localStorage.setItem(TREND_SELECTION_KEY, JSON.stringify([occupied(1), occupied(2)]));
    expect(readTrendSelection()).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
    expect(readTrendSelection()).toHaveLength(MAX_SLOTS);
  });

  it('discards a payload whose slot shape is wrong', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: '3', series: { pv: true, sp: true, co: true } },
        freeSlot(),
        freeSlot(),
        freeSlot(),
      ]),
    );
    expect(readTrendSelection()).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
  });

  it('discards a payload with a missing signal flag', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: 3, series: { pv: true, sp: true } },
        freeSlot(),
        freeSlot(),
        freeSlot(),
      ]),
    );
    expect(readTrendSelection()).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
  });

  it('degrades to session-only when the write throws', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('QuotaExceededError');
    });
    expect(() => writeTrendSelection([occupied(1), freeSlot(), freeSlot(), freeSlot()])).not.toThrow();
  });

  it('degrades to four free slots when the read throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('SecurityError');
    });
    expect(readTrendSelection()).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
  });
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd packages/smart_pid_web && npx vitest run src/features/multitrend/trendSelectionStore.test.ts`
Expected: FAIL — the file cannot be collected:
`Error: Failed to resolve import "./trendSelectionStore" from "src/features/multitrend/trendSelectionStore.test.ts". Does the file exist?`

- [ ] **Step 3: Write the store**

Create `packages/smart_pid_web/src/features/multitrend/trendSelectionStore.ts`:

```ts
import { freeSlot, MAX_SLOTS, SIGNALS, type TrendSlot } from './types';

/**
 * Trend-selection persistence (§9.1).
 *
 * Deliberately NOT a `useSyncExternalStore` store: `useSettings` uses that
 * pattern because preferences have many readers, and the trend selection has
 * exactly one. Two pure functions are the whole surface.
 *
 * Its own key, not folded into `AppPreferences`: that is a user-facing form
 * with a "Restaurar padrões" button, and a preference reset must not wipe a
 * trend layout.
 */

export const TREND_SELECTION_KEY = 'spid.multitrend';

function fourFreeSlots(): TrendSlot[] {
  return Array.from({ length: MAX_SLOTS }, freeSlot);
}

/** Anything not exactly four well-formed slots is discarded, never patched. */
function isTrendSlot(value: unknown): value is TrendSlot {
  if (typeof value !== 'object' || value === null) return false;
  const slot = value as { controllerId?: unknown; series?: unknown };
  if (slot.controllerId !== null && typeof slot.controllerId !== 'number') return false;
  if (typeof slot.series !== 'object' || slot.series === null) return false;
  const series = slot.series as Record<string, unknown>;
  return SIGNALS.every((signal) => typeof series[signal] === 'boolean');
}

export function readTrendSelection(): TrendSlot[] {
  try {
    const raw = localStorage.getItem(TREND_SELECTION_KEY);
    if (raw === null) return fourFreeSlots();
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed) || parsed.length !== MAX_SLOTS) return fourFreeSlots();
    if (!parsed.every(isTrendSlot)) return fourFreeSlots();
    return parsed.map(({ controllerId, series }) => ({
      controllerId,
      series: { pv: series.pv, sp: series.sp, co: series.co },
    }));
  } catch {
    // Corrupt, blocked or unreadable storage must never take the page down.
    return fourFreeSlots();
  }
}

export function writeTrendSelection(slots: readonly TrendSlot[]): void {
  try {
    localStorage.setItem(TREND_SELECTION_KEY, JSON.stringify(slots));
  } catch {
    // Quota or private mode: degrade to session-only, surface nothing.
  }
}
```

- [ ] **Step 4: Run the store test and watch it pass**

Run: `cd packages/smart_pid_web && npx vitest run src/features/multitrend/trendSelectionStore.test.ts`
Expected: PASS — 9 passed.

- [ ] **Step 5: Write the failing hook tests**

In `packages/smart_pid_web/src/features/multitrend/useMultiTrendModel.test.tsx`, replace lines
1-18 with:

```tsx
import type { ReactNode } from 'react';
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { statusEnvelope } from '@/test/fixtures';
import { createFakeRealtime, TestProviders } from '@/test/providers';
import { freeSlot, MAX_SLOTS } from './types';
import { TREND_SELECTION_KEY } from './trendSelectionStore';
import { useMultiTrendModel } from './useMultiTrendModel';

const controllerA = { id: 1 };
const controllerB = { id: 2 };

/** `null` roster = the stats query has not resolved; nothing is reconciled. */
function setup(roster: readonly number[] | null = null) {
  const realtime = createFakeRealtime();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <TestProviders realtime={realtime.value}>{children}</TestProviders>
  );
  return { realtime, ...renderHook(() => useMultiTrendModel(roster), { wrapper }) };
}

beforeEach(() => {
  localStorage.clear();
});
```

Then append this describe block at the end of the file:

```tsx
describe('useMultiTrendModel persistence and reconciliation', () => {
  it('restores a stored layout on mount', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: 3, series: { pv: true, sp: false, co: true } },
        freeSlot(),
        freeSlot(),
        freeSlot(),
      ]),
    );
    const { result } = setup();
    expect(result.current.slots[0]).toEqual({
      controllerId: 3,
      series: { pv: true, sp: false, co: true },
    });
    expect(result.current.isSelected(3, 'co')).toBe(true);
  });

  it('persists every selection change', () => {
    const { result } = setup();
    act(() => result.current.assign(1, controllerB));
    const stored = JSON.parse(localStorage.getItem(TREND_SELECTION_KEY) ?? 'null') as unknown[];
    expect(stored).toHaveLength(MAX_SLOTS);
    expect(stored[1]).toEqual({ controllerId: 2, series: { pv: true, sp: true, co: true } });
  });

  it('releases a restored slot whose loop is absent from the roster', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: 3, series: { pv: true, sp: true, co: true } },
        { controllerId: 1, series: { pv: true, sp: false, co: false } },
        freeSlot(),
        freeSlot(),
      ]),
    );
    const { result } = setup([1, 2]);
    expect(result.current.slots[0]).toEqual(freeSlot());
    expect(result.current.slots[1].controllerId).toBe(1);
  });

  it('releases a restored slot that has no signal enabled', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: 1, series: { pv: false, sp: false, co: false } },
        freeSlot(),
        freeSlot(),
        freeSlot(),
      ]),
    );
    const { result } = setup([1]);
    expect(result.current.slots[0]).toEqual(freeSlot());
  });

  it('reconciles nothing while the roster is still null', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: 99, series: { pv: true, sp: true, co: true } },
        freeSlot(),
        freeSlot(),
        freeSlot(),
      ]),
    );
    const { result } = setup(null);
    expect(result.current.slots[0].controllerId).toBe(99);
  });

  it('ignores malformed storage and starts from four free slots', () => {
    localStorage.setItem(TREND_SELECTION_KEY, '{"nope":true}');
    const { result } = setup();
    expect(result.current.slots).toEqual([freeSlot(), freeSlot(), freeSlot(), freeSlot()]);
  });

  it('never restores paused', () => {
    localStorage.setItem(
      TREND_SELECTION_KEY,
      JSON.stringify([
        { controllerId: 1, series: { pv: true, sp: true, co: true } },
        freeSlot(),
        freeSlot(),
        freeSlot(),
      ]),
    );
    const { result } = setup([1]);
    expect(result.current.paused).toBe(false);
  });
});
```

- [ ] **Step 6: Run the hook test and watch it fail**

Run: `cd packages/smart_pid_web && npx vitest run src/features/multitrend/useMultiTrendModel.test.tsx`
Expected: FAIL — TypeScript rejects `useMultiTrendModel(roster)` with
`Expected 0 arguments, but got 1.`, and the seven new cases fail with
`expected { controllerId: null, … } to deeply equal { controllerId: 3, … }` once the argument
is ignored.

- [ ] **Step 7: Change the hook signature and add persistence**

In `packages/smart_pid_web/src/features/multitrend/useMultiTrendModel.ts`, add to the `./types`
import block on lines 5-13 nothing new, and add a new import immediately after it:

```ts
import { readTrendSelection, writeTrendSelection } from './trendSelectionStore';
```

Replace lines 65-71 with:

```ts
export function useMultiTrendModel(roster: readonly number[] | null): MultiTrendModel {
  // Lazily initialised from storage: a layout an operator built must survive a
  // navigation, a reload and a browser restart (§9.1).
  const [slots, setSlots] = useState<TrendSlot[]>(readTrendSelection);
  const [paused, setPaused] = useState(false);
  const [pxWidth, setPxWidth] = useState(800);
  const [revision, setRevision] = useState(0);
```

- [ ] **Step 8: Add the persist and reconcile effects**

In the same file, immediately after the `subscribe` effect closes (originally line 106, the
`  );` that ends `useEffect( … [subscribe])`), insert:

```ts
  useEffect(() => {
    writeTrendSelection(slots);
  }, [slots]);

  /**
   * One-shot reconciliation against the live roster (§9.2). A restored slot for
   * a loop that no longer exists would render a permanently empty cell, and a
   * slot with no signal left is not a selection. Gated on `roster !== null`: an
   * unresolved query must never be read as "every loop is gone".
   */
  const reconciled = useRef(false);
  useEffect(() => {
    if (roster === null || reconciled.current) return;
    reconciled.current = true;
    setSlots((prev) =>
      prev.map((s) => {
        if (s.controllerId === null) return s;
        const silent = !s.series.pv && !s.series.sp && !s.series.co;
        if (!roster.includes(s.controllerId) || silent) {
          buffers.current.delete(s.controllerId);
          return freeSlot();
        }
        return s;
      }),
    );
  }, [roster]);
```

- [ ] **Step 9: Update the three call sites**

`packages/smart_pid_web/src/pages/MultiTrendPage.tsx` line 28:

```tsx
  const model = useMultiTrendModel(stats.isPending ? null : stats.loops);
```

`packages/smart_pid_web/src/features/multitrend/useMultiTrendModel.test.tsx` — already done in
Step 5 (`setup()` defaults `roster` to `null`, preserving every existing case's behaviour
exactly).

`packages/smart_pid_web/src/realtime/multiLoopFanout.test.tsx` line 157:

```tsx
    const { result } = renderHook(() => useMultiTrendModel(null), {
```

- [ ] **Step 10: Run the three suites and watch them pass**

Run: `cd packages/smart_pid_web && npx vitest run src/features/multitrend src/realtime/multiLoopFanout.test.tsx src/pages`
Expected: PASS — all green, including the seven new persistence/reconciliation cases and the
untouched slot-invariant, toggling and live-buffer describes.

- [ ] **Step 11: Add the Playwright reload case**

Append to `packages/smart_pid_web/e2e/multitrend.spec.ts`, inside the
`test.describe('Multi-trend', …)` block:

```ts
  test('a trend selection survives a full page reload', async ({ page }) => {
    await page.goto('/multitrend');

    await page.getByLabel('Loop 1 · PV').check();
    await page.getByLabel('Loop 2 · CO').check();
    await expect(page.getByLabel('Loop 1 · PV')).toBeChecked();

    await page.reload();

    await expect(page.getByLabel('Loop 1 · PV')).toBeChecked();
    await expect(page.getByLabel('Loop 2 · CO')).toBeChecked();
    await expect(page.getByLabel('Loop 1 · SP')).not.toBeChecked();
    expect(
      await page.evaluate(() => localStorage.getItem('spid.multitrend')),
    ).not.toBeNull();
  });
```

- [ ] **Step 12: Run the e2e spec and watch it pass**

Run: `cd packages/smart_pid_web && env -u CI npx playwright test e2e/multitrend.spec.ts`
Expected: PASS — every test in the file, including the new reload case. The existing
`getByLabel('Loop 1 · PV')` locators still resolve: the checkbox accessible name is frozen.

- [ ] **Step 13: Typecheck, lint and commit**

Run: `npm --prefix packages/smart_pid_web run typecheck && npm --prefix packages/smart_pid_web run lint`
Expected: both exit 0.

```bash
git add packages/smart_pid_web/src/features/multitrend/trendSelectionStore.ts packages/smart_pid_web/src/features/multitrend/trendSelectionStore.test.ts packages/smart_pid_web/src/features/multitrend/useMultiTrendModel.ts packages/smart_pid_web/src/features/multitrend/useMultiTrendModel.test.tsx packages/smart_pid_web/src/realtime/multiLoopFanout.test.tsx packages/smart_pid_web/src/pages/MultiTrendPage.tsx packages/smart_pid_web/e2e/multitrend.spec.ts
git commit -m "feat(web): persist the trend selection and reconcile it against the roster"
```

---

### Task 7: Title every trend cell and selector row

Implements spec §9.3. Format `#3 · TIC-E2E`, fallback `Loop {id}`, checkbox accessible name
frozen.

**Files:**
- Modify: `packages/smart_pid_web/src/features/multitrend/SeriesSelector.tsx:19-53`
- Modify: `packages/smart_pid_web/src/pages/MultiTrendPage.tsx:1-14`, `:26-42`, `:63-78`
- Test: `packages/smart_pid_web/src/features/multitrend/SeriesSelector.test.tsx`

**Interfaces:**
- Consumes: `useControllers(): UseQueryResult<ControllerResponse[]>` from `@/features/dashboard/useControllers` (already cached — the dashboard uses the same `queryKeys.controllers` entry); `MultiTrendChartProps.ariaLabel: string`.
- Produces: `SeriesSelectorProps` gains a required member `loopLabel(loopId: number): string`. The full prop list becomes `{ loops: readonly number[]; loopLabel(loopId: number): string; isSelected(loopId: number, signal: Signal): boolean; isFull: boolean; occupiedLoops: readonly number[]; onToggle(loopId: number, signal: Signal): void }`.

- [ ] **Step 1: Write the failing selector test**

In `packages/smart_pid_web/src/features/multitrend/SeriesSelector.test.tsx`, replace lines 5-18
with:

```tsx
function renderSelector(overrides: Partial<SeriesSelectorProps> = {}) {
  const onToggle = vi.fn();
  render(
    <SeriesSelector
      loops={[1, 2]}
      loopLabel={(id) => (id === 1 ? '#1 · FIC-101' : `Loop ${id}`)}
      isSelected={() => false}
      isFull={false}
      occupiedLoops={[]}
      onToggle={onToggle}
      {...overrides}
    />,
  );
  return { onToggle };
}
```

Then append this case to the `describe('SeriesSelector', …)` block:

```tsx
  it('shows the loop title as visible text while the accessible name stays frozen', () => {
    renderSelector();
    expect(screen.getByText('#1 · FIC-101')).toBeVisible();
    // Loop 2 has no name yet — the row must never go blank.
    expect(screen.getByText('Loop 2')).toBeVisible();
    for (const name of ['Loop 1 · PV', 'Loop 1 · SP', 'Loop 1 · CO', 'Loop 2 · CO']) {
      expect(screen.getByLabelText(name)).toBeInTheDocument();
    }
  });
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd packages/smart_pid_web && npx vitest run src/features/multitrend/SeriesSelector.test.tsx`
Expected: FAIL — TypeScript rejects the unknown prop
`Object literal may only specify known properties, and 'loopLabel' does not exist in type 'SeriesSelectorProps'`, and the new case fails with
`Unable to find an element with the text: #1 · FIC-101`.

- [ ] **Step 3: Add the `loopLabel` prop to `SeriesSelector`**

In `packages/smart_pid_web/src/features/multitrend/SeriesSelector.tsx`, replace lines 19-27:

```tsx
export interface SeriesSelectorProps {
  /** Controller ids offered, ascending. */
  loops: readonly number[];
  isSelected(loopId: number, signal: Signal): boolean;
  /** Every slot taken — loops outside `occupiedLoops` can no longer be added. */
  isFull: boolean;
  occupiedLoops: readonly number[];
  onToggle(loopId: number, signal: Signal): void;
}
```

with:

```tsx
export interface SeriesSelectorProps {
  /** Controller ids offered, ascending. */
  loops: readonly number[];
  /** Row title, `#3 · TIC-E2E`; the caller falls back to `Loop {id}`. */
  loopLabel(loopId: number): string;
  isSelected(loopId: number, signal: Signal): boolean;
  /** Every slot taken — loops outside `occupiedLoops` can no longer be added. */
  isFull: boolean;
  occupiedLoops: readonly number[];
  onToggle(loopId: number, signal: Signal): void;
}
```

Replace lines 29-35 (the destructuring) with:

```tsx
export function SeriesSelector({
  loops,
  loopLabel,
  isSelected,
  isFull,
  occupiedLoops,
  onToggle,
}: SeriesSelectorProps) {
```

Replace lines 46-53 (the row title span) with:

```tsx
              <span
                className={cn(
                  // w-28 fits `#3 · TIC-E2E`; w-16 clipped it.
                  'numeric w-28 shrink-0 truncate text-xs',
                  locked ? 'text-text-disabled' : 'text-text-soft',
                )}
              >
                {loopLabel(loopId)}
              </span>
```

Update the component doc comment at lines 4-11 — replace the sentence
``The accessible name `Loop {id} · {SIGNAL}` is frozen by the multitrend E2E; the visible text is the short signal tag, which the accessible name contains (WCAG 2.5.3).``
with:

```
 * The checkbox accessible name `Loop {id} · {SIGNAL}` is FROZEN by the
 * multitrend E2E and by this file's own suite; only the row title changes to
 * `#3 · TIC-E2E` so the selector and the grid map onto each other by sight.
 * The visible signal text is the short tag, which the accessible name contains
 * (WCAG 2.5.3).
```

- [ ] **Step 4: Run the selector test and watch it pass**

Run: `cd packages/smart_pid_web && npx vitest run src/features/multitrend/SeriesSelector.test.tsx`
Expected: PASS — 5 passed, the four frozen `getByLabelText('Loop N · SIGNAL')` assertions
included.

- [ ] **Step 5: Build the id→name lookup in `MultiTrendPage`**

In `packages/smart_pid_web/src/pages/MultiTrendPage.tsx`, add to the import block:

```tsx
import { useControllers } from '@/features/dashboard/useControllers';
```

Insert after line 27 (`const stats = useStats();`):

```tsx
  // Already cached — the dashboard runs the same `queryKeys.controllers` query.
  // The id→tag join is client-side by design: /controllers/stats stays lean.
  const controllers = useControllers();
  const loopLabel = useMemo(() => {
    const byId = new Map<number, string>();
    for (const c of controllers.data ?? []) byId.set(c.id, c.name);
    // Never blank: an unloaded or deleted loop still reads `Loop {id}`.
    return (loopId: number): string => {
      const name = byId.get(loopId);
      return name === undefined ? `Loop ${loopId}` : `#${loopId} · ${name}`;
    };
  }, [controllers.data]);
```

- [ ] **Step 6: Title each grid cell and its chart**

In the same file, replace lines 64-76 — the `model.slots.map(…)` expression — with:

```tsx
              model.slots.map((slot, index) =>
                slot.controllerId === null ? null : (
                  <div key={slot.controllerId} className="flex min-w-0 flex-col gap-1">
                    <h2 className="numeric truncate text-2xs uppercase tracking-wider text-text-soft">
                      {loopLabel(slot.controllerId)}
                    </h2>
                    <MultiTrendChart
                      id={`slot-${index}`}
                      testId={`multitrend-slot-${index}`}
                      ariaLabel={`Tendência ${loopLabel(slot.controllerId)}`}
                      series={model.slotSeries[index]}
                      sync={sync}
                      onPxWidth={model.setPxWidth}
                    />
                  </div>
                ),
              )
```

- [ ] **Step 7: Pass `loopLabel` to the selector**

In the same file, replace the `<SeriesSelector … />` element (originally lines 89-95) with:

```tsx
          <SeriesSelector
            loops={stats.loops}
            loopLabel={loopLabel}
            isSelected={model.isSelected}
            isFull={model.isFull}
            occupiedLoops={occupiedLoops}
            onToggle={model.toggleSignal}
          />
```

- [ ] **Step 8: Run the page and feature suites**

Run: `cd packages/smart_pid_web && npx vitest run src/pages src/features/multitrend`
Expected: PASS — all green. `MultiTrendChart.test.tsx` passes `ariaLabel` explicitly as a prop
and is unaffected.

- [ ] **Step 9: Run the multitrend e2e spec**

Run: `cd packages/smart_pid_web && env -u CI npx playwright test e2e/multitrend.spec.ts`
Expected: PASS — the `getByLabel('Loop 1 · PV')` / `getByLabel('Loop 2 · CO')` locators at
lines 150, 151 and 214 still resolve, because only the row title text changed.

- [ ] **Step 10: Typecheck, lint and commit**

Run: `npm --prefix packages/smart_pid_web run typecheck && npm --prefix packages/smart_pid_web run lint`
Expected: both exit 0.

```bash
git add packages/smart_pid_web/src/features/multitrend/SeriesSelector.tsx packages/smart_pid_web/src/features/multitrend/SeriesSelector.test.tsx packages/smart_pid_web/src/pages/MultiTrendPage.tsx
git commit -m "feat(web): name the loop on every trend cell and selector row"
```

---

### Task 8: Update the `TEST_E2E.md` gate

Implements spec §11.3 for the four procedures the UI corrections touch. **E2E-045 and E2E-046
belong to the sibling theme plan — do not edit them.**

**Files:**
- Modify: `TEST_E2E.md:92-96`, `:282-286`, `:364-368`, `:385`, `:415`, `:428`

**Interfaces:**
- Consumes: the `Executivo` nav entry from Task 5, the rail geometry from Task 2.
- Produces: no code symbol. The gate stays at 50 procedures; E2E-006 is repurposed rather than deleted, and E2E-049 gains a strictly stronger assertion.

- [ ] **Step 1: Repurpose E2E-006**

In `TEST_E2E.md`, replace lines 92-96:

```markdown
#### E2E-006 — Command palette
- **Steps:** Press `k` outside a field; search `alarm`; activate `Ir para Alarmes`; repeat while cursor is inside an input.
- **Expected:** Palette opens and navigates to `/alarms`; typing `k` inside a field enters text and does not open the palette.
- **Evidence:** `test-evidence/E2E-006-command-palette.png`
- **Result:** [x] PASS [ ] FAIL
```

with:

```markdown
#### E2E-006 — Executive dashboard from the top bar
- **Steps:** As `admin` and as `operador`, click `Executivo` in the top bar; confirm the route; click the wordmark.
- **Expected:** `Executivo` is present for both roles and navigates to `/executive`; the wordmark navigates to `/`.
- **Evidence:** `test-evidence/E2E-006-executive-nav.png`
- **Result:** [ ] PASS [ ] FAIL
```

- [ ] **Step 2: Restate E2E-036's steps**

Replace line 283:

```markdown
- **Steps:** Let loops run; open `/executive` from wordmark/palette.
```

with:

```markdown
- **Steps:** Let loops run; open `/executive` from the top bar.
```

and set line 286 to:

```markdown
- **Result:** [ ] PASS [ ] FAIL
```

The expected outcome on line 284 is unchanged.

- [ ] **Step 3: Strengthen E2E-049**

Replace lines 365-368:

```markdown
- **Steps:** Use CDP viewports 1440×900, 1024×768, 768×900, 320×800; capture dashboard at each.
- **Expected:** ≥1024 trend/faceplate side-by-side; <1024 faceplate stacks; <768 cards scroll and alarm count chip replaces full footer; 320 retains monitoring, ACK and SP input without horizontal page overflow.
- **Evidence:** `test-evidence/E2E-049-responsive.png`
- **Result:** [x] PASS [ ] FAIL
```

with:

```markdown
- **Steps:** Use CDP viewports 1920×1080, 1600×900, 1440×900, 1024×768, 768×900, 320×800; capture dashboard at each. At every viewport ≥1024, for roles `admin` and `operador`, with and without the simulator banner, evaluate `const fp = document.querySelector('aside[aria-label^="Faceplate"]'); fp.scrollHeight === fp.clientHeight` and `document.documentElement.scrollHeight === document.documentElement.clientHeight`.
- **Expected:** ≥1024 trend/faceplate side-by-side, the faceplate being the full-height LEFT column; <1024 faceplate stacks under the trend; <768 cards scroll and alarm count chip replaces full footer; 320 retains monitoring, ACK and SP input without horizontal page overflow. **New, stricter:** the faceplate rail's `scrollHeight === clientHeight` and the page has no vertical scrollbar in all 16 viewport×role×banner combinations. Every interactive target inside the rail stays ≥44×44 CSS px.
- **Evidence:** `test-evidence/E2E-049-responsive.png`
- **Result:** [ ] PASS [ ] FAIL
```

- [ ] **Step 4: Update the three summary-table rows**

Replace line 385:

```markdown
| E2E-006 | Command palette | PASS | `E2E-006-command-palette.png` |  |
```

with:

```markdown
| E2E-006 | Executive dashboard from the top bar | PENDING | `E2E-006-executive-nav.png` | Repurposed: the command palette was removed; the number now covers the navigation path that replaced it |
```

Replace line 415:

```markdown
| E2E-036 | Executive KPIs | PASS | `E2E-036-executive-kpis.png` | Feature added: /system/status now publishes CPU and memory (psutil, soft dep) |
```

with:

```markdown
| E2E-036 | Executive KPIs | PENDING | `E2E-036-executive-kpis.png` | Steps restated: `/executive` is opened from the top bar. Expected outcome unchanged. Feature added earlier: /system/status publishes CPU and memory (psutil, soft dep) |
```

Replace line 428:

```markdown
| E2E-049 | Responsive breakpoints | PASS | `E2E-049-responsive.png` | Bug fixed: header overflowed 4 px at the 320 px floor |
```

with:

```markdown
| E2E-049 | Responsive breakpoints | PENDING | `E2E-049-responsive.png` | Strengthened: faceplate rail `scrollHeight === clientHeight` across 16 combinations. Bug fixed earlier: header overflowed 4 px at the 320 px floor |
```

- [ ] **Step 5: Confirm the gate is still 50 procedures**

Run: `grep -c '^#### E2E-' TEST_E2E.md`
Expected: `50`.

Run: `grep -n 'E2E-045\|E2E-046' TEST_E2E.md | head -4`
Expected: the pre-existing lines, unmodified — those two belong to the sibling theme plan.

- [ ] **Step 6: Commit**

```bash
git add TEST_E2E.md
git commit -m "docs(e2e): repurpose E2E-006, restate E2E-036, strengthen E2E-049"
```

---

### Task 9: Verification sweep

Mirrors spec §12 steps 1-5. Steps 6-11 of §12 are the theme's and belong to the sibling plan.

**Files:**
- Modify: none by default. Any failure here is fixed in the task that owns the file.
- Test: the whole frontend suite plus a CDP measurement sweep.

**Interfaces:**
- Consumes: every artefact of Tasks 1-8.
- Produces: a pass/fail record. No new symbol.

- [ ] **Step 1: Typecheck and lint (§12.1)**

Run: `npm --prefix packages/smart_pid_web run typecheck && npm --prefix packages/smart_pid_web run lint`
Expected: both exit 0, no diagnostics.

- [ ] **Step 2: Full Vitest run (§12.2)**

Run: `npm --prefix packages/smart_pid_web run test`
Expected: PASS — every test file green. Relative to the 746-passing baseline the count shifts
by: −3 (AppShell palette cases), −N (`Command.test.tsx` deleted with the component), −2
(AiPanel field-inventory and guardrail cases moved), +5 (LoopConfigDialog AI Optimization),
+9 (`trendSelectionStore.test.ts`), +7 (useMultiTrendModel persistence/reconciliation), +1
(SeriesSelector title), +3 (AppShell registry/executive/icon), +1 (LoopCard icon). No failure
is acceptable.

- [ ] **Step 3: Full Playwright run (§12.3)**

Run: `cd packages/smart_pid_web && env -u CI npx playwright test`
Expected: PASS — all specs green. **Not** the `browser` tool: it does not deliver CDP input to
the page.

- [ ] **Step 4: CDP measurement sweep for §4.4 (§12.4)**

The 16 combinations (4 viewports × 2 roles × simulator banner on/off) are already encoded in
the `the faceplate rail never scrolls at any supported desktop viewport` test added in Task 2
for the banner-off half. Cover the banner-on half by running the same measurement against a
live instance with the simulator running.

Start the app and backend, then run:

```bash
cd packages/smart_pid_web && env -u CI npx playwright test e2e/responsive.spec.ts -g "never scrolls"
```

Expected: PASS — 1 passed, all 8 assertions inside it green.

For the twin-banner half, with the simulator running against `http://127.0.0.1:5173`, evaluate
per viewport and role:

```js
const fp = document.querySelector('aside[aria-label^="Faceplate"]');
JSON.stringify({
  banner: document.querySelector('[data-testid="simulation-mode-banner"]') !== null,
  rail: fp.scrollHeight - fp.clientHeight,
  page: document.documentElement.scrollHeight - document.documentElement.clientHeight,
});
```

Expected: `banner` is `true` and both `rail` and `page` are `0` at 1920×1080, 1600×900,
1440×900 and 1024×768, for `admin` and for `operador`. A non-zero `rail` at 1024×768 means the
32 px LOG.AI floor must come down further (spec §13, first risk row) — never a 44 px target.

- [ ] **Step 5: Re-confirm the 320 px nav floor (§12.5)**

With the app loaded at a 320 px viewport, evaluate:

```js
const nav = document.querySelector('nav[aria-label="Navegação principal"]');
JSON.stringify({
  navScroll: nav.scrollWidth,
  navClient: nav.clientWidth,
  headerOverflow: document.querySelector('header').scrollWidth - document.querySelector('header').clientWidth,
  pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
});
```

Expected: `navScroll` reads `236` (5 links × 44 px + 4 gaps × 4 px), `headerOverflow` is `0`
and `pageOverflow` is `0`. Any non-zero `pageOverflow` is a failure of E2E-049 and must be
fixed before this plan is done.

- [ ] **Step 6: Re-capture the evidence PNGs for the four affected procedures**

E2E-006 (`test-evidence/E2E-006-executive-nav.png`), E2E-036
(`test-evidence/E2E-036-executive-kpis.png`), E2E-049
(`test-evidence/E2E-049-responsive.png`), plus E2E-015 and E2E-043 whose assertions remain
valid but whose screenshots now show the new layout
(`test-evidence/E2E-015-faceplate-consistency.png`,
`test-evidence/E2E-043-user-forbidden.png` — use the filenames already recorded in
`TEST_E2E.md` for those two rows).

Then flip the four `- **Result:** [ ] PASS` lines you set in Task 8 to `[x] PASS` and the three
`PENDING` summary cells back to `PASS`.

- [ ] **Step 7: Confirm no backend file was touched**

Run: `git diff --stat main -- '*.py'`
Expected: no output. This work is frontend-only; the backend suite is deliberately not re-run.

- [ ] **Step 8: Commit the evidence and gate result**

```bash
git add TEST_E2E.md test-evidence
git commit -m "test(e2e): re-run the four gate procedures affected by the UI corrections"
```

---

## Spec discrepancies

Two points where the spec's stated test impact is incomplete. Both are handled above; neither
changes a designed behaviour.

1. **§11.2 understates the `responsive.spec.ts` change.** It lists only "replace the `Comandos`
   target-size assertion; add the rail no-scroll assertion at each viewport". But the existing
   test `trend and faceplate split at >=1024 and stack below it` asserts
   `fp.x > t.x + t.width - 1` — the faceplate is to the **right** of the trend. §4.2 moves it to
   the left, so that assertion must be **restated** (`fp.x + fp.width < t.x + 1`), not merely
   augmented. Task 2 Step 1 does this. The assertion is not weakened: it still pins a strict
   side-by-side relationship, only with the sides in their new order, which is exactly what
   §11.3's E2E-049 row says ("faceplate is now the left column").

2. **§4.2 says the below-`lg` stacked behaviour is unchanged, while §4.2's diagram puts the
   faceplate first.** Those are only reconcilable through CSS ordering: DOM order stays
   cards → trend → faceplate (so the stacked reading order and the existing 900 px stacking
   assertion hold) and the rail takes `lg:order-first` to become the left column once the flex
   row exists. Task 2 Step 3 and Step 5 implement it that way.

---

## Spec coverage

| Spec section | Change | Task |
|---|---|---|
| §4 — Faceplate as a full-height left rail | Two-column `DashboardPage`, `lg:order-first` rail, `lg:border-r`, `gap-2`, `p-2`, elastic LOG.AI with a 32 px floor, single AI action row | **Task 2** (compaction levers), **Task 9** (§4.4 measurement) |
| §5 — Move the AI configuration form into the loop config dialog | `AiConfigSection.tsx`, `Draft.process_speed` + `Draft.ai`, `<Section label="AI Optimization">`, single PATCH, `Salvar IA` deleted | **Task 1** |
| §6 — Remove the command palette | `AppShell` listener/button/dialog, `AppRoute.command`, `commandRoutes()`, `Command.tsx` + test, `cmdk` | **Task 3** |
| §7 — Icons instead of `[cfg]` | `<Settings>` in `AppShell`, `<SlidersHorizontal>` in `LoopCard`, `NewLoopDialog` copy | **Task 4** (icons), **Task 1 Step 15** (copy) |
| §8 — Executive dashboard in the top bar | `nav: { label: 'Executivo', order: 50 }`, wordmark → `/`, 320 px floor re-measured | **Task 5**, **Task 9 Step 5** |
| §9.1 — Trend selection persistence | `trendSelectionStore.ts`, lazy init, persist effect, `spid.multitrend`, defensive parse | **Task 6** |
| §9.2 — Roster reconciliation | `useMultiTrendModel(roster)`, one-shot effect, three call sites updated | **Task 6** |
| §9.3 — Titled trend cells | `#3 · TIC-E2E` in the cell header, the chart `aria-label` and the selector rows; `Loop {id}` fallback; checkbox name frozen | **Task 7** |
| §11.1 — Unit/component test impact | AppShell, Command, AiPanel, LoopConfigDialog, SeriesSelector, useMultiTrendModel, multiLoopFanout | **Tasks 1, 3, 4, 5, 6, 7** |
| §11.2 — Playwright impact | login-dashboard, responsive, target-size, multitrend | **Tasks 2, 3, 6** |
| §11.3 — `TEST_E2E.md` (E2E-006, E2E-036, E2E-049 only) | Repurposed, restated, strengthened | **Task 8** |
| §12.1–§12.5 — Verification | typecheck, lint, Vitest, Playwright, CDP rail sweep, 320 px nav re-measure | **Task 9** |

Not covered here, by design: spec §10 (the `neon` theme) and the `TEST_E2E.md` procedures
E2E-045 and E2E-046, which belong to the sibling theme plan.
