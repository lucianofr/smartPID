import { expect, test } from '@playwright/test';
import { FIC101, faceplate, gotoDashboard, loopCard } from './helpers/harness';

// Spec §9 from the operator's side: `user` runs the loop, `admin` configures it.
// The gating asserted here is PRESENTATION ONLY — the backend re-enforces every
// route — so the last test drives a forced 403 to prove the §11 recovery path.

test('user operates the loop: setpoint, mode and manual output stay available', async ({ page }) => {
  await gotoDashboard(page, { role: 'user' });

  await expect(page.getByRole('spinbutton', { name: 'Setpoint' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Set setpoint' })).toBeVisible();
  await expect(page.getByRole('combobox', { name: 'Mode' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Set output' })).toBeVisible();
  await expect(faceplate(page, 'FIC-101').getByRole('slider', { name: 'Manual CO' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'ACK ALL' })).toBeVisible();
});

test('user cannot reach tuning, AI or controller management', async ({ page }) => {
  await gotoDashboard(page, { role: 'user' });
  await expect(page.getByRole('spinbutton', { name: 'Setpoint' })).toBeVisible();

  await expect(page.getByRole('button', { name: 'Apply tuning' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Start', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Pause', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Stop', exact: true })).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'Otimização IA' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Salvar IA' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Nova malha' })).toHaveCount(0);
});

test('the configuration dialog is read-only for a user', async ({ page }) => {
  await gotoDashboard(page, { role: 'user' });
  await loopCard(page, 'FIC-101').getByRole('button', { name: 'Configurar FIC-101' }).click();

  const dialog = page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel('Nome')).toBeDisabled();
  await expect(dialog.getByRole('button', { name: 'Salvar' })).toHaveCount(0);
  await expect(dialog.getByRole('button', { name: 'Excluir' })).toHaveCount(0);
  await expect(dialog.getByRole('button', { name: 'Cancelar' })).toBeVisible();
});

test('admin keeps the tuning and AI surfaces the user is denied', async ({ page }) => {
  await gotoDashboard(page, { role: 'admin' });

  await expect(page.getByRole('region', { name: 'Otimização IA' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Apply tuning' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Nova malha' })).toBeVisible();
});

test('a 403 on a write raises "sem permissão" and refetches /auth/me', async ({ page }) => {
  let meRequests = 0;
  page.on('request', (request) => {
    if (request.url().includes('/api/auth/me')) meRequests += 1;
  });

  await gotoDashboard(page, { role: 'user' });
  // Registered after the harness catch-all, so it wins for this one route.
  await page.route('**/api/commands/setpoint', (route) =>
    route.fulfill({ status: 403, json: { detail: 'requires admin role' } }),
  );

  const before = meRequests;
  await page.getByRole('spinbutton', { name: 'Setpoint' }).fill(String(FIC101.sp + 1));
  await page.getByRole('button', { name: 'Set setpoint' }).click();

  await expect(page.getByText(/sem permissão/i)).toBeVisible();
  // §11: a 403 may mean the role changed mid-session — the session is re-read.
  await expect.poll(() => meRequests).toBeGreaterThan(before);
});
