import { expect, test } from '@playwright/test';
import { FIC101, faceplate, gotoDashboard } from './helpers/harness';

// Phase 4 — the faceplate is part of the dashboard layout (§6.9), not a dialog:
// at >=1024 it sits beside the trend at a fixed ~320px. Visual baselines are
// deferred to phase 11; everything asserted here is functional.

test('faceplate renders PV/SP/CO, mode control and the stats block', async ({ page }) => {
  await gotoDashboard(page);

  const fp = faceplate(page, 'FIC-101');
  await expect(fp).toBeVisible();

  await expect(fp.getByRole('group', { name: 'Modo do controlador' })).toBeVisible();
  await expect(fp.getByRole('meter', { name: 'PV' })).toHaveAttribute('aria-valuenow', '50');
  await expect(fp.getByRole('meter', { name: 'SP' })).toHaveAttribute('aria-valuenow', '55');
  await expect(fp.getByRole('meter', { name: 'CO' })).toHaveAttribute('aria-valuenow', '42');
  await expect(fp.getByText('IAE')).toBeVisible();
  await expect(fp.getByText('2σ/Range')).toBeVisible();
});

test('operator controls are present for both roles; Apply tuning is admin-only', async ({
  page,
}) => {
  await gotoDashboard(page, { role: 'user' });
  const fp = faceplate(page, 'FIC-101');
  await expect(fp.getByRole('button', { name: 'AUTO' })).toBeVisible();
  await expect(fp.getByRole('button', { name: 'MAN' })).toBeVisible();
  await expect(fp.getByLabel('Setpoint')).toBeVisible();
  await expect(fp.getByRole('button', { name: 'Set setpoint' })).toBeVisible();
  await expect(fp.getByRole('slider', { name: 'Manual CO' })).toBeVisible();
  await expect(fp.getByRole('button', { name: 'Apply tuning' })).toHaveCount(0);
});

test('admin sees Apply tuning', async ({ page }) => {
  await gotoDashboard(page, { role: 'admin' });
  await expect(faceplate(page, 'FIC-101').getByRole('button', { name: 'Apply tuning' })).toBeVisible();
});

test('a mode press posts the command for the selected loop', async ({ page }) => {
  await gotoDashboard(page);
  const posted: string[] = [];
  await page.route('**/api/commands/mode', async (route) => {
    posted.push(route.request().postData() ?? '');
    await route.fulfill({ json: { ok: true } });
  });

  await faceplate(page, 'FIC-101').getByRole('button', { name: 'MAN' }).click();
  await expect.poll(() => posted).toEqual([JSON.stringify({ controller_id: FIC101.id, mode: 'MAN' })]);
});

test('the manual output is locked while the loop is in AUTO', async ({ page }) => {
  await gotoDashboard(page);
  await expect(faceplate(page, 'FIC-101').getByRole('button', { name: 'Set output' })).toBeDisabled();
});
