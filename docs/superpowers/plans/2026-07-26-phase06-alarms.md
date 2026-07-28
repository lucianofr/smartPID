# Phase 6 — Alarms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the flood-safe alarm panel, four-severity state presentation, acknowledgement/history flows, administrator configuration, and the fully wired global alarm footer.

**Architecture:** REST seeds active/history data; realtime envelopes transition each alarm through the phase-3 state machine. `VirtualList` renders active floods. Acknowledgements always refetch; no optimistic process truth.

**Tech Stack:** React 18, TanStack Query/Virtual, phase-2 primitives, phase-3 alarm machine/realtime, Vitest, Playwright.

## Global Constraints

- Four severities: CRITICAL octagon, WARNING triangle, ADVISORY diamond, LOG dot.
- Severity and acknowledgement are never color-only; reduced motion uses a static badge/highlight.
- Both roles may acknowledge; only admin may configure alarm limits.

---

### Task 1: Severity and Alarm Model

**Files:**
- Create: `packages/smart_pid_web/src/features/alarms/severity.ts`
- Create: `packages/smart_pid_web/src/features/alarms/types.ts`
- Test: `packages/smart_pid_web/src/features/alarms/__tests__/severity.test.ts`

- [ ] **Step 1: Write complete mapping test**

```ts
expect(severity('CRITICAL')).toEqual({label:'CRITICAL',glyph:'octagon',token:'--alarm-crit'});
expect(severity('WARNING')).toEqual({label:'WARNING',glyph:'triangle',token:'--alarm-warn'});
expect(severity('ADVISORY')).toEqual({label:'ADVISORY',glyph:'diamond',token:'--alarm-adv'});
expect(severity('LOG')).toEqual({label:'LOG',glyph:'dot',token:'--alarm-log'});
```

- [ ] **Step 2: Implement and verify**

Run: `npm run test -- src/features/alarms/__tests__/severity.test.ts`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/alarms
git commit -m "feat(web): define four-severity alarm language"
```

### Task 2: Active Alarm Panel and Acknowledgement

**Files:**
- Create: `packages/smart_pid_web/src/features/alarms/useAlarms.ts`
- Create: `packages/smart_pid_web/src/features/alarms/AlarmPanel.tsx`
- Create: `packages/smart_pid_web/src/features/alarms/__tests__/AlarmPanel.test.tsx`
- Create: `packages/smart_pid_web/src/pages/AlarmsPage.tsx`
- Modify: `packages/smart_pid_web/src/app/routes.tsx`

**Interfaces:** GET `/alarms/active`; POST `/alarms/{id}/ack`; POST `/alarms/ack-all`.

- [ ] **Step 1: Write ack lifecycle test**

```tsx
const row = await screen.findByTestId('alarm-row-42');
expect(row).toHaveTextContent('UNACKNOWLEDGED');
await userEvent.click(within(row).getByRole('button',{name:'ACK'}));
expect(ack).toHaveBeenCalledWith(42);
expect(await screen.findByTestId('alarm-row-42')).toHaveTextContent('ACKNOWLEDGED');
```

- [ ] **Step 2: Implement VirtualList and state channels**

Each row carries glyph + severity text, bold/unacked icon, and status text. `VirtualList` receives `estimateSize={() => 48}`. Acknowledge mutation invalidates `alarmsActive`; realtime transitions reconcile with REST.

- [ ] **Step 3: Register route**

```ts
appRoutes.push({path:'/alarms',element:AlarmsPage,
  nav:{label:'Alarms',order:30},command:{label:'Ir para Alarmes',keywords:['alarmes']}});
```

- [ ] **Step 4: Verify and commit**

Run: `npm run test -- src/features/alarms/__tests__/AlarmPanel.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/alarms packages/smart_pid_web/src/pages/AlarmsPage.tsx packages/smart_pid_web/src/app/routes.tsx
git commit -m "feat(web): add active alarm panel and acknowledgement"
```

### Task 3: History Filters

**Files:**
- Create: `packages/smart_pid_web/src/features/alarms/AlarmHistory.tsx`
- Create: `packages/smart_pid_web/src/features/alarms/__tests__/AlarmHistory.test.tsx`

**Interfaces:** GET `/alarms/history?start=<iso>&end=<iso>&limit=<n>`.

- [ ] **Step 1: Write filter request test**

```tsx
await userEvent.selectOptions(screen.getByLabelText('Prioridade'), 'WARNING');
await userEvent.selectOptions(screen.getByLabelText('Tipo'), 'HI');
await userEvent.click(screen.getByRole('button',{name:'Aplicar filtros'}));
expect(history).toHaveBeenCalledWith(expect.objectContaining({priority:'WARNING',type:'HI'}));
```

- [ ] **Step 2: Implement filters**

Send required `start` and `end`, default `limit=1000`; filter priority/type client-side only if backend lacks parameters. Use ISO timestamps and preserve the selected range after errors.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/alarms/__tests__/AlarmHistory.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/alarms/AlarmHistory*
git commit -m "feat(web): add alarm history filters"
```

### Task 4: Alarm Configuration

**Files:**
- Create: `packages/smart_pid_web/src/features/alarms/AlarmConfigForm.tsx`
- Create: `packages/smart_pid_web/src/features/alarms/useAlarmConfig.ts`
- Test: `packages/smart_pid_web/src/features/alarms/__tests__/AlarmConfigForm.test.tsx`

- [ ] **Step 1: Write role and validation tests**

```tsx
renderConfig({role:'user'}); expect(screen.queryByRole('form',{name:'Configuração de alarmes'})).toBeNull();
renderConfig({role:'admin'}); await userEvent.clear(screen.getByLabelText('HIHI'));
await userEvent.type(screen.getByLabelText('HIHI'),'70');
expect(screen.getByText('HIHI deve ser maior que HI')).toBeVisible();
```

- [ ] **Step 2: Implement form**

Fields: deadband, HIHI/HI/LO/LOLO values and priority selects. Gate with `useCan('alarms.configure')`; map backend 422 fields without resetting input.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/alarms/__tests__/AlarmConfigForm.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/alarms
git commit -m "feat(web): add administrator alarm configuration"
```

### Task 5: Reduced Motion and Footer Integration

**Files:**
- Create: `packages/smart_pid_web/src/features/alarms/useReducedMotion.ts`
- Modify: `packages/smart_pid_web/src/features/dashboard/AlarmFooterBar.tsx`
- Test: `packages/smart_pid_web/src/features/alarms/__tests__/AlarmFooterIntegration.test.tsx`

- [ ] **Step 1: Write both motion-path tests**

```tsx
stubReducedMotion(false); expect(await screen.findByTestId('count-critical')).toHaveClass('alarm-blink');
stubReducedMotion(true); expect(await screen.findByTestId('unacked-badge-critical')).toHaveTextContent('1');
expect(screen.getByTestId('alarm-bar-live')).toHaveAttribute('aria-live','assertive');
```

- [ ] **Step 2: Implement static fallback**

Under `prefers-reduced-motion: reduce`, suppress blink/transition and render an unacked count badge plus persistent border/weight. Add last-alarm text to full footer; preserve phase-4 mobile count chip and `ACK ALL` name.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/alarms/__tests__/AlarmFooterIntegration.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/alarms packages/smart_pid_web/src/features/dashboard/AlarmFooterBar.tsx
git commit -m "feat(web): complete reduced-motion alarm feedback"
```

### Task 6: Re-green Alarms E2E

**Files:** Modify `packages/smart_pid_web/e2e/alarms.spec.ts`.

- [ ] **Step 1: Patch `/auth/me`, monotonic WS sequence, and resync mocks**
- [ ] **Step 2: Run phase gate**

Run: `npm run test:e2e -- e2e/alarms.spec.ts`
Expected: PASS.

Run: `npm run test && npm run typecheck && npm run lint`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add packages/smart_pid_web/e2e/alarms.spec.ts
git commit -m "test(web): re-enable alarm lifecycle e2e"
```

## Interfaces exported (for later phases)

- `AlarmSeverity = 'CRITICAL'|'WARNING'|'ADVISORY'|'LOG'` and complete presentation map.
- `useAlarms`, `AlarmPanel`, `AlarmHistory`, `AlarmConfigForm`, `useReducedMotion`.
- Footer keeps `count-{severity}`, `unacked-badge-{severity}`, `alarm-count-chip`, `alarm-bar-live`, and `ACK ALL` contracts.
