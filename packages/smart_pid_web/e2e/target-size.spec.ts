import { expect, test, type Page } from '@playwright/test';
import { assertMinTarget } from './helpers/targetSize';

// Target-size smoke (spec §8.3 / refactor spec §4): interactive controls on control stations must
// reach >=44x44 CSS px. This spec lands the reusable helper + one smoke assertion now; later phases
// flesh it out per surface (segmented mode buttons, CO slider, ACK / ack-all, apply-tuning, theme
// switch), enforcing the full 44x44 floor once those controls are refactored.
//
// CURRENT STATE (pre-refactor): measured dashboard controls clear the WCAG 2.5.8 AA 24x24 minimum
// (e.g. Apply tuning 109x27, Start 44x27) but NOT the 44x44 height the spec demands — the gap the
// per-surface refactor closes. So the smoke assertion exercises the helper at the WCAG 24px floor
// (green today) rather than silently failing on a control later phases will resize.
//
// Harness mirrors themes.spec.ts: no backend — /api/* is mocked via page.route and the WebSocket is
// stubbed via addInitScript. The dashboard route `/` is RequireAuth-gated, so the token is seeded
// into sessionStorage before load; the post-login WelcomeDialog is suppressed.

const WCAG_AA_MIN = 24;
const SPEC_MIN = 44;

const CONTROLLERS = [
  {
    id: 1,
    name: 'FIC-101',
    description: 'Flow',
    pv_decimals: 1,
    pv_unit: '%',
    optimization_enabled: false,
  },
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
          mode: 'AUTO',
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

test.describe('target size (>=44x44)', () => {
  test.beforeEach(async ({ page }) => {
    await stubWebSocket(page);
    await mockRest(page);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    await expect(page.getByText('FIC-101')).toBeVisible();
  });

  test('apply-tuning control meets the WCAG 2.5.8 AA minimum (helper smoke)', async ({ page }) => {
    // 'Apply tuning' is one of the eventual >=44x44 targets; today it clears the 24x24 AA floor.
    const applyTuning = page.getByRole('button', { name: /apply tuning/i }).first();
    await expect(applyTuning).toBeVisible();
    await assertMinTarget(applyTuning, WCAG_AA_MIN);
  });
});

// Responsive floor (Task 9.2 / §9): below the 1024 token breakpoint the spec's full >=44x44 floor
// is ENFORCED on the primary controls — nav items (collapsed icon rail), mode buttons, ACK ALL, and
// the MAN-only CO slider thumb. Same mocked harness; status frame uses MAN so the slider is enabled.
test.describe('target size (>=44x44) — responsive <1024', () => {
  test.beforeEach(async ({ page }) => {
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
    await mockRest(page);
    await page.setViewportSize({ width: 768, height: 1100 });
    await page.goto('/');
    await expect(page.getByText('FIC-101')).toBeVisible();
  });

  test('nav items, ack-all, mode buttons and slider thumb all clear >=44x44', async ({ page }) => {
    await assertMinTarget(page.getByRole('link', { name: 'Dashboard' }), SPEC_MIN);
    await assertMinTarget(page.getByRole('button', { name: 'ACK ALL' }), SPEC_MIN);

    const card = page
      .getByText('FIC-101', { exact: true })
      .locator('xpath=ancestor::*[contains(@class,"rounded-card")][1]');
    await card.getByRole('button', { name: 'Open faceplate' }).click();
    await expect(page.getByRole('complementary', { name: /faceplate fic-101/i })).toBeVisible();

    await assertMinTarget(page.getByRole('button', { name: 'AUTO' }).first(), SPEC_MIN);
    await assertMinTarget(page.getByRole('slider').first(), SPEC_MIN);
  });
});
