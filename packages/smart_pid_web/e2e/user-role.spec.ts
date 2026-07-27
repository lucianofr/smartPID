import { expect, test, type Page } from '@playwright/test';
import { FIC101, TIC202, faceplate, gotoDashboard, loopCard } from './helpers/harness';

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

// ---------------------------------------------------------------------------
// The tests above assert what a `user` can SEE. These assert what a `user` can
// DO — every one of them drives a real click and then checks the wire or the
// resulting DOM state. A regression that leaves an enabled control on screen
// but stops it reaching the API passes every `toBeVisible` in this file and
// fails here.
// ---------------------------------------------------------------------------

/** Commands the app actually put on the wire, in order. */
function recordCommands(page: Page): string[] {
  const seen: string[] = [];
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    if (request.method() === 'POST' && path.startsWith('/api/commands/')) {
      seen.push(`${path} ${JSON.stringify(request.postDataJSON())}`);
    }
  });
  return seen;
}

test('user writes setpoint, mode and manual output to the API', async ({ page }) => {
  const commands = recordCommands(page);
  // Manual output is locked outside MAN and the stubbed socket keeps replaying
  // the fixture's mode, so the loop has to START in MAN for CO to be drivable.
  await gotoDashboard(page, { role: 'user', loops: [{ ...FIC101, mode: 'MAN' }] });

  await page.getByRole('spinbutton', { name: 'Setpoint' }).fill('57');
  await page.getByRole('button', { name: 'Set setpoint' }).click();
  await expect
    .poll(() => commands)
    .toContain('/api/commands/setpoint {"controller_id":1,"value":57}');

  const output = page.getByRole('button', { name: 'Set output' });
  await expect(output).toBeEnabled();
  await page.getByRole('spinbutton', { name: 'Saída' }).fill('12');
  await output.click();
  await expect
    .poll(() => commands)
    .toContain('/api/commands/output {"controller_id":1,"value":12}');

  await page.getByRole('combobox', { name: 'Mode' }).selectOption('AUTO');
  await expect
    .poll(() => commands)
    .toContain('/api/commands/mode {"controller_id":1,"mode":"AUTO"}');
});

test('user reaches the faceplate AUTO/MAN buttons and they command', async ({ page }) => {
  const commands = recordCommands(page);
  await gotoDashboard(page, { role: 'user' });

  const modes = faceplate(page, 'FIC-101').getByRole('group', { name: 'Modo do controlador' });
  await modes.getByRole('button', { name: 'MAN', exact: true }).click();
  await expect
    .poll(() => commands)
    .toContain('/api/commands/mode {"controller_id":1,"mode":"MAN"}');

  await modes.getByRole('button', { name: 'AUTO', exact: true }).click();
  await expect
    .poll(() => commands)
    .toContain('/api/commands/mode {"controller_id":1,"mode":"AUTO"}');
});

test('every loop card offers a live [cfg] for a user — no dead control', async ({ page }) => {
  await gotoDashboard(page, { role: 'user', loops: [FIC101, TIC202] });

  for (const tag of [FIC101.name, TIC202.name]) {
    const trigger = loopCard(page, tag).getByRole('button', { name: `Configurar ${tag}` });
    await expect(trigger).toBeEnabled();
    await trigger.click();

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    // Opening it is the point; CRUD staying absent is E2E-043.
    await expect(dialog.getByRole('button', { name: 'Salvar' })).toHaveCount(0);
    await expect(dialog.getByRole('button', { name: 'Excluir' })).toHaveCount(0);

    await dialog.getByRole('button', { name: 'Cancelar' }).click();
    await expect(dialog).toHaveCount(0);
  }
});

test('user opens the [cfg] menu, gets every theme and no Administração', async ({ page }) => {
  await gotoDashboard(page, { role: 'user' });

  const trigger = page.getByRole('button', { name: 'Configurações' });
  await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  await trigger.click();

  const menu = page.getByRole('menu');
  await expect(menu).toBeVisible();
  await expect(menu.getByText('Tema')).toBeVisible();
  await expect(menu.getByRole('menuitemradio')).toHaveText(['Recorder', 'Phosphor', 'ISA-101']);

  // The menu is the only route to the theme picker, so hiding the admin block
  // must not cost a user the ability to change theme.
  await expect(menu.getByText('Administração')).toHaveCount(0);
  for (const label of ['Projects', 'Settings', 'Connection', 'Users']) {
    await expect(menu.getByRole('menuitem', { name: label })).toHaveCount(0);
  }

  await menu.getByRole('menuitemradio', { name: 'ISA-101' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'isa101');
  expect(await page.evaluate(() => localStorage.getItem('spid.theme'))).toBe('isa101');
});

test('admin keeps the Administração block in the same [cfg] menu', async ({ page }) => {
  await gotoDashboard(page, { role: 'admin' });

  await page.getByRole('button', { name: 'Configurações' }).click();
  const menu = page.getByRole('menu');
  await expect(menu.getByText('Administração')).toBeVisible();
  await expect(menu.getByRole('menuitemradio')).toHaveCount(3);
  for (const label of ['Projects', 'Settings', 'Connection', 'Users']) {
    await expect(menu.getByRole('menuitem', { name: label })).toBeVisible();
  }
});
