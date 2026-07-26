# Phase 10 — Settings, Connection, Projects, and Users Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore backend settings, OPC-UA connection/tag browsing, portable `.spid` project management, and add the administrator-only users management surface.

**Architecture:** Four cfg-menu features consume typed generated APIs and share phase-3 error handling. All routes and menu entries are admin-only; direct backend authorization remains mandatory.

**Tech Stack:** React 18, TanStack Query, phase-2 forms/dialogs, phase-3 apiClient/useCan, Vitest, Playwright.

## Global Constraints

- Cfg menu entries: Projects, Settings, Connection, Users; all hidden for `user`.
- Project download relies on phase-1 WAL checkpoint; client does not duplicate it.
- Delete confirmations use `--alarm-crit`; no raw red.

---

### Task 1: Settings

**Files:**
- Create: `packages/smart_pid_web/src/features/settings/settingsTypes.ts`
- Create: `packages/smart_pid_web/src/features/settings/useSettings.ts`
- Create: `packages/smart_pid_web/src/features/settings/SettingsForm.tsx`
- Create: `packages/smart_pid_web/src/pages/SettingsPage.tsx`
- Test: `packages/smart_pid_web/src/features/settings/SettingsForm.test.tsx`

- [ ] **Step 1: Write role and persistence tests**

```tsx
renderSettings('user'); expect(screen.queryByRole('form',{name:'Configurações'})).toBeNull();
renderSettings('admin'); await userEvent.click(screen.getByRole('button',{name:'Salvar'}));
expect(save).toHaveBeenCalledWith(expect.objectContaining({db_flush_interval_s:5}));
```

- [ ] **Step 2: Port current settings fields and validation**

Gate with `settings.manage`; map 422 field errors and preserve values.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/settings/SettingsForm.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/settings packages/smart_pid_web/src/pages/SettingsPage.tsx
git commit -m "feat(web): restore application settings"
```

### Task 2: OPC-UA Connection and Tag Browser

**Files:**
- Create: `packages/smart_pid_web/src/features/connection/opcuaApi.ts`
- Create: `packages/smart_pid_web/src/features/connection/useOpcua.ts`
- Create: `packages/smart_pid_web/src/features/connection/ConnectionPanel.tsx`
- Create: `packages/smart_pid_web/src/features/connection/TagBrowser.tsx`
- Create: `packages/smart_pid_web/src/pages/ConnectionPage.tsx`
- Test: `packages/smart_pid_web/src/features/connection/ConnectionPanel.test.tsx`

- [ ] **Step 1: Write state and browse tests**

```tsx
expect(screen.getByText('ONLINE')).toBeVisible();
await userEvent.click(screen.getByRole('button',{name:'Navegar tags'}));
await userEvent.type(screen.getByRole('searchbox'),'MAIN.PV');
expect(search).toHaveBeenCalledWith('MAIN.PV');
```

- [ ] **Step 2: Implement real routes**

GET `/opcua/status`; PUT `/opcua/endpoint`; POST `/opcua/connect|disconnect`; GET `/opcua/browse/{node_id}` and `/opcua/search?q=`. Display OFFLINE/ONLINE/RECONNECTING states and a searchable modal tree.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/connection/ConnectionPanel.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/connection packages/smart_pid_web/src/pages/ConnectionPage.tsx
git commit -m "feat(web): restore OPC-UA connection and tag browser"
```

### Task 3: Portable Projects and Welcome Gate

**Files:**
- Create: `packages/smart_pid_web/src/features/projects/projectApi.ts`
- Create: `packages/smart_pid_web/src/features/projects/useProjects.ts`
- Create: `packages/smart_pid_web/src/features/projects/ProjectList.tsx`
- Create: `packages/smart_pid_web/src/features/projects/ProjectImportDropzone.tsx`
- Create: `packages/smart_pid_web/src/features/projects/WelcomeDialog.tsx`
- Create: `packages/smart_pid_web/src/features/projects/WelcomeGate.tsx`
- Create: `packages/smart_pid_web/src/pages/ProjectsPage.tsx`
- Modify: `packages/smart_pid_web/src/app/AppShell.tsx`

- [ ] **Step 1: Write complete lifecycle test**

```tsx
await userEvent.click(screen.getByRole('button',{name:'Novo projeto'})); expect(create).toHaveBeenCalled();
await userEvent.click(screen.getByRole('button',{name:'Baixar'})); expect(download).toHaveBeenCalled();
await userEvent.click(screen.getByRole('button',{name:'Excluir'}));
expect(screen.getByRole('dialog')).toHaveTextContent('Excluir projeto');
```

- [ ] **Step 2: Implement exact routes**

GET `/project/current|list|download`; POST `/project/new|open|import`; DELETE `/project/{name}`. `WelcomeGate` mounts inside authenticated `AppShell`, admin-only, and suppresses itself after `sessionStorage['spid.welcome-seen']='1'`.

- [ ] **Step 3: Verify and commit**

Run: `npm run test -- src/features/projects/ProjectList.test.tsx src/features/projects/WelcomeDialog.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/projects packages/smart_pid_web/src/pages/ProjectsPage.tsx packages/smart_pid_web/src/app/AppShell.tsx
git commit -m "feat(web): restore portable project management"
```

### Task 4: Users Management

**Files:**
- Create: `packages/smart_pid_web/src/features/users/usersApi.ts`
- Create: `packages/smart_pid_web/src/features/users/UsersPanel.tsx`
- Create: `packages/smart_pid_web/src/features/users/UserDialog.tsx`
- Create: `packages/smart_pid_web/src/features/users/UsersPanel.test.tsx`
- Create: `packages/smart_pid_web/src/pages/UsersPage.tsx`

**Interfaces:** phase-0 GET/POST `/users`; PATCH/DELETE `/users/{user_id}`; roles `admin|user`.

- [ ] **Step 1: Write CRUD and last-admin tests**

```tsx
await userEvent.click(screen.getByRole('button',{name:'Novo usuário'}));
await userEvent.type(screen.getByLabelText('Usuário'),'operador');
await userEvent.selectOptions(screen.getByLabelText('Perfil'),'user');
await userEvent.click(screen.getByRole('button',{name:'Salvar'}));
expect(create).toHaveBeenCalledWith({username:'operador',password:expect.any(String),role:'user'});
```

Mock 409 and assert `Não é possível desativar o último administrador`; form stays editable. Support role change, soft deactivation/reactivation and password change.

- [ ] **Step 2: Verify and commit**

Run: `npm run test -- src/features/users/UsersPanel.test.tsx`
Expected: PASS.

```bash
git add packages/smart_pid_web/src/features/users packages/smart_pid_web/src/pages/UsersPage.tsx
git commit -m "feat(web): add administrator user management"
```

### Task 5: Register Cfg Routes and Re-green E2E

**Files:**
- Modify: `packages/smart_pid_web/src/app/routes.tsx`
- Modify: `packages/smart_pid_web/e2e/fatia7-connection.spec.ts`
- Modify: `packages/smart_pid_web/e2e/fatia7-projects.spec.ts`

- [ ] **Step 1: Append registry entries**

```ts
appRoutes.push(
 {path:'/projects',element:ProjectsPage,adminOnly:true,cfg:{label:'Projects',order:10},command:{label:'Projetos'}},
 {path:'/settings',element:SettingsPage,adminOnly:true,cfg:{label:'Settings',order:20},command:{label:'Configurações'}},
 {path:'/connection',element:ConnectionPage,adminOnly:true,cfg:{label:'Connection',order:30},command:{label:'Conexão'}},
 {path:'/users',element:UsersPage,adminOnly:true,cfg:{label:'Users',order:40},command:{label:'Usuários'}},
);
```

Visibility table: admin sees all four; user sees none. Direct navigation by user renders 403/redirect via RouteGuard.

- [ ] **Step 2: Patch E2E harnesses**

Add `/api/auth/me`, monotonic WS sequence and complete resync mocks; preserve existing route/copy assertions. Replace the old “users panel absent” assertion with the admin management expectation in component coverage.

- [ ] **Step 3: Run gate**

Run: `npm run test:e2e -- e2e/fatia7-connection.spec.ts e2e/fatia7-projects.spec.ts`
Expected: PASS.

Run: `npm run test && npm run typecheck && npm run lint`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add packages/smart_pid_web/src/app/routes.tsx packages/smart_pid_web/e2e
git commit -m "test(web): re-enable connection and project e2e"
```

## Interfaces exported (for later phases)

- `SettingsForm`, `ConnectionPanel`, `TagBrowser`, `ProjectList`, `WelcomeGate`, `UsersPanel`.
- Frozen admin cfg routes: `/projects`, `/settings`, `/connection`, `/users`.
