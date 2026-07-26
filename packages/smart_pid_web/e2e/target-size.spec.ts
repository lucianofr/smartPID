import { test } from '@playwright/test';
import { assertMinTarget } from './helpers/targetSize';
import { FIC101, faceplate, gotoDashboard, loopCard } from './helpers/harness';

// Spec §8.3 / design-system §9: every interactive control on a control station
// reaches >=44x44 CSS px. Phase 4 enforces the full floor (the pre-rewrite 24px
// interim is gone — the phase-2 primitives ship min-h-11/min-w-11 by default).

const SPEC_MIN = 44;
const MAN_LOOP = { ...FIC101, mode: 'MAN' };

test.describe('target size (>=44x44)', () => {
  test.beforeEach(async ({ page }) => {
    await gotoDashboard(page, { loops: [MAN_LOOP], width: 1440, height: 900 });
  });

  test('shell chrome clears the floor', async ({ page }) => {
    await assertMinTarget(page.getByRole('link', { name: 'Loops' }), SPEC_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'Comandos' }), SPEC_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'Configurações' }), SPEC_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'Sair' }), SPEC_MIN);
  });

  test('card, trend and alarm controls clear the floor', async ({ page }) => {
    const card = loopCard(page, 'FIC-101');
    await assertMinTarget(card.getByRole('button', { name: 'Abrir FIC-101' }), SPEC_MIN);
    await assertMinTarget(card.getByRole('button', { name: 'Configurar FIC-101' }), SPEC_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'Exportar CSV' }), SPEC_MIN);
    await assertMinTarget(page.getByRole('combobox', { name: 'Unidade da janela' }), SPEC_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'ACK ALL' }), SPEC_MIN);
  });

  test('faceplate operator controls clear the floor', async ({ page }) => {
    const fp = faceplate(page, 'FIC-101');
    await assertMinTarget(fp.getByRole('button', { name: 'AUTO' }), SPEC_MIN);
    await assertMinTarget(fp.getByRole('button', { name: 'MAN' }), SPEC_MIN);
    await assertMinTarget(fp.getByRole('button', { name: 'Set setpoint' }), SPEC_MIN);
    await assertMinTarget(fp.getByRole('button', { name: 'Set output' }), SPEC_MIN);
    await assertMinTarget(fp.getByRole('button', { name: 'Apply tuning' }), SPEC_MIN);
    // The slider ROW is the 44px target at >=1024; the phase-2 thumb is a
    // deliberate compact 16px pointer handle there (it grows to 44 below 1024,
    // asserted in the touch describe below).
    await assertMinTarget(page.getByTestId('manual-co-slider'), SPEC_MIN);
  });
});

// Below the 1024 breakpoint the full floor applies to the thumb itself — the
// touch case the compact desktop handle is exempted from.
test.describe('target size (>=44x44) — touch below 1024', () => {
  test('the CO slider thumb grows to the touch floor', async ({ page }) => {
    await gotoDashboard(page, { loops: [MAN_LOOP], width: 768, height: 1100 });
    await assertMinTarget(
      faceplate(page, 'FIC-101').getByRole('slider', { name: 'Manual CO' }),
      SPEC_MIN,
    );
  });
});
