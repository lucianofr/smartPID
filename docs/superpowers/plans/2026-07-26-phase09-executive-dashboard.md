# Phase 9 — Executive Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore buyer-facing aggregate KPIs, bad-actor ranking, AI ROI, and backend health in the Recorder identity.

**Architecture:** Reuse AppShell rather than creating a second shell. REST seeds controllers/stats/OPC state; realtime `stats` and `system` envelopes overlay fresh values. The layout uses quieter, wider KPI composition but no separate visual language.

**Tech Stack:** React 18, TanStack Query, phase-2 Readout/Badge, phase-3 realtime/apiClient/format, Vitest, Playwright.

## Global Constraints

- Resolved §15 decision: reuse the operational shell. Rationale: shared navigation/session/alarm context and no evidence that a second shell improves the buyer workflow.
- Every numeral uses Geist Mono; no traffic-light green for healthy state.

---

### Task 1: Executive Data Model

**Files:**
- Create: `packages/smart_pid_web/src/features/executive/types.ts`
- Create: `packages/smart_pid_web/src/features/executive/useExecutiveData.ts`
- Test: `packages/smart_pid_web/src/features/executive/useExecutiveData.test.tsx`

- [ ] **Step 1: Write aggregation test**

```ts
expect(aggregate([{mode:'AUTO',ai:true,iae:10},{mode:'MAN',ai:false,iae:20}]))
 .toMatchObject({autoPercent:50,aiCoveragePercent:50,averageIae:15});
```

- [ ] **Step 2: Implement REST + realtime overlay**

Query `/controllers`, `/controllers/stats`, `/system/status`, `/opcua/status`; overlay keyed `stats` WS frames without mutating cached REST values.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/executive/useExecutiveData.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/executive
git commit -m "feat(web): aggregate executive dashboard data"
```

### Task 2: KPI and Bad Actor Surfaces

**Files:**
- Create: `packages/smart_pid_web/src/features/executive/ExecutiveKpiCard.tsx`
- Create: `packages/smart_pid_web/src/features/executive/BadActorsTable.tsx`
- Test: `packages/smart_pid_web/src/features/executive/ExecutiveKpiCard.test.tsx`

- [ ] **Step 1: Write exact labels test**

```tsx
for(const label of ['Malhas em AUTO','Cobertura da IA','IAE médio','Variabilidade 2σ/RANGE'])
 expect(screen.getByText(label)).toBeVisible();
expect(screen.getByTestId('kpi-auto').querySelector('.numeric')).not.toBeNull();
```

- [ ] **Step 2: Implement cards and ranking**

Rank descending by IAE then variability; click a row navigates to `/?loop=<id>`. Use token borders/surfaces only.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/executive/ExecutiveKpiCard.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/executive
git commit -m "feat(web): add executive KPI and bad actor views"
```

### Task 3: AI ROI and Backend Health

**Files:**
- Create: `packages/smart_pid_web/src/features/executive/AiRoiPanel.tsx`
- Create: `packages/smart_pid_web/src/features/executive/BackendHealthPanel.tsx`
- Test: `packages/smart_pid_web/src/features/executive/BackendHealthPanel.test.tsx`

- [ ] **Step 1: Write health rendering test**

```tsx
render(<BackendHealthPanel state={{cpu_percent:12.4,memory_percent:31.0,uptime_s:3661}}/>);
expect(screen.getByText('12.4%')).toHaveClass('numeric');
expect(screen.getByText('1 h 1 min')).toHaveClass('numeric');
```

- [ ] **Step 2: Implement panels**

AI ROI compares before/after aggregates only when available; otherwise `MissingState` explains insufficient data. Health uses system REST/WS CPU, RAM and uptime plus OPC state, with gray normal states and error token only for abnormal.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/executive/BackendHealthPanel.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/executive
git commit -m "feat(web): add AI ROI and backend health panels"
```

### Task 4: Page, Route, and E2E Gate

**Files:**
- Create: `packages/smart_pid_web/src/pages/ExecutiveDashboardPage.tsx`
- Modify: `packages/smart_pid_web/src/app/routes.tsx`
- Modify: `packages/smart_pid_web/e2e/executive-dashboard.spec.ts`

- [ ] **Step 1: Register command-only route**

```ts
appRoutes.push({path:'/executive',element:ExecutiveDashboardPage,
 command:{label:'Painel executivo',keywords:['executivo','kpi','roi']}});
```

The wordmark links to `/executive`; top operational navigation stays Loops/Trends/Alarms/Sim.

- [ ] **Step 2: Patch E2E harness**

Add `/api/auth/me`, monotonic WS `seq`, and complete resync mocks while preserving `/executive` and existing KPI assertions.

- [ ] **Step 3: Run gate**

Run: `npm run test:e2e -- e2e/executive-dashboard.spec.ts`
Expected: PASS.

Run: `npm run test && npm run typecheck && npm run lint`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_web/src/pages/ExecutiveDashboardPage.tsx packages/smart_pid_web/src/app/routes.tsx packages/smart_pid_web/e2e/executive-dashboard.spec.ts
git commit -m "feat(web): ship recorder executive dashboard"
```

## Interfaces exported (for later phases)

- `ExecutiveData`, `aggregate`, `useExecutiveData`, `ExecutiveKpiCard`, `BadActorsTable`, `AiRoiPanel`, `BackendHealthPanel`.
- Route `/executive`; no separate shell.
