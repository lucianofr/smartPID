# Phase 4 — Shell, Login, and Operational Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-enable the first frontend E2E slice with authenticated routing, the Recorder/Phosphor application shell, the operational dashboard, live trend signature, faceplate, and responsive alarm footer.

**Architecture:** `src/app/routes.tsx` is the single route/navigation registry. Thin pages compose `src/features/dashboard`; REST seeds data and the phase-3 realtime layer advances it. The phase-2 primitives and tokens are consumed without adding raw colors.

**Tech Stack:** React 18, React Router 6, TanStack Query 5, uPlot, Tailwind v4, Vitest/Testing Library, Playwright.

## Global Constraints

- UI copy and accessible names remain pt-BR: `Usuário`, `Senha`, `Entrar`, `Salvar`, `Fechar`.
- Recorder is default; Phosphor glow is a halo pass; `ctx.shadowBlur` is forbidden.
- Cards never wrap; faceplate is ~320 px; all interactive targets are at least 44×44 px.
- Add `GET /api/auth/me` mocks with `{user_id:1,username:'admin',role:'admin'}` to every phase-4 E2E harness.
- WebSocket fixtures increment `seq`; constant `seq: 1` is forbidden because phase-3 gap detection would force resync.

---

### Task 1: Route Registry and App Shell

**Files:**
- Create: `packages/smart_pid_web/src/app/routes.tsx`
- Create: `packages/smart_pid_web/src/app/AppShell.tsx`
- Create: `packages/smart_pid_web/src/app/AppShell.test.tsx`
- Modify: `packages/smart_pid_web/src/App.tsx`
- Modify: `packages/smart_pid_web/src/main.tsx`

**Interfaces:**
- Consumes: `ThemeProvider`, `AuthProvider`, `RouteGuard`, `RealtimeProvider`, `Command`, `DropdownMenu`.
- Produces:
```ts
export interface AppRoute {
  path: string;
  element: React.ComponentType;
  adminOnly?: boolean;
  nav?: { label: string; order: number };
  cfg?: { label: string; order: number };
  command?: { label: string; keywords?: readonly string[] };
}
export const appRoutes: AppRoute[];
```

- [ ] **Step 1: Write the failing registry/shell test**

```tsx
it('renders registry-backed top navigation and logout', () => {
  render(<TestProviders><AppShell><p>conteúdo</p></AppShell></TestProviders>);
  expect(screen.getByRole('link', { name: 'Loops' })).toHaveAttribute('href', '/');
  expect(screen.getByRole('button', { name: 'Comandos' })).toBeVisible();
  expect(screen.getByRole('button', { name: 'Configurações' })).toBeVisible();
  expect(screen.getByRole('button', { name: 'Sair' })).toBeVisible();
});
```

- [ ] **Step 2: Verify failure**

Run: `npm run test -- src/app/AppShell.test.tsx`
Expected: FAIL because `AppShell` and `appRoutes` do not exist.

- [ ] **Step 3: Implement the frozen registry contract**

```tsx
export const appRoutes: AppRoute[] = [{
  path: '/', element: DashboardPage,
  nav: { label: 'Loops', order: 10 },
  command: { label: 'Ir para Malhas', keywords: ['loops', 'malhas'] },
}];
```

`AppShell` sorts `nav` and `cfg` entries by `order`, renders a top bar, opens the command palette with the `k` key outside editable fields, and calls `logout()` from `AuthContext` on `Sair`.

- [ ] **Step 4: Compose providers and guarded routes**

```tsx
<ThemeProvider><QueryClientProvider client={queryClient}><AuthProvider>
  <BrowserRouter><RealtimeProvider><Routes>{appRoutes.map(toRoute)}</Routes></RealtimeProvider></BrowserRouter>
</AuthProvider></QueryClientProvider></ThemeProvider>
```

- [ ] **Step 5: Run test and commit**

Run: `npm run test -- src/app/AppShell.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/app packages/smart_pid_web/src/{App.tsx,main.tsx}
git commit -m "feat(web): add registry-backed application shell"
```

### Task 2: Login and Protected Routing

**Files:**
- Create: `packages/smart_pid_web/src/pages/LoginPage.tsx`
- Create: `packages/smart_pid_web/src/pages/LoginPage.test.tsx`
- Modify: `packages/smart_pid_web/src/app/routes.tsx`

**Interfaces:** Consumes `useAuth().login(username,password)` and `RouteGuard`. Produces `/login` public route.

- [ ] **Step 1: Write failing login tests**

```tsx
it('submits Portuguese-labelled credentials', async () => {
  renderLogin();
  await userEvent.type(screen.getByLabelText('Usuário'), 'admin');
  await userEvent.type(screen.getByLabelText('Senha'), 'admin');
  await userEvent.click(screen.getByRole('button', { name: 'Entrar' }));
  expect(login).toHaveBeenCalledWith('admin', 'admin');
});
```

- [ ] **Step 2: Run the focused test**

Run: `npm run test -- src/pages/LoginPage.test.tsx`
Expected: FAIL because the page is absent.

- [ ] **Step 3: Implement login and deep-link restoration**

```tsx
<form onSubmit={submit}>
  <Field label="Usuário"><input autoComplete="username" value={username} onChange={onUser}/></Field>
  <Field label="Senha"><input type="password" autoComplete="current-password" value={password} onChange={onPassword}/></Field>
  <Button type="submit">Entrar</Button>
</form>
```

On 401 render `Usuário ou senha inválidos`; after success navigate to `location.state.from ?? '/'`. Protected routes wrap their element with `<RouteGuard adminOnly={route.adminOnly}>`.

- [ ] **Step 4: Verify and commit**

Run: `npm run test -- src/pages/LoginPage.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/pages/LoginPage* packages/smart_pid_web/src/app/routes.tsx
git commit -m "feat(web): restore authenticated login flow"
```

### Task 3: Loop Cards and Dashboard Data

**Files:**
- Create: `packages/smart_pid_web/src/features/dashboard/LoopCard.tsx`
- Create: `packages/smart_pid_web/src/features/dashboard/LoopCard.test.tsx`
- Create: `packages/smart_pid_web/src/features/dashboard/useControllers.ts`
- Create: `packages/smart_pid_web/src/pages/DashboardPage.tsx`

**Interfaces:**
```ts
export interface LoopCardProps {
  controller: ControllerResponse;
  status: StatusData | null;
  onOpenConfig(id: number): void;
  controlsSlot?: React.ReactNode;
}
```

- [ ] **Step 1: Write failing card behavior test**

```tsx
it('renders live values and emits configure id', async () => {
  render(<LoopCard controller={controller} status={status} onOpenConfig={open}/>);
  expect(screen.getByText('PIC-005')).toBeVisible();
  expect(screen.getByText('AUTO', { selector: 'span.numeric' })).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Configurar PIC-005' }));
  expect(open).toHaveBeenCalledWith(5);
});
```

- [ ] **Step 2: Implement the single-row card strip**

```tsx
<div className="relative after:pointer-events-none after:absolute after:right-0 after:inset-y-0 after:w-8 after:bg-[linear-gradient(to_right,transparent,var(--bg))]">
  <div className="flex flex-nowrap gap-3 overflow-x-auto">{controllers.map(renderCard)}</div>
</div>
```

Each card uses `AnalogBar` for PV/SP/CO, `Badge` for mode, `--alarm-*` border only during alarm, and has no sparkline.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/dashboard/LoopCard.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/dashboard packages/smart_pid_web/src/pages/DashboardPage.tsx
git commit -m "feat(web): add live operational loop cards"
```

### Task 4: Trend Signature and Faceplate

**Files:**
- Create: `packages/smart_pid_web/src/features/dashboard/TrendPanel.tsx`
- Create: `packages/smart_pid_web/src/features/dashboard/TrendPanel.test.tsx`
- Create: `packages/smart_pid_web/src/features/dashboard/Faceplate.tsx`
- Create: `packages/smart_pid_web/src/features/dashboard/Faceplate.test.tsx`

**Interfaces:**
```ts
export interface TrendPanelProps { controllerId: number; scale: Scale; }
export interface FaceplateProps { controllerId: number; tag: string; description?: string; scale: Scale; decimals?: number; }
```

- [ ] **Step 1: Write tests for the signature invariants**

```tsx
expect(source).not.toContain('shadowBlur');
expect(screen.getByLabelText('Janela de tempo')).toHaveValue(30);
expect(screen.getByLabelText('Autoescala')).toBeChecked();
expect(screen.queryByRole('button', { name: 'Apply tuning' })).not.toBeInTheDocument(); // user role
```

- [ ] **Step 2: Implement TrendPanel**

Use `createWindowBuffer`, append `status` frames, pass `buffer.values()` plus `buffer.latest()` to `Trend`, pass AI event timestamps as `aiTicks`, and set `glow={theme === 'phosphor'}`. Controls are number + `segundo|minuto|hora`, auto-scale, manual PV/CO bounds, and `Exportar CSV` using a Blob of exactly the plotted rows.

- [ ] **Step 3: Implement Faceplate**

Render PV/SP/CO `Readout` + `AnalogBar`, mode as `span.numeric`, IAE and `2σ/Range`. Keep AUTO/MAN/SP/CO controls present for both roles; hide `Apply tuning` unless `useCan('tuning.edit')`.

- [ ] **Step 4: Verify and commit**

Run: `npm run test -- src/features/dashboard/TrendPanel.test.tsx src/features/dashboard/Faceplate.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/dashboard
git commit -m "feat(web): add recorder trend and responsive faceplate"
```

### Task 5: Alarm Footer and Responsive Layout

**Files:**
- Create: `packages/smart_pid_web/src/features/dashboard/useAlarmCounts.ts`
- Create: `packages/smart_pid_web/src/features/dashboard/AlarmFooterBar.tsx`
- Create: `packages/smart_pid_web/src/features/dashboard/AlarmFooterBar.test.tsx`
- Modify: `packages/smart_pid_web/src/pages/DashboardPage.tsx`

**Interfaces:**
```ts
export interface AlarmFooterBarProps { className?: string; }
export function useAlarmCounts(): {
  buckets: Record<AlarmSeverity,{active:number;unacked:number}>;
  totalUnacked: number;
  lastEvent: AlarmEventData | null;
};
```

- [ ] **Step 1: Write quiet/alarm/mobile tests**

```tsx
expect(screen.getByTestId('count-critical')).toHaveStyle({ color: 'var(--text-soft)' });
expect(screen.getByRole('button', { name: 'ACK ALL' })).toBeDisabled();
setViewport(767); expect(screen.getByTestId('alarm-count-chip')).toBeVisible();
```

- [ ] **Step 2: Implement four buckets and ACK ALL**

Use `CRIT/WARN/ADV/LOG`; color a bucket only while it has unacknowledged alarms. Wire `ACK ALL` to `POST /alarms/ack-all`, invalidate `queryKeys.alarmsActive`; hide it below 768 px where one count chip remains.

- [ ] **Step 3: Implement layout breakpoints**

At ≥1024 px, trend and fixed 320 px faceplate sit side by side (trend ≥65% at 1440). Below 1024 faceplate stacks. Below 768 cards remain horizontal and alarm footer collapses. 320 px retains monitoring, acknowledgement, and SP entry.

- [ ] **Step 4: Verify and commit**

Run: `npm run test -- src/features/dashboard/AlarmFooterBar.test.tsx src/pages/DashboardPage.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/dashboard packages/smart_pid_web/src/pages/DashboardPage.tsx
git commit -m "feat(web): add responsive alarm footer"
```

### Task 6: Rewrite and Re-green Phase-4 E2E

**Files:**
- Modify: `packages/smart_pid_web/e2e/login-dashboard.spec.ts`
- Modify: `packages/smart_pid_web/e2e/faceplate.spec.ts`
- Modify: `packages/smart_pid_web/e2e/responsive.spec.ts`
- Modify: `packages/smart_pid_web/e2e/target-size.spec.ts`
- Modify: `packages/smart_pid_web/e2e/fatia7-auth-negative.spec.ts`
- Rewrite: `packages/smart_pid_web/e2e/themes.spec.ts`

- [ ] **Step 1: Patch all auth and WebSocket fixtures**

Every mock API handles `/api/auth/me`; every emitted envelope advances `seq` monotonically. Mock all §7 resync endpoints when a gap is intentionally tested.

- [ ] **Step 2: Rewrite the theme matrix**

```ts
const THEMES = ['recorder', 'phosphor', 'isa101'] as const;
test('persists explicit theme', async ({ page }) => {
  await selectTheme(page, 'phosphor');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'phosphor');
});
```

Snapshots remain deferred to phase 11.

- [ ] **Step 3: Run phase gate**

Run: `npm run test:e2e -- e2e/login-dashboard.spec.ts e2e/faceplate.spec.ts e2e/responsive.spec.ts e2e/target-size.spec.ts e2e/fatia7-auth-negative.spec.ts e2e/themes.spec.ts`
Expected: all phase-4 specs PASS.

Run: `npm run test && npm run typecheck && npm run lint`
Expected: all commands exit 0.

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_web/e2e
git commit -m "test(web): re-enable dashboard e2e coverage"
```

## Interfaces exported (for later phases)

- `AppRoute` and mutable `appRoutes` use the exact contract in Task 1. Later phases append one literal and lazy import.
- `LoopCardProps`, `TrendPanelProps`, `FaceplateProps`, `AlarmFooterBarProps`, and `useAlarmCounts()` use the exact signatures above.
- Phase 5 replaces `controlsSlot` with `CardControls` and mounts `LoopConfigDialog` from selected `configId`.
- Phase 6 preserves `ACK ALL`, bucket test IDs, and the active-alarm query key while adding alarm history and per-row acknowledgement.
