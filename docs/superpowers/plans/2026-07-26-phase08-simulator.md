# Phase 8 — Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the simulator and twin trend while exposing only SP/mode/CO operation to the `user` role and keeping plant-model configuration administrator-only.

**Architecture:** A typed simulator API and status query feed a control panel and live twin trend. The Sim page is visible to both roles; 403 from `/simulator/status` produces a designed operator state, while permitted twin commands remain available from loop operation surfaces.

**Tech Stack:** React 18, TanStack Query, phase-2 Trend/Slider/Switch/Select, phase-3 realtime/apiClient/useCan, Vitest, Playwright.

## Global Constraints

- Extend capability actions with `simulator.configure` (admin-only); `user` permissions remain unchanged.
- Sim page is not admin-route-guarded because twin SP/mode/CO are user capabilities.
- Admin-only: start/stop, OPC-UA server, preset, process parameters, disturbance, PID enable/params, auto-SP, auto-disturbance.

---

### Task 1: Simulator API and Capability

**Files:**
- Create: `packages/smart_pid_web/src/features/simulator/api.ts`
- Create: `packages/smart_pid_web/src/features/simulator/types.ts`
- Modify: `packages/smart_pid_web/src/auth/useCan.ts`
- Modify: `packages/smart_pid_web/src/auth/useCan.test.ts`

- [ ] **Step 1: Write capability test**

```ts
expect(can('admin','simulator.configure')).toBe(true);
expect(can('user','simulator.configure')).toBe(false);
expect(can('user','loop.operate')).toBe(true);
```

- [ ] **Step 2: Add exact typed endpoints**

```ts
export const simulatorApi={
 status:()=>apiClient.get('/simulator/status'),
 start:()=>apiClient.post('/simulator/start',{}),
 stop:()=>apiClient.post('/simulator/stop',{}),
 preset:(preset:string)=>apiClient.post('/simulator/preset',{preset}),
 parameters:(body:SimulatorParameters)=>apiClient.put('/simulator/parameters',body),
 disturbance:(body:SimulatorDisturbance)=>apiClient.post('/simulator/disturbance',body),
};
```

Also map `/simulator/{id}/pid/sp`, `/pid/mode`, and `/co` to operator calls.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/auth/useCan.test.ts`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/auth packages/smart_pid_web/src/features/simulator
git commit -m "feat(web): define simulator API and permission"
```

### Task 2: Status and Banner

**Files:**
- Create: `packages/smart_pid_web/src/features/simulator/useSimulatorStatus.ts`
- Create: `packages/smart_pid_web/src/features/simulator/SimulationModeBanner.tsx`
- Test: `packages/smart_pid_web/src/features/simulator/useSimulatorStatus.test.tsx`

- [ ] **Step 1: Write 403 designed-state test**

```tsx
server.use(status403); renderHookWithRole('user');
expect(await screen.findByText('Simulador gerenciado pelo administrador')).toBeVisible();
```

- [ ] **Step 2: Implement query and banner**

Admin polls `/simulator/status`; user treats 403 as `restricted`, not a generic crash. Banner displays `SIMULAÇÃO ATIVA` only when running and is mounted on simulator/dashboard twin views.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/simulator/useSimulatorStatus.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/simulator
git commit -m "feat(web): add simulator status and role state"
```

### Task 3: Administrator Control Panel

**Files:**
- Create: `packages/smart_pid_web/src/features/simulator/SimulatorControlPanel.tsx`
- Create: `packages/smart_pid_web/src/features/simulator/StartStopControl.tsx`
- Create: `packages/smart_pid_web/src/features/simulator/PresetSelector.tsx`
- Create: `packages/smart_pid_web/src/features/simulator/DynamicsSliders.tsx`
- Create: `packages/smart_pid_web/src/features/simulator/DisturbanceControls.tsx`
- Create: `packages/smart_pid_web/src/features/simulator/AutoToggles.tsx`
- Create: `packages/smart_pid_web/src/features/simulator/TwinOutputModeControl.tsx`
- Test: `packages/smart_pid_web/src/features/simulator/__tests__/SimulatorControlPanel.test.tsx`

- [ ] **Step 1: Write role test**

```tsx
renderPanel({role:'user'});
for(const name of ['Iniciar simulador','Preset','Aplicar parâmetros','Injetar distúrbio'])
 expect(screen.queryByRole('button',{name})).toBeNull();
```

- [ ] **Step 2: Port exact controls/ranges from current modules**

Keep stateful REST invalidation after every mutation. Preserve current presets, process gain/time constants/dead time bounds, disturbance value, auto-SP and auto-disturbance toggles. Gate the whole configuration region with `simulator.configure`.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/simulator/__tests__/SimulatorControlPanel.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/simulator
git commit -m "feat(web): restore simulator control panel"
```

### Task 4: Twin Trend and Route

**Files:**
- Create: `packages/smart_pid_web/src/features/simulator/twinTrend.ts`
- Create: `packages/smart_pid_web/src/features/simulator/TwinTrend.tsx`
- Create: `packages/smart_pid_web/src/pages/SimulatorPage.tsx`
- Modify: `packages/smart_pid_web/src/app/routes.tsx`

- [ ] **Step 1: Write frame conversion test**

```ts
expect(toTwinPoint(frame)).toEqual({x:Date.parse(frame.timestamp)/1000,pv:50,sp:55,co:40});
```

- [ ] **Step 2: Render phase-2 Trend and register route**

```ts
appRoutes.push({path:'/simulator',element:SimulatorPage,
 nav:{label:'Sim',order:40},command:{label:'Ir para Simulador',keywords:['sim','twin']}});
```

Use `useRealtime(loopId,'status')`, phase-3 window buffer, theme glow rules, and AI ticks if emitted.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/simulator/twinTrend.test.ts`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/simulator packages/smart_pid_web/src/pages/SimulatorPage.tsx packages/smart_pid_web/src/app/routes.tsx
git commit -m "feat(web): add live simulator twin page"
```

### Task 5: Re-green Simulator E2E

**Files:** Modify `packages/smart_pid_web/e2e/simulator.spec.ts`.

- [ ] **Step 1: Add `/auth/me`, monotonic `seq`, and resync mocks**
- [ ] **Step 2: Preserve stateful mutation/refetch assertions**
- [ ] **Step 3: Run gate**

Run: `npm run test:e2e -- e2e/simulator.spec.ts`
Expected: PASS.

Run: `npm run test && npm run typecheck && npm run lint`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_web/e2e/simulator.spec.ts
git commit -m "test(web): re-enable simulator e2e"
```

## Interfaces exported (for later phases)

- Capability `simulator.configure` is admin-only.
- `simulatorApi`, `useSimulatorStatus`, `SimulationModeBanner`, `SimulatorControlPanel`, `TwinTrend`.
- Route `/simulator`, nav label `Sim`.
