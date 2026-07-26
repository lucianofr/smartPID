import { expect, test, type Page } from '@playwright/test';
import { FIC101, TIC202, faceplate, gotoDashboard } from './helpers/harness';

// §6.8 theme matrix. Three themes ship: recorder (default), phosphor, isa101.
// MD3 dark/light and Ocean are dropped; Dark Room is superseded by Phosphor, and
// stored legacy values migrate rather than silently falling back.
//
// FUNCTIONAL ONLY — visual baselines are deferred to phase 11, so the old 5x4
// screenshot matrix (and its snapshots) is gone.

const THEMES = ['recorder', 'phosphor', 'isa101'] as const;
const LOOPS = [FIC101, TIC202];

const THEME_LABEL: Record<(typeof THEMES)[number], string> = {
  recorder: 'Recorder',
  phosphor: 'Phosphor',
  isa101: 'ISA-101',
};

async function selectTheme(page: Page, theme: (typeof THEMES)[number]): Promise<void> {
  await page.getByRole('button', { name: 'Configurações' }).click();
  await page.getByRole('menuitemradio', { name: THEME_LABEL[theme] }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
}

test('recorder is the default when nothing is stored', async ({ page }) => {
  await gotoDashboard(page, { loops: LOOPS });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'recorder');
});

for (const theme of THEMES) {
  test(`persists an explicit ${theme} selection across a reload`, async ({ page }) => {
    await gotoDashboard(page, { loops: LOOPS });
    await selectTheme(page, theme);

    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    // The pre-paint script in index.html applies it before React mounts, so the
    // operator never flashes the default first.
    await expect(page.getByText('FIC-101').first()).toBeVisible();
  });

  test(`the dashboard renders under ${theme}`, async ({ page }) => {
    await gotoDashboard(page, { loops: LOOPS, theme });
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    await expect(page.getByText('FIC-101').first()).toBeVisible();
    await expect(page.getByRole('img', { name: 'Tendência FIC-101' })).toBeVisible();
    await expect(faceplate(page, 'FIC-101')).toBeVisible();
    await expect(page.getByRole('button', { name: 'ACK ALL' })).toBeVisible();
  });
}

test('the phosphor halo pass is on only under phosphor', async ({ page }) => {
  await gotoDashboard(page, { loops: LOOPS, theme: 'phosphor' });
  await expect(page.getByRole('img', { name: 'Tendência FIC-101' })).toHaveAttribute(
    'data-glow',
    'on',
  );

  await selectTheme(page, 'recorder');
  await expect(page.getByRole('img', { name: 'Tendência FIC-101' })).toHaveAttribute(
    'data-glow',
    'off',
  );
});

const LEGACY: ReadonlyArray<readonly [string, string]> = [
  ['dark-room', 'phosphor'],
  ['md3-dark', 'recorder'],
  ['md3-light', 'recorder'],
  ['ocean', 'recorder'],
  ['not-a-theme', 'recorder'],
];

for (const [stored, expected] of LEGACY) {
  test(`migrates the stored value ${stored} to ${expected}`, async ({ page }) => {
    await gotoDashboard(page, { loops: LOOPS, theme: stored });
    await expect(page.locator('html')).toHaveAttribute('data-theme', expected);
    const persisted = await page.evaluate(() => localStorage.getItem('spid.theme'));
    expect(persisted, 'the migration is written back once').toBe(expected);
  });
}
