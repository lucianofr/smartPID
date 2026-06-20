import { expect, test, type Page } from '@playwright/test';
import { assertMinTarget } from './helpers/targetSize';

// Responsive <1024 rules (Task 9.2 / design-system §9). Below the 1024 token breakpoint:
//  - the nav rail collapses to an icon-only 64px rail,
//  - the ControllerCard grid reflows to a single column (one card per row, full width),
//  - the faceplate dialog goes full-screen,
//  - interactive targets (nav items, mode buttons, ACK ALL, slider thumb) stay >=44x44.
//
// Harness mirrors target-size.spec.ts: no backend — /api/* is mocked via page.route and the
// WebSocket is stubbed via addInitScript so the dashboard renders a live status frame. The dashboard
// route `/` is RequireAuth-gated, so the token is seeded into sessionStorage before load and the
// post-login WelcomeDialog is suppressed.

const NAV_RAIL_COLLAPSED = 64;
const NAV_RAIL_EXPANDED = 224;
const TARGET_MIN = 44;

const CONTROLLERS = [
  { id: 1, name: 'FIC-101', description: 'Flow', pv_decimals: 1, pv_unit: '%', optimization_enabled: false },
  { id: 2, name: 'TIC-202', description: 'Temp', pv_decimals: 1, pv_unit: '°C', optimization_enabled: false },
];

async function mockRest(page: Page): Promise<void> {
  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ json: { access_token: 'jwt-e2e', token_type: 'bearer' } }),
  );
  await page.route('**/api/controllers/stats', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/controllers', (route) => route.fulfill({ json: CONTROLLERS }));
  await page.route('**/api/opcua/status', (route) =>
    route.fulfill({ json: { state: 'ONLINE', endpoint: 'opc.tcp://localhost:4840' } }),
  );
  await page.route('**/api/alarms/active', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/alarms/ai-history**', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/controllers/*/ai/status', (route) =>
    route.fulfill({ status: 404, json: { detail: 'none' } }),
  );
  await page.route('**/api/commands/tuning-recommendations/*', (route) =>
    route.fulfill({ status: 404, json: { detail: 'none' } }),
  );
}

async function stubWebSocket(page: Page): Promise<void> {
  await page.addInitScript((controllerIds: number[]) => {
    sessionStorage.setItem('smart-pid-token', 'jwt-e2e');
    sessionStorage.setItem('spid.welcome-seen', '1');

    const ff = (value: number) => ({
      value,
      severity: 'GOOD',
      limit_bits: 'NONE',
      sub_status: 'NON_SPECIFIC',
    });
    const statusFrame = (loopId: number) =>
      JSON.stringify({
        type: 'status',
        loop_id: loopId,
        seq: 1,
        ts: 1,
        data: {
          pv: ff(50),
          sp: ff(55),
          co: ff(42),
          bkcal_in: ff(0),
          bkcal_out: ff(0),
          mode: 'MAN',
          kp: 1,
          ti: 10,
          td: 0,
          integral_val: 0,
          timestamp: '2026-06-20T00:00:00.000Z',
        },
      });

    class StubWS extends EventTarget {
      url: string;
      readyState = 1;
      onopen: (() => void) | null = null;
      onmessage: ((e: MessageEvent) => void) | null = null;
      onclose: (() => void) | null = null;
      constructor(url: string) {
        super();
        this.url = url;
        setTimeout(() => this.onopen?.(), 0);
      }
      send() {
        setTimeout(() => {
          this.onmessage?.(
            new MessageEvent('message', { data: JSON.stringify({ type: 'auth_ok' }) }),
          );
          for (const id of controllerIds) {
            this.onmessage?.(new MessageEvent('message', { data: statusFrame(id) }));
          }
        }, 0);
      }
      close() {
        this.onclose?.();
      }
    }
    // @ts-expect-error override
    window.WebSocket = StubWS;
  }, CONTROLLERS.map((c) => c.id));
}

async function gotoDashboard(page: Page, width: number, height: number): Promise<void> {
  await stubWebSocket(page);
  await mockRest(page);
  await page.setViewportSize({ width, height });
  await page.goto('/');
  await expect(page.getByText('FIC-101')).toBeVisible();
}

const navRail = (page: Page) => page.getByRole('navigation', { name: 'Main navigation' });

// Click the per-card "Open faceplate" button inside the card whose tag matches `tag`.
async function openFaceplate(page: Page, tag: string): Promise<void> {
  const card = page
    .getByText(tag, { exact: true })
    .locator('xpath=ancestor::*[contains(@class,"rounded-card")][1]');
  await card.getByRole('button', { name: 'Open faceplate' }).click();
}

test.describe('responsive <1024', () => {
  test('nav rail collapses to icon-only (~64px) below 1024 and expands at >=1024', async ({
    page,
  }) => {
    // 320 + 768 are below the breakpoint -> collapsed icon rail.
    for (const width of [320, 768]) {
      await gotoDashboard(page, width, 900);
      const box = await navRail(page).boundingBox();
      expect(box, `nav rail visible at ${width}`).not.toBeNull();
      expect(box!.width, `nav rail collapsed at ${width}`).toBeLessThanOrEqual(
        NAV_RAIL_COLLAPSED + 4,
      );
      // Labels are hidden when collapsed; the icon-only links keep their accessible name.
      await expect(page.getByText('Dashboard', { exact: true })).toBeHidden();
      await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();
    }

    // 1024 + 1440 are at/above the breakpoint -> expanded label rail.
    for (const width of [1024, 1440]) {
      await gotoDashboard(page, width, 900);
      const box = await navRail(page).boundingBox();
      expect(box!.width, `nav rail expanded at ${width}`).toBeGreaterThanOrEqual(
        NAV_RAIL_EXPANDED - 8,
      );
      await expect(page.getByText('Dashboard', { exact: true })).toBeVisible();
    }
  });

  test('controller card grid is single-column below 1024 and multi-column at >=1024', async ({
    page,
  }) => {
    // Below 1024: the two cards stack -> distinct rows (one card per row).
    await gotoDashboard(page, 768, 900);
    const cardA = page.getByText('FIC-101').locator('xpath=ancestor::*[contains(@class,"rounded-card")][1]');
    const cardB = page.getByText('TIC-202').locator('xpath=ancestor::*[contains(@class,"rounded-card")][1]');
    const boxA = await cardA.boundingBox();
    const boxB = await cardB.boundingBox();
    expect(boxA && boxB).toBeTruthy();
    // Single column => card B starts below card A (no horizontal sharing of a row).
    expect(boxB!.y, 'second card stacks below the first').toBeGreaterThanOrEqual(
      boxA!.y + boxA!.height - 1,
    );
    // Each card spans (almost) the full content width — not the fixed 280px card token.
    expect(boxA!.width, 'card grows past the 280px fixed width when stacked').toBeGreaterThan(300);

    // At 1440: the cards sit side-by-side on the same row (wrap layout).
    await gotoDashboard(page, 1440, 900);
    const wideA = await page
      .getByText('FIC-101')
      .locator('xpath=ancestor::*[contains(@class,"rounded-card")][1]')
      .boundingBox();
    const wideB = await page
      .getByText('TIC-202')
      .locator('xpath=ancestor::*[contains(@class,"rounded-card")][1]')
      .boundingBox();
    expect(Math.abs(wideA!.y - wideB!.y), 'cards share a row at 1440').toBeLessThan(8);
  });

  test('faceplate opens full-screen below 1024', async ({ page }) => {
    await gotoDashboard(page, 768, 900);
    // Open the faceplate for FIC-101.
    await openFaceplate(page, 'FIC-101');
    const faceplate = page.getByRole('complementary', { name: /faceplate fic-101/i });
    await expect(faceplate).toBeVisible();
    // The dialog content wrapping the faceplate fills the viewport below 1024.
    const dialog = page.getByRole('dialog');
    const box = await dialog.boundingBox();
    const viewport = page.viewportSize()!;
    expect(box!.width, 'dialog spans viewport width').toBeGreaterThanOrEqual(viewport.width - 2);
    expect(box!.height, 'dialog spans viewport height').toBeGreaterThanOrEqual(viewport.height - 2);
  });

  test('touch targets stay >=44x44 below 1024', async ({ page }) => {
    await gotoDashboard(page, 768, 1100);

    // Nav items (collapsed icon rail).
    await assertMinTarget(page.getByRole('link', { name: 'Dashboard' }), TARGET_MIN);
    await assertMinTarget(page.getByRole('link', { name: 'Alarms' }), TARGET_MIN);

    // ACK ALL in the persistent alarm bar.
    await assertMinTarget(page.getByRole('button', { name: 'ACK ALL' }), TARGET_MIN);

    // Open the faceplate to reach the mode buttons + the MAN-only CO slider thumb.
    await openFaceplate(page, 'FIC-101');
    await expect(page.getByRole('complementary', { name: /faceplate fic-101/i })).toBeVisible();

    // Mode button (AUTO) inside the segmented control.
    await assertMinTarget(page.getByRole('button', { name: 'AUTO' }).first(), TARGET_MIN);

    // Slider thumb (MAN mode => enabled). Radix renders the thumb with role="slider".
    await assertMinTarget(page.getByRole('slider').first(), TARGET_MIN);
  });
});
