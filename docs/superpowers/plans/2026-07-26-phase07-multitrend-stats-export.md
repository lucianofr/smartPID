# Phase 7 — Multi-trend, Statistics, History, and Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore four-slot synchronized trends, historical windows, loop performance statistics, and create/download CSV export without inventing an export-history list.

**Architecture:** One page model owns four slots and one shared x-range. REST supplies history/stats/export jobs; realtime adds current samples. The phase-3 formatter is the only numeric formatter.

**Tech Stack:** React 18, uPlot, TanStack Query, phase-2 Trend, phase-3 window/format/apiClient, Vitest, Playwright.

## Global Constraints

- Maximum four controllers in a 2×2 grid.
- Pan/zoom synchronizes all occupied charts without a feedback loop.
- Export request uses `controller_id` singular, never `controller_ids`.
- No `GET /export/list` and no export-history UI (TD-008).

---

### Task 1: Four-slot Model

**Files:**
- Create: `packages/smart_pid_web/src/features/multitrend/types.ts`
- Create: `packages/smart_pid_web/src/features/multitrend/useMultiTrendModel.ts`
- Create: `packages/smart_pid_web/src/features/multitrend/SeriesSelector.tsx`
- Test: `packages/smart_pid_web/src/features/multitrend/useMultiTrendModel.test.tsx`

- [ ] **Step 1: Write slot invariant tests**

```ts
const {result}=renderHook(()=>useMultiTrendModel());
act(()=>result.current.assign(0, controllerA));
act(()=>result.current.toggleSeries(0,'co'));
expect(result.current.slots[0]).toMatchObject({controllerId:1,series:{pv:true,sp:true,co:false}});
expect(()=>result.current.assign(4,controllerA)).toThrow('slot must be between 0 and 3');
```

- [ ] **Step 2: Implement model**

```ts
export type Signal='pv'|'sp'|'co';
export interface TrendSlot { controllerId:number|null; series:Record<Signal,boolean>; }
```

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/multitrend/useMultiTrendModel.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/multitrend
git commit -m "feat(web): add four-slot multitrend model"
```

### Task 2: Feedback-safe Time Synchronization

**Files:**
- Create: `packages/smart_pid_web/src/features/multitrend/timeSync.ts`
- Create: `packages/smart_pid_web/src/features/multitrend/timeSync.test.ts`
- Create: `packages/smart_pid_web/src/features/multitrend/MultiTrendChart.tsx`

**Interfaces:**
```ts
export interface XRange { min:number; max:number; }
export interface SyncChart { id:string; setX(range:XRange):void; }
export function createTimeSync(): { register(chart:SyncChart):()=>void; publish(sourceId:string,range:XRange):void };
```

- [ ] **Step 1: Write feedback prevention test**

```ts
const sync=createTimeSync(); sync.register(a); sync.register(b);
sync.publish('a',{min:10,max:20});
expect(a.setX).not.toHaveBeenCalled(); expect(b.setX).toHaveBeenCalledOnce();
```

- [ ] **Step 2: Implement guard**

```ts
let broadcasting=false;
function publish(sourceId:string,range:XRange){
 if(broadcasting)return; broadcasting=true;
 try{for(const chart of charts.values())if(chart.id!==sourceId)chart.setX(range);}finally{broadcasting=false;}
}
```

Wire uPlot `hooks.setScale` for x only; programmatic sibling `setScale` is ignored while broadcasting.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/multitrend/timeSync.test.ts`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/multitrend
git commit -m "feat(web): synchronize multitrend time ranges"
```

### Task 3: History and Decimation

**Files:**
- Create: `packages/smart_pid_web/src/features/multitrend/useHistory.ts`
- Create: `packages/smart_pid_web/src/features/multitrend/HistoryQuery.tsx`
- Create: `packages/smart_pid_web/src/features/multitrend/decimate.ts`
- Test: `packages/smart_pid_web/src/features/multitrend/HistoryQuery.test.tsx`

- [ ] **Step 1: Write time-window request test**

```tsx
await userEvent.clear(screen.getByLabelText('Janela')); await userEvent.type(screen.getByLabelText('Janela'),'2');
await userEvent.selectOptions(screen.getByLabelText('Unidade'),'hora');
await userEvent.click(screen.getByRole('button',{name:'Carregar histórico'}));
expect(load).toHaveBeenCalledWith(expect.objectContaining({controllerId:1,hours:2}));
```

- [ ] **Step 2: Implement GET `/history/{controller_id}`**

Convert segundo/minuto/hora to ISO start/end or backend-supported `hours`. Decimate for display while retaining exact first/latest samples.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/multitrend/HistoryQuery.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/multitrend
git commit -m "feat(web): add multitrend history windows"
```

### Task 4: Statistics Panel

**Files:**
- Create: `packages/smart_pid_web/src/features/multitrend/useStats.ts`
- Create: `packages/smart_pid_web/src/features/multitrend/StatsPanel.tsx`
- Test: `packages/smart_pid_web/src/features/multitrend/StatsPanel.test.tsx`

**Interfaces:** GET `/stats/{controller_id}/stats`; render fields present in generated schema: IAE, ISE, ITAE, MSE, standard deviation, variability, and total variation.

- [ ] **Step 1: Write exact metric test**

```tsx
for(const label of ['IAE','ISE','ITAE','MSE','σ','2σ/SP','2σ/Range','TV'])
  expect(screen.getByText(label)).toBeVisible();
expect(screen.getByText('4.20')).toHaveClass('numeric');
```

- [ ] **Step 2: Implement using phase-3 format only**

Delete the old `features/multitrend/format.ts`; import `formatNumber`, `formatPercent`, `formatWithUnit` from `src/lib/format.ts`.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/multitrend/StatsPanel.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/multitrend
git commit -m "feat(web): restore loop statistics panel"
```

### Task 5: Create and Download Export

**Files:**
- Create: `packages/smart_pid_web/src/features/multitrend/useExport.ts`
- Create: `packages/smart_pid_web/src/features/multitrend/ExportButton.tsx`
- Test: `packages/smart_pid_web/src/features/multitrend/ExportButton.test.tsx`

- [ ] **Step 1: Write singular DTO test**

```ts
await createExport({controller_id:5,start:'2026-07-26T00:00:00Z',end:'2026-07-26T01:00:00Z'});
expect(fetchBody).toEqual({controller_id:5,start:'2026-07-26T00:00:00Z',end:'2026-07-26T01:00:00Z'});
expect(fetchBody).not.toHaveProperty('controller_ids');
```

- [ ] **Step 2: Implement job lifecycle**

POST `/export`; poll GET `/export/{export_id}` until complete/error; download `/export/{export_id}/download`. Render no list/history affordance.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/multitrend/ExportButton.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/multitrend
git commit -m "feat(web): add CSV export create and download"
```

### Task 6: Page, Route, and Phase Gate

**Files:**
- Create: `packages/smart_pid_web/src/pages/MultiTrendPage.tsx`
- Modify: `packages/smart_pid_web/src/app/routes.tsx`
- Modify: `packages/smart_pid_web/e2e/multitrend.spec.ts`

- [ ] **Step 1: Register route**

```ts
appRoutes.push({path:'/multitrend',element:MultiTrendPage,
 nav:{label:'Trends',order:20},command:{label:'Ir para Trends',keywords:['trend','tendência']}});
```

- [ ] **Step 2: Fix E2E fixtures**

Increment WebSocket `seq`; mock `/api/auth/me` and the full resync set. Preserve existing route `/multitrend` and accessible names.

- [ ] **Step 3: Run gate**

Run: `npm run test:e2e -- e2e/multitrend.spec.ts`
Expected: PASS.

Run: `npm run test && npm run typecheck && npm run lint`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_web/src/pages/MultiTrendPage.tsx packages/smart_pid_web/src/app/routes.tsx packages/smart_pid_web/e2e/multitrend.spec.ts
git commit -m "feat(web): ship synchronized multitrend workspace"
```

## Interfaces exported (for later phases)

- `Signal`, `TrendSlot`, `XRange`, `createTimeSync`, `useMultiTrendModel`, `useHistory`, `useStats`, `useExport`.
- Export DTO is permanently singular `controller_id`.
- `/multitrend` and top-nav label `Trends` are frozen.
