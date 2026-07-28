import { expect, test } from '@playwright/test';
import { mockRest, stubWebSocket } from './helpers/harness';

// Negative-auth e2e.
//
// NOTE: the brief's `request.get('/api/project/list') -> 401` test stays DROPPED. This repo's e2e
// has NO backend — Playwright auto-starts only Vite, so a bare /api request hits a dead proxy
// (ECONNREFUSED / 5xx), not a 401. The 401 contract is covered by the backend pytest contract
// tests, which is the right layer. Here we only assert the UI-level guard.
//
// No session is seeded, so `RouteGuard` has nothing to authenticate and bounces every protected
// path (including unknown ones, which the catch-all route resolves inside the guarded layout).
// Route stubs stay NARROW: a broad `**/api/**` glob would also swallow Vite's own /src/api/*
// module scripts, blank the SPA and break the redirect.

test('unauthenticated UI is redirected to /login', async ({ page }) => {
  await mockRest(page);
  await page.goto('/projects');

  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole('button', { name: 'Entrar' })).toBeVisible();
});

test('the dashboard itself is guarded', async ({ page }) => {
  await mockRest(page);
  await page.goto('/');

  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByLabel('Usuário')).toBeVisible();
});

test('logging in after a blocked deep link lands inside the shell', async ({ page }) => {
  await stubWebSocket(page);
  await mockRest(page);

  await page.goto('/');
  await expect(page).toHaveURL(/\/login/);
  await page.getByLabel('Usuário').fill('admin');
  await page.getByLabel('Senha').fill('pw');
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('link', { name: 'Loops' })).toBeVisible();
});
