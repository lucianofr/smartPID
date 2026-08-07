import { test } from '@playwright/test';
import { assertMinTarget } from './helpers/targetSize';
import { faceplate, gotoDashboard, loopCard, TIC202 } from './helpers/harness';

// Spec §8.3 / design-system §9: every interactive control on a control station
// reaches >=44x44 CSS px. Phase 4 enforces the full floor (the pre-rewrite 24px
// interim is gone — the phase-2 primitives ship min-h-11/min-w-11 by default).

const SPEC_MIN = 44;
const MAN_LOOP = { ...TIC202, mode: 'MAN' };

test.describe('target size (>=44x44)', () => {
  test.beforeEach(async ({ page }) => {
    await gotoDashboard(page, { loops: [MAN_LOOP], width: 1440, height: 900 });
  });

  test('shell chrome clears the floor', async ({ page }) => {
    await assertMinTarget(page.getByRole('link', { name: 'Loops' }), SPEC_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'Configurações' }), SPEC_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'Sair' }), SPEC_MIN);
  });

  test('card, trend and alarm controls clear the floor', async ({ page }) => {
    const card = loopCard(page, 'TIC-202');
    await assertMinTarget(card.getByRole('button', { name: 'TIC-202', exact: true }), SPEC_MIN);
    await assertMinTarget(card.getByRole('button', { name: 'Configurar TIC-202' }), SPEC_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'Exportar CSV' }), SPEC_MIN);
    await assertMinTarget(page.getByRole('combobox', { name: 'Unidade da janela' }), SPEC_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'ACK ALL' }), SPEC_MIN);
  });

  test('faceplate operator controls clear the floor', async ({ page }) => {
    const fp = faceplate(page, 'TIC-202');
    await assertMinTarget(fp.getByRole('button', { name: 'AUTO' }), SPEC_MIN);
    await assertMinTarget(fp.getByRole('button', { name: 'MAN' }), SPEC_MIN);
    await assertMinTarget(fp.getByRole('button', { name: 'Set setpoint' }), SPEC_MIN);
    await assertMinTarget(fp.getByRole('button', { name: 'Set output' }), SPEC_MIN);
    await assertMinTarget(fp.getByRole('button', { name: 'Apply tuning' }), SPEC_MIN);
  });
});
