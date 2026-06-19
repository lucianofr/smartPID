# Task 8 Report — API client + AuthContext + LoginPage

Branch: `feat/web-fatia01-foundation-dashboard` (worktree `.worktrees/main-web-hmi`)
Scope: `packages/smart_pid_web/` only.

## Files created (6)
- `packages/smart_pid_web/src/api/client.ts` — `ApiError{status,detail}`, `setTokenGetter`, `apiGet`/`apiPost`. `/api` prefix, `Authorization: Bearer <token>` when a token is present, `Content-Type: application/json`. On non-ok: parses `detail` from JSON body (string or stringified), falls back to `res.statusText`; `204` returns `undefined`.
- `packages/smart_pid_web/src/api/queryClient.ts` — TanStack Query v5 `QueryClient` (retry 1, staleTime 5000, refetchOnWindowFocus false).
- `packages/smart_pid_web/src/auth/AuthContext.tsx` — `AuthProvider` + `useAuth` → `{ token, isAuthenticated, login(user,pass), logout() }`. Token in `sessionStorage` key `smart-pid-token`. `login` calls `apiPost('/auth/login', {username, password})`. Wires `setTokenGetter(() => token)` so `client.ts` reads the live token.
- `packages/smart_pid_web/src/auth/RequireAuth.tsx` — redirect to `/login` (`<Navigate replace state={{from}} />`) when not authenticated.
- `packages/smart_pid_web/src/auth/LoginPage.tsx` — 360px centered card, PT-BR labels (Usuário/Senha/Entrar), `role="alert"` error line, design-system CSS vars.
- `packages/smart_pid_web/src/auth/AuthContext.test.tsx` — 2 tests (mocks `globalThis.fetch`).

Not wired into router/App (deferred to the app-shell task), as instructed.

## TDD
RED (Step 2): `Failed to resolve import "./AuthContext"` — confirmed before implementing.
GREEN (Step 8): 2 passed after implementation + one test-isolation fix.

### Test output (verbatim, GREEN)
```
 ✓ src/auth/AuthContext.test.tsx (2 tests) 36ms
 Test Files  1 passed (1)
      Tests  2 passed (2)
```
Full suite (regression check):
```
 ✓ src/lib/format.test.ts (3 tests) 4ms
 ✓ src/auth/AuthContext.test.tsx (2 tests) 32ms
 Test Files  2 passed (2)
      Tests  5 passed (5)
```

### Build (verbatim)
```
> tsc -b && vite build
✓ 30 modules transformed.
dist/assets/index-BPp-gYhQ.js  142.52 kB │ gzip: 45.77 kB
✓ built in 866ms
```
Clean — zero type errors under strict + noUnusedLocals + noUnusedParameters.

## Two strict fixes applied
1. `AuthContext.tsx`: removed unused `useCallback` from the import (brief listed it but it is unused → `noUnusedLocals`). Final import: `createContext, useContext, useMemo, useState, type ReactNode`.
2. `RequireAuth.tsx`: brief used `React.ReactNode` without importing `React` (out of scope under react-jsx runtime) → changed to `import { type ReactNode } from 'react'` and annotated `children: ReactNode`. No other `React.X` usages elsewhere.

## Additional fix (test isolation)
First GREEN run: the 401 test failed `expect(isAuthenticated).toBe(false)` because jsdom persists `sessionStorage` across tests in a file — the first test's `jwt-123` leaked into the second test's `AuthProvider` mount initializer. Added `sessionStorage.clear()` to the test `afterEach` (test-only; source contract unchanged). The binding-contract assertion `.rejects.toThrow('Invalid credentials')` passed on the first GREEN run already, confirming `apiPost` throws `ApiError(detail)`.

## Self-review
- Bearer header: `Authorization: Bearer ${token}` set only when token present — OK.
- sessionStorage key: exactly `smart-pid-token` — OK.
- ApiError detail parsing: JSON `detail` (string or `JSON.stringify`), fallback `statusText` — OK.
- Strict build: clean — OK.
- Unused imports: removed (`useCallback`) — OK.
- Nothing wired prematurely: `AuthProvider`/`RequireAuth`/`LoginPage` not imported by App/router — OK.
- Commit staged only 6 source/test files (no unrelated deleted pytest artifacts; `dist/`+`*.tsbuildinfo` are gitignored) — OK.

## Commit
`bfcae54 feat(web): API client, AuthContext (POST /auth/login), RequireAuth, LoginPage`

## Concerns
- None blocking. Minor: brief's stock test had no `sessionStorage.clear()`; added it for isolation. Login response `token_type` is read into the typed interface but not used (matches contract).
