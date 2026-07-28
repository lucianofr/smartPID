# Phase 5 — Loop Configuration, Commands, and AI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore loop operation and administrator-only tuning/AI surfaces while proving the new `user` role can operate but cannot configure.

**Architecture:** TanStack mutations call REST and invalidate canonical query keys. `CardControls` fills phase-4's `controlsSlot`; `LoopConfigDialog` owns controller configuration; `AiPanel` owns optimizer state and log display. Backend authorization remains the security boundary.

**Tech Stack:** React 18, TanStack Query, phase-2 primitives, phase-3 `apiClient`/`useCan`, Vitest, Playwright.

## Global Constraints

- `user`: SP, mode, manual CO. `admin`: tuning, AI, controller CRUD and configuration.
- 403 → toast `sem permissão` + refetch `/auth/me`; 409 preserves form; 422 maps fields.
- Every destructive write requires confirmation.

---

### Task 1: Validation and Command Mutations

**Files:**
- Create: `packages/smart_pid_web/src/features/loop-config/types.ts`
- Create: `packages/smart_pid_web/src/features/loop-config/validation.ts`
- Create: `packages/smart_pid_web/src/features/loop-config/commandApi.ts`
- Create: `packages/smart_pid_web/src/features/loop-config/useCommands.ts`
- Test: `packages/smart_pid_web/src/features/loop-config/__tests__/validation.test.ts`
- Test: `packages/smart_pid_web/src/features/loop-config/__tests__/useCommands.test.tsx`

**Interfaces:** POST `/commands/setpoint`, `/commands/mode`, `/commands/output`, `/commands/tuning`, `/commands/apply-tuning/{id}`.

- [ ] **Step 1: Write boundary tests**

```ts
expect(validateSetpoint(-1, {min:0,max:100})).toBe('Setpoint deve estar entre 0 e 100');
expect(validateOutput(101)).toBe('Saída deve estar entre 0 e 100');
expect(validateTuning({kp:0,ti:0,td:-1})).toEqual({kp:'Kp deve ser maior que 0',ti:'Ti deve ser maior que 0',td:'Td não pode ser negativo'});
```

- [ ] **Step 2: Verify failure**

Run: `npm run test -- src/features/loop-config/__tests__/validation.test.ts`
Expected: FAIL because the module is absent.

- [ ] **Step 3: Implement typed mutations**

```ts
export const setpoint = (controllerId:number, value:number) =>
  apiClient.post('/commands/setpoint', { controller_id: controllerId, value });
export const mode = (controllerId:number, value:LoopMode) =>
  apiClient.post('/commands/mode', { controller_id: controllerId, mode: value });
export const output = (controllerId:number, value:number) =>
  apiClient.post('/commands/output', { controller_id: controllerId, value });
```

On success invalidate controller/status keys. Route `ApiError.status===403` through `handleForbidden`; keep inputs intact for 409/422.

- [ ] **Step 4: Verify and commit**

Run: `npm run test -- src/features/loop-config/__tests__/validation.test.ts src/features/loop-config/__tests__/useCommands.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/loop-config
git commit -m "feat(web): add typed loop command mutations"
```

### Task 2: Card Controls and Operational Commands

**Files:**
- Create: `packages/smart_pid_web/src/features/loop-config/CardControls.tsx`
- Create: `packages/smart_pid_web/src/features/loop-config/__tests__/CardControls.test.tsx`
- Modify: `packages/smart_pid_web/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Write behavior tests**

```tsx
await userEvent.type(screen.getByRole('spinbutton', { name: 'Setpoint' }), '60');
await userEvent.click(screen.getByRole('button', { name: 'Set setpoint' }));
expect(setpoint).toHaveBeenCalledWith(5, 60);
expect(screen.getByRole('button', { name: 'Set output' })).toBeDisabled();
```

- [ ] **Step 2: Implement controls**

Keep native mode `<select aria-label="Mode">`; keep button names `Set setpoint` and `Set output` for retained E2E. Enable CO only in MAN. Mount as `controlsSlot` on the selected phase-4 `LoopCard`/faceplate.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/loop-config/__tests__/CardControls.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/loop-config/CardControls* packages/smart_pid_web/src/pages/DashboardPage.tsx
git commit -m "feat(web): restore operator loop controls"
```

### Task 3: Loop Configuration Dialog

**Files:**
- Create: `packages/smart_pid_web/src/features/loop-config/LoopConfigDialog.tsx`
- Create: `packages/smart_pid_web/src/features/loop-config/__tests__/LoopConfigDialog.test.tsx`
- Modify: `packages/smart_pid_web/src/pages/DashboardPage.tsx`

**Interfaces:** `useCan('controllers.manage')`, generated controller schemas.

- [ ] **Step 1: Write supervisory/DDC visibility tests**

```tsx
renderDialog({ modo_execucao:'SUPERVISORY' });
for (const name of DDC_SECTIONS) expect(screen.queryByRole('region',{name})).not.toBeInTheDocument();
await userEvent.selectOptions(screen.getByLabelText('Modo de execução'), 'DDC');
for (const name of DDC_SECTIONS) expect(screen.getByRole('region',{name})).toBeVisible();
```

`DDC_SECTIONS` is exactly: `PID Tuning`, `Scaling & Limits`, `Filters & IO`, `Shed & Safety`, `PID Structure`, `Integral Type`.

- [ ] **Step 2: Implement form**

Always render name, description, execution mode, scan rate and NodeIDs PV/SP/CO/Ti. Render the six DDC sections only for DDC. Controller create/edit/delete is hidden unless `controllers.manage`; deletion uses a critical confirmation dialog.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/loop-config/__tests__/LoopConfigDialog.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/loop-config/LoopConfigDialog* packages/smart_pid_web/src/pages/DashboardPage.tsx
git commit -m "feat(web): add role-gated loop configuration"
```

### Task 4: AI Panel and Tuning Confirmation

**Files:**
- Create: `packages/smart_pid_web/src/features/loop-config/AiPanel.tsx`
- Create: `packages/smart_pid_web/src/features/loop-config/ConfirmApplyTuningDialog.tsx`
- Create: `packages/smart_pid_web/src/features/loop-config/useAiControls.ts`
- Test: `packages/smart_pid_web/src/features/loop-config/__tests__/AiPanel.test.tsx`

- [ ] **Step 1: Write failing role and lifecycle tests**

```tsx
renderAi({role:'user'}); expect(screen.queryByRole('button',{name:'Start'})).not.toBeInTheDocument();
renderAi({role:'admin'}); await userEvent.click(screen.getByRole('button',{name:'Start'}));
expect(startAi).toHaveBeenCalledWith(5);
```

- [ ] **Step 2: Implement panel**

Fields: engine `NONE|FUZZY|RL`, objective, process speed, dead time `L`, `ai_limit_min`, `ai_limit_max`. Buttons keep accessible names `Start`, `Pause`, `Stop`; optimizer state is independent from AUTO/MAN. Render `LOG.AI` events in a terminal-style `role="log"` box. `Apply tuning` opens a dialog; only `Confirm Write` POSTs `/commands/apply-tuning/{id}`.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/loop-config/__tests__/AiPanel.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/loop-config
git commit -m "feat(web): add AI lifecycle and tuning confirmation"
```

### Task 5: User-role E2E and Phase Gate

**Files:**
- Modify: `packages/smart_pid_web/e2e/fatia2-commands.spec.ts`
- Create: `packages/smart_pid_web/e2e/user-role.spec.ts`

- [ ] **Step 1: Fix retained WS fixtures**

Use monotonically increasing `seq`; mock `/api/auth/me` and the complete resync set. Do not leave a second constant `seq:1` frame.

- [ ] **Step 2: Add full user-role spec**

```ts
test('user operates but cannot configure', async ({page}) => {
  await mockMe(page, 'user'); await login(page);
  await expect(page.getByRole('spinbutton',{name:'Setpoint'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Apply tuning'})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Start',exact:true})).toHaveCount(0);
});
```

Add a forced 403 route for an admin mutation and assert toast text `sem permissão` plus a second `/api/auth/me` request.

- [ ] **Step 3: Run phase gate**

Run: `npm run test:e2e -- e2e/fatia2-commands.spec.ts e2e/user-role.spec.ts`
Expected: PASS.

Run: `npm run test && npm run typecheck && npm run lint`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_web/e2e
git commit -m "test(web): cover commands and user role gating"
```

## Interfaces exported (for later phases)

- `validateSetpoint`, `validateOutput`, `validateTuning`; typed `useCommands(controllerId)`.
- `CardControls`, `LoopConfigDialog`, `AiPanel`, `ConfirmApplyTuningDialog` are phase-owned exports.
- Admin-only surfaces use `tuning.edit`, `ai.control`, or `controllers.manage`; operator commands use `loop.operate`.
