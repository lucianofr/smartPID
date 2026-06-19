import { expect, test } from '@playwright/test';

// Fatia 7 — negative-auth e2e.
//
// NOTE: the brief's `request.get('/api/project/list') -> 401` test is intentionally DROPPED. This
// repo's e2e has NO backend — Playwright auto-starts only Vite, so a bare /api request hits a dead
// proxy (ECONNREFUSED / 5xx), not a 401. The 401 contract for unauthenticated /project/list is
// already covered by the backend pytest contract test from the previous task, which is the right
// layer for it. Here we only assert the UI-level guard.
//
// This test seeds NO token (no addInitScript), so RequireAuth has no session and redirects the
// protected UI route to /login. The redirect is client-side and fires before ProjectsPage mounts,
// so no /api fetch is ever issued — we intentionally register NO route stub. (A broad `**/api/**`
// stub is actively harmful here: Vite serves the app's own source modules from /src/api/*, and the
// glob would intercept those module scripts, blank the SPA, and break the redirect.)

test('unauthenticated UI is redirected to /login', async ({ page }) => {
  await page.goto('/projects');

  await expect(page).toHaveURL(/\/login/);
});
