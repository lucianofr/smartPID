import { expect, test, type Page } from '@playwright/test';

// Fatia 8 — faceplate visual-regression. No real backend: all /api/* is mocked via page.route and
// the WebSocket is stubbed via addInitScript (mirrors themes.spec.ts / executive-dashboard.spec).
// The dashboard route `/` is RequireAuth-gated, so the token is seeded into sessionStorage before
// load (STORAGE_KEY = 'smart-pid-token'). The WelcomeDialog is suppressed (spid.welcome-seen) so
// its overlay does not intercept the "Open faceplate" click.
//
// Flow: harness -> goto('/') -> click the card's "Open faceplate" button (T9a wiring) -> the
// Faceplate renders inside a Dialog as <aside role=complementary aria-label="Faceplate FIC-101">.
// The Faceplate reads lastStatus.get(controllerId); the auto-pushed status frame (loop_id === id)
// is what makes it populate PV/SP/CO + the mode group instead of showing "Waiting for data…".

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
  // The faceplate's useTuningRecommendation hits this; 404 = no pending recommendation (Apply
  // tuning… stays disabled), which keeps the snapshot deterministic.
  await page.route('**/api/commands/tuning-recommendations/*', (route) =>
    route.fulfill({ status: 404, json: { detail: 'none' } }),
  );
}

// Auto-push a deterministic `status` frame for the mocked controller so the faceplate populates.
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

test.describe('Faceplate', () => {
  test.beforeEach(async ({ page }) => {
    await stubWebSocket(page);
    await mockRest(page);
  });

  test('faceplate renders PV/SP/CO and mode control', async ({ page }) => {
    await page.goto('/');

    // Open the first controller's faceplate (T9a button on ControllerCard).
    await expect(page.getByText('FIC-101')).toBeVisible();
    await page.getByRole('button', { name: /open faceplate/i }).first().click();

    // The faceplate is an <aside role=complementary aria-label="Faceplate FIC-101"> inside a Dialog.
    const fp = page.getByRole('complementary', { name: /faceplate/i });
    await expect(fp).toBeVisible();

    // Status frame applied -> populated branch (mode group + PV/SP/CO readouts), not "Waiting…".
    await expect(fp.getByRole('group', { name: /controller mode/i })).toBeVisible();
    await expect(fp.getByText('PV').first()).toBeVisible();
    await expect(fp.getByText('SP').first()).toBeVisible();
    await expect(fp.getByText('CO').first()).toBeVisible();

    await expect(fp).toHaveScreenshot('faceplate-default.png', {
      maxDiffPixelRatio: 0.02,
      animations: 'disabled',
    });
  });
});
