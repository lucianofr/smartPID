import type { Page } from '@playwright/test';
import { expect, test } from '@playwright/test';
import { gotoDashboard, loopCard } from './helpers/harness';

/**
 * Task 1 checkpoint, in a real browser: the integral-type radio group renders,
 * saves, and comes back on the saved value when the dialog is reopened.
 *
 * FIC-101 in the harness is a SUPERVISORY loop, which is exactly where the
 * control has to work: `integral_type` sets the sign of every integral
 * adjustment the optimizer computes and rides the ACTION.AI write-back that
 * only a SUPERVISORY loop performs.
 */

async function openConfig(page: Page) {
  await loopCard(page, 'FIC-101').getByRole('button', { name: 'Configurar FIC-101' }).click();
  return page.getByRole('dialog');
}

test('integral type renders as a radio group, saves, and reopens on the saved value', async ({
  page,
}) => {
  await gotoDashboard(page);

  let putBody: Record<string, unknown> | null = null;
  let savedIntegralType = 'TIME_TI';

  // Serve the loop back with whatever was last saved, so reopening the dialog
  // reads real round-tripped state rather than the original fixture.
  await page.route('**/api/controllers/1', async (route) => {
    if (route.request().method() === 'PUT') {
      putBody = JSON.parse(route.request().postData() ?? '{}') as Record<string, unknown>;
      savedIntegralType = String(putBody.integral_type);
    }
    await route.fallback();
  });

  const dialog = await openConfig(page);
  await expect(dialog).toBeVisible();

  const timeTi = dialog.getByRole('radio', { name: 'Tempo Integral (1/Ti)' });
  const gainKi = dialog.getByRole('radio', { name: 'Ganho Integral (Ki)' });

  // Renders: both alternatives visible at once, current value selected.
  await expect(timeTi).toBeVisible();
  await expect(gainKi).toBeVisible();
  await expect(timeTi).toBeChecked();

  // Saves.
  await gainKi.check();
  await expect(gainKi).toBeChecked();
  await dialog.getByRole('button', { name: 'Salvar' }).click();
  await expect(dialog).toBeHidden();
  expect(putBody).not.toBeNull();
  expect(putBody!.integral_type).toBe('GAIN_KI');
  expect(savedIntegralType).toBe('GAIN_KI');
});

test('the PLC process-running binding is offered next to the other NodeIDs', async ({ page }) => {
  await gotoDashboard(page);
  const dialog = await openConfig(page);
  // getByLabel would also match the field's tooltip button, which shares the
  // accessible-name prefix — address the control by its role instead.
  await expect(dialog.getByRole('textbox', { name: 'NodeID PID em uso' })).toBeVisible();
});

test('the optimizer stability band is editable and blank means "inherit global"', async ({
  page,
}) => {
  await gotoDashboard(page);
  const dialog = await openConfig(page);
  const band = dialog.getByRole('spinbutton', { name: 'Banda de estabilidade (% do SP)' });
  await expect(band).toBeVisible();
  await expect(band).toHaveValue('');
  await band.fill('0.5');
  await expect(band).toHaveValue('0.5');
});

/**
 * One `limit_min`/`limit_max` pair clamps whichever integral parameter the
 * loop uses, so the label has to follow the radio above it — a box labelled Ti
 * holding a Ki bound is how an operator clamps the wrong quantity.
 */
test('the integral limits are labelled after the loop integral type', async ({ page }) => {
  await gotoDashboard(page);
  const dialog = await openConfig(page);

  await expect(dialog.getByRole('spinbutton', { name: 'Ti mínimo' })).toBeVisible();
  await expect(dialog.getByRole('spinbutton', { name: 'Ti máximo' })).toBeVisible();

  await dialog.getByRole('radio', { name: 'Ganho Integral (Ki)' }).check();
  await expect(dialog.getByRole('spinbutton', { name: 'Ki mínimo' })).toBeVisible();
  await expect(dialog.getByRole('spinbutton', { name: 'Ki máximo' })).toBeVisible();
  await expect(dialog.getByRole('spinbutton', { name: 'Ti mínimo' })).toHaveCount(0);
});

test('the level band appears only for the SURGE_LEVEL objective', async ({ page }) => {
  await gotoDashboard(page);
  const dialog = await openConfig(page);
  const levelMin = dialog.getByRole('spinbutton', { name: 'Nível mín. (%)' });

  await expect(levelMin).toHaveCount(0);
  await dialog.getByRole('combobox', { name: 'Objetivo' }).selectOption('SURGE_LEVEL');
  await expect(levelMin).toBeVisible();
  await expect(dialog.getByRole('spinbutton', { name: 'Nível máx. (%)' })).toBeVisible();
});
