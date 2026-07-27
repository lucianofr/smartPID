import { expect, test } from '@playwright/test';
import { faceplate, mockRest, stubWebSocket, type HarnessLoop } from './helpers/harness';

// Phase 4 — the authenticated entry path: pt-BR login form → guarded dashboard →
// first live status frame. No backend: REST is stubbed per route and the socket is
// replaced in an init script (monotonic `seq`, see helpers/harness.ts).

const PIC005: HarnessLoop = {
  id: 5,
  name: 'PIC-005',
  description: 'Pressure',
  euMin: 0,
  euMax: 200,
  unit: '°C',
  pv: 150.2,
  sp: 152,
  co: 64,
  mode: 'AUTO',
};

test.beforeEach(async ({ page }) => {
  await stubWebSocket(page, { loops: [PIC005] });
  await mockRest(page, { loops: [PIC005] });
});

test('login then dashboard receives a status frame', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Usuário').fill('admin');
  await page.getByLabel('Senha').fill('pw');
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page.getByText('PIC-005').first()).toBeVisible();
  await expect(page.getByText('150.2').first()).toBeVisible();
  await expect(faceplate(page, 'PIC-005')).toBeVisible();
});

test('the shell exposes registry navigation and logout', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Usuário').fill('admin');
  await page.getByLabel('Senha').fill('pw');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.getByText('PIC-005').first()).toBeVisible();

  await expect(page.getByRole('link', { name: 'Loops' })).toHaveAttribute('href', '/');
  await expect(page.getByRole('button', { name: 'Configurações' })).toBeVisible();

  // The palette is gone: a bare `k` over a live process must do nothing.
  await page.getByText('PIC-005').first().click();
  await page.keyboard.press('k');
  await expect(page.getByRole('dialog')).toHaveCount(0);

  await page.getByRole('button', { name: 'Sair' }).click();
  await expect(page).toHaveURL(/\/login/);
});

test('bad credentials keep the operator on the form with the pt-BR message', async ({ page }) => {
  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ status: 401, json: { detail: 'Invalid credentials' } }),
  );

  await page.goto('/login');
  await page.getByLabel('Usuário').fill('admin');
  await page.getByLabel('Senha').fill('errada');
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page.getByRole('alert')).toHaveText('Usuário ou senha inválidos');
  await expect(page).toHaveURL(/\/login/);
});
