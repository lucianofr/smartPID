import { expect, test } from '@playwright/test';
import { TIC202, emitFrames, faceplate, gotoDashboard, settleForShot } from './helpers/harness';

// Phase 4 — the faceplate is part of the dashboard layout (§6.9), not a dialog:
// at >=1024 it sits beside the trend at a fixed ~320px. Everything asserted in
// the first five tests is functional; the last one is the 13th and final §6.8
// visual baseline (phase 11).

test('faceplate renders PV/SP/CO, mode control and the stats block', async ({ page }) => {
  await gotoDashboard(page);

  const fp = faceplate(page, 'FIC-101');
  await expect(fp).toBeVisible();

  await expect(fp.getByText('SUPERVISORY')).toBeVisible();
  await expect(fp.locator('span.numeric', { hasText: /^AUTO$/ })).toBeVisible();
  await expect(fp.getByRole('group', { name: 'Modo do controlador' })).toHaveCount(0);
  await expect(fp.getByRole('meter', { name: 'PV' })).toHaveAttribute('aria-valuenow', '50');
  await expect(fp.getByRole('meter', { name: 'SP' })).toHaveAttribute('aria-valuenow', '55');
  await expect(fp.getByRole('meter', { name: 'CO' })).toHaveAttribute('aria-valuenow', '42');
  await expect(fp.getByText('IAE')).toBeVisible();
  await expect(fp.getByText('2σ/Range')).toBeVisible();
});

test('a SUPERVISORY loop hides every operator control for a user', async ({ page }) => {
  await gotoDashboard(page, { role: 'user' });
  const fp = faceplate(page, 'FIC-101');
  await expect(fp.getByRole('button', { name: 'AUTO' })).toHaveCount(0);
  await expect(fp.getByRole('button', { name: 'MAN' })).toHaveCount(0);
  await expect(fp.getByLabel('Setpoint')).toHaveCount(0);
  await expect(fp.getByRole('button', { name: 'Set setpoint' })).toHaveCount(0);
  await expect(fp.getByRole('button', { name: 'Set output' })).toHaveCount(0);
  await expect(fp.getByLabel('Escrever Kp')).toHaveCount(0);
});

test('a SUPERVISORY loop offers manual tuning entry to an admin but no setpoint control', async ({
  page,
}) => {
  await gotoDashboard(page, { role: 'admin' });
  const fp = faceplate(page, 'FIC-101');
  await expect(fp.getByLabel('Escrever Kp')).toBeVisible();
  await expect(fp.getByRole('button', { name: 'Set setpoint' })).toHaveCount(0);
});

test('operator controls are present for a DDC loop', async ({ page }) => {
  await gotoDashboard(page, { loops: [TIC202], role: 'user' });
  const fp = faceplate(page, 'TIC-202');
  await expect(fp.getByRole('button', { name: 'AUTO' })).toBeVisible();
  await expect(fp.getByRole('button', { name: 'MAN' })).toBeVisible();
  await expect(fp.getByLabel('Setpoint')).toBeVisible();
  await expect(fp.getByRole('button', { name: 'Set setpoint' })).toBeVisible();
  await expect(fp.getByRole('button', { name: 'Set output' })).toBeVisible();
});

test('admin sees Apply tuning', async ({ page }) => {
  await gotoDashboard(page, { role: 'admin' });
  await expect(faceplate(page, 'FIC-101').getByRole('button', { name: 'Apply tuning' })).toBeVisible();
});

test('a mode press posts the command for the selected loop', async ({ page }) => {
  await gotoDashboard(page, { loops: [TIC202] });
  const posted: string[] = [];
  await page.route('**/api/commands/mode', async (route) => {
    posted.push(route.request().postData() ?? '');
    await route.fulfill({ json: { ok: true } });
  });

  await faceplate(page, 'TIC-202').getByRole('button', { name: 'MAN' }).click();
  await expect.poll(() => posted).toEqual([JSON.stringify({ controller_id: TIC202.id, mode: 'MAN' })]);
});

test('the manual output is locked while the loop is in AUTO', async ({ page }) => {
  await gotoDashboard(page, { loops: [TIC202] });
  await expect(faceplate(page, 'TIC-202').getByRole('button', { name: 'Set output' })).toBeDisabled();
});

test.describe('visual baseline', () => {
  test.use({ timezoneId: 'UTC' });

  test('the default faceplate matches its recorded appearance', async ({ page }) => {
    await gotoDashboard(page, { samples: 0, wave: 1 });
    await emitFrames(page, 24);
    await settleForShot(page);
    await expect(faceplate(page, 'FIC-101')).toHaveScreenshot('faceplate-default.png');
  });
});
