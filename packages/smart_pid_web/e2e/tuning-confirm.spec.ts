import { expect, test, type Page } from '@playwright/test';
import { FIC101, mockRest, seedSession, stubWebSocket } from './helpers/harness';

// E2E-021 — the tuning confirmation gate.
//
// PRD-41 surfaces a backend-generated recommendation per loop; PRD-34 says the
// tuning is written ONLY after an explicit confirmation. This file guards the
// gate itself, so it is deliberately stricter than the smoke pass in
// fatia2-commands.spec.ts:
//
//   1. The gate is asserted on OBSERVED NETWORK TRAFFIC, never on a disabled
//      attribute. Every POST /commands/apply-tuning/* is recorded off
//      `page.on('request')`, which sees the request whatever handler ends up
//      fulfilling it — so wiring the button straight through to `applyTuning`
//      turns this file red even though the DOM would still look correct.
//   2. The before/after table is asserted on the RENDERED NUMBERS. A dialog
//      that opens but shows the wrong side of the comparison is not a
//      confirmation, it is a rubber stamp.
//   3. The post-write refetch is asserted through the REFETCHED PAYLOAD: the
//      recommendation route flips `status` to `applied` once a write landed,
//      so the affordance can only go disabled if the invalidation really
//      refetched. A bare request counter would pass on any stray fetch.
//
// Harness rules as everywhere else (helpers/harness.ts): no backend, GET
// /auth/me stubbed because `useCan` is deny-by-default, the whole §7 resync set
// stubbed because StrictMode's second mount always resyncs, and a monotonic
// `seq` socket so the tracker never sees a fake gap.

/** Distinct current/recommended values on every axis — a swapped column shows. */
const RECOMMENDATION = {
  controller_id: FIC101.id,
  current_kp: 1.4,
  current_ti: 42,
  current_td: 3.5,
  recommended_kp: 2.15,
  recommended_ti: 26.5,
  recommended_td: 5.25,
  reason: 'IMC/lambda sobre modelo FOPDT identificado (lambda = 12 s).',
  timestamp: 1750000000,
  status: 'pending',
  source: 'IMC',
} as const;

interface Wire {
  /** URLs of every POST /commands/apply-tuning/* the page actually put on the wire. */
  applies: string[];
  /** GET /commands/tuning-recommendations/* — the initial fetch plus every refetch. */
  recFetches: number;
}

interface TuningOptions {
  /** null serves 404 — "nothing pending", the state `getTuningRecommendation` expects. */
  recommendation?: typeof RECOMMENDATION | null;
}

/**
 * Records the tuning wire and serves both tuning routes.
 *
 * Registered AFTER `mockRest` so it beats that helper's `**\/api/commands/**`
 * catch-all: Playwright matches the most recently registered route first. It
 * must also be registered BEFORE the first navigation, otherwise the catch-all
 * answers the initial recommendation fetch with `{ ok: true }`.
 */
async function mockTuning(page: Page, options: TuningOptions = {}): Promise<Wire> {
  const recommendation = options.recommendation === undefined ? RECOMMENDATION : options.recommendation;
  const wire: Wire = { applies: [], recFetches: 0 };

  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().includes('/commands/apply-tuning/')) {
      wire.applies.push(request.url());
    }
  });

  await page.route('**/api/commands/tuning-recommendations/*', async (route) => {
    wire.recFetches += 1;
    if (recommendation === null) {
      await route.fulfill({ status: 404, json: { detail: 'no pending recommendation' } });
      return;
    }
    // Once a write has landed the backend marks the recommendation consumed.
    // Serving that here is what makes the post-write refetch observable in the DOM.
    await route.fulfill({
      json: { ...recommendation, status: wire.applies.length > 0 ? 'applied' : 'pending' },
    });
  });

  await page.route('**/api/commands/apply-tuning/*', (route) =>
    route.fulfill({ json: { ok: true, controller_id: FIC101.id, detail: null } }),
  );

  return wire;
}

async function gotoLoop(page: Page, role: 'admin' | 'user'): Promise<Wire> {
  await seedSession(page);
  await stubWebSocket(page, { loops: [FIC101] });
  await mockRest(page, { loops: [FIC101], role });
  const wire = await mockTuning(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await expect(page.getByText(FIC101.name).first()).toBeVisible();
  return wire;
}

const applyButton = (page: Page) => page.getByRole('button', { name: 'Apply tuning' });
const confirmButton = (page: Page) => page.getByRole('button', { name: 'Confirm Write' });

test.describe('E2E-021 tuning confirmation', () => {
  test('admin is offered the write and the dialog shows current vs recommended', async ({
    page,
  }) => {
    const wire = await gotoLoop(page, 'admin');

    // 1 — a pending recommendation enables the affordance for an admin.
    await expect(applyButton(page)).toBeEnabled();
    await expect.poll(() => wire.recFetches).toBeGreaterThan(0);
    expect(wire.applies).toEqual([]);

    await applyButton(page).click();

    // 2 — the confirmation is explicit: it names the loop, restates the target
    // parameters and puts current beside recommended for all three terms.
    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('heading', { name: `Aplicar sintonia — ${FIC101.name}` })).toBeVisible();
    await expect(dialog).toContainText(`Escrita direta no PID da malha #${FIC101.id}`);
    await expect(dialog).toContainText('Kp=2.15 Ti=26.5 Td=5.25');

    // The comparison grid in document order: header row, then Kp/Ti/Td rows as
    // label | current | recommended. Asserting the whole table at once catches a
    // swapped column, a dropped row and a stale number in one expectation.
    await expect(dialog.locator('div.grid > span')).toHaveText([
      '',
      'Atual',
      'Recomendado',
      'Kp',
      '1.4',
      '2.15',
      'Ti',
      '42',
      '26.5',
      'Td',
      '3.5',
      '5.25',
    ]);

    // The reason is the operator's only evidence for WHY the write is proposed.
    await expect(dialog).toContainText(RECOMMENDATION.reason);

    // 3 — the heart of E2E-021: opening the dialog wrote nothing.
    expect(wire.applies).toEqual([]);
  });

  test('no apply request is issued until Confirm Write, then exactly one', async ({ page }) => {
    const wire = await gotoLoop(page, 'admin');

    await applyButton(page).click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Give an ungated implementation every chance to fire: the dialog is fully
    // painted and the confirm control is interactive, and still nothing is on
    // the wire. This is the assertion that a `toBeDisabled()` check cannot make.
    await expect(confirmButton(page)).toBeEnabled();
    expect(wire.applies).toEqual([]);

    const fetchesBeforeConfirm = wire.recFetches;
    await confirmButton(page).click();

    // 4a — exactly one write, addressed to this loop.
    await expect
      .poll(() => wire.applies)
      .toEqual([expect.stringContaining(`/api/commands/apply-tuning/${FIC101.id}`)]);

    // The dialog closes on success and the operator is told the write landed.
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(page.getByText('Sintonia aplicada', { exact: true })).toBeVisible();

    // 4b — success invalidates/refetches the tuning query, and the refetched
    // payload (status `applied`) is what disables the affordance again. A gate
    // that posted but never invalidated leaves the button enabled here.
    await expect.poll(() => wire.recFetches).toBeGreaterThan(fetchesBeforeConfirm);
    await expect(applyButton(page)).toBeDisabled();

    // Still exactly one write after everything settled — no double submit.
    expect(wire.applies).toHaveLength(1);
  });

  test('cancelling closes the dialog and writes nothing', async ({ page }) => {
    const wire = await gotoLoop(page, 'admin');

    await applyButton(page).click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // 5 — the cancel path.
    await page.getByRole('button', { name: 'Cancelar' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(wire.applies).toEqual([]);

    // The recommendation survives the cancel: the gate is a stop, not a discard.
    await expect(applyButton(page)).toBeEnabled();
    await applyButton(page).click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Escape is the other way out of a Radix dialog, and it must not write either.
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(wire.applies).toEqual([]);
  });

  test('a user is not offered the apply affordance at all', async ({ page }) => {
    const wire = await gotoLoop(page, 'user');

    // 6 — `tuning.edit` is admin-only, so the control is absent rather than
    // merely disabled, and the recommendation is never even fetched.
    await expect(applyButton(page)).toHaveCount(0);
    await expect(page.getByTestId('ai-panel')).toHaveCount(0);
    expect(wire.recFetches).toBe(0);
    expect(wire.applies).toEqual([]);
  });

  test('without a pending recommendation the write stays unavailable', async ({ page }) => {
    await seedSession(page);
    await stubWebSocket(page, { loops: [FIC101] });
    await mockRest(page, { loops: [FIC101], role: 'admin' });
    const wire = await mockTuning(page, { recommendation: null });
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await expect(page.getByText(FIC101.name).first()).toBeVisible();

    // 404 = nothing pending. The button renders (the capability is there) but
    // there is nothing to confirm, so it cannot open the dialog.
    await expect(applyButton(page)).toBeDisabled();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    expect(wire.applies).toEqual([]);
  });
});
