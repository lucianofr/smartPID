import { expect, test, type Page } from '@playwright/test';

// Fatia 8 — theme visual-regression. No real backend: all /api/* is mocked via page.route and
// the WebSocket is stubbed via addInitScript (mirrors executive-dashboard.spec.ts /
// multitrend.spec.ts). The dashboard route `/` is RequireAuth-gated, so the token is seeded
// into sessionStorage before load (STORAGE_KEY = 'smart-pid-token'); without it `/` redirects
// to /login and the snapshot captures the login screen instead of the dashboard. The post-login
// WelcomeDialog is suppressed (spid.welcome-seen) so its overlay does not cover the dashboard.
//
// Matrix: 5 themes x 4 breakpoints = 20 dashboard snapshots. The theme is seeded into
// localStorage BEFORE goto (ThemeProvider reads it synchronously at mount and applies it via
// `document.documentElement.setAttribute('data-theme', …)`), then asserted on <html> before the
// screenshot so the apply effect has run.

const THEMES = ['isa101', 'dark-room', 'md3-dark', 'md3-light', 'ocean'] as const;
const WIDTHS = [320, 768, 1024, 1440] as const;

// DashboardPage reads id/name/description/pv_decimals/pv_unit + optimization_enabled (passed to
// CardControls). One deterministic controller keeps the dashboard a single, stable card.
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

// AppShell + DashboardPage REST dependencies. No backend runs, so every endpoint touched on `/`
// must be stubbed or the unstubbed ones hang/404 and the page never settles.
async function mockRest(page: Page): Promise<void> {
  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ json: { access_token: 'jwt-e2e', token_type: 'bearer' } }),
  );
  // /controllers and /controllers/stats share a prefix — register /stats first so the more
  // specific glob wins over the bare /controllers handler. The dashboard does not read /stats,
  // but stubbing it keeps the harness identical to the other fatias and harmless if polled.
  await page.route('**/api/controllers/stats', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/controllers', (route) => route.fulfill({ json: CONTROLLERS }));
  await page.route('**/api/opcua/status', (route) =>
    route.fulfill({ json: { state: 'ONLINE', endpoint: 'opc.tcp://localhost:4840' } }),
  );
  await page.route('**/api/alarms/active', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/alarms/ai-history**', (route) => route.fulfill({ json: [] }));
  // Per-loop AI status + tuning recommendation: 404 = no AI worker / no pending recommendation.
  await page.route('**/api/controllers/*/ai/status', (route) =>
    route.fulfill({ status: 404, json: { detail: 'none' } }),
  );
  await page.route('**/api/commands/tuning-recommendations/*', (route) =>
    route.fulfill({ status: 404, json: { detail: 'none' } }),
  );
}

// Stub the WebSocket: emit `auth_ok` on send(), then auto-push a deterministic `status` frame for
// every mocked controller so the cards render populated PV/SP/CO instead of '—'. The frame uses
// the real envelope shape (envelope.ts StatusData): pv/sp/co/bkcal_* are FFSignal objects and
// `timestamp` is an ISO string. All values are FIXED — no random / no Date.now — so the snapshot
// is byte-stable.
async function stubWebSocket(page: Page): Promise<void> {
  await page.addInitScript((controllerIds: number[]) => {
    sessionStorage.setItem('smart-pid-token', 'jwt-e2e');
    // Suppress the post-login WelcomeDialog so its overlay does not cover the dashboard snapshot.
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

test.describe('theme visual parity', () => {
  test.beforeEach(async ({ page }) => {
    await stubWebSocket(page);
    await mockRest(page);
  });

  for (const theme of THEMES) {
    for (const width of WIDTHS) {
      test(`${theme} @ ${width}`, async ({ page }) => {
        await page.addInitScript((t) => localStorage.setItem('spid.theme', t), theme);
        await page.setViewportSize({ width, height: 900 });
        await page.goto('/');

        // The chosen theme must be applied to <html> before snapshotting.
        await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
        // The card (and its WS-driven PV) must be present so the snapshot is stable.
        await expect(page.getByText('FIC-101')).toBeVisible();
        await expect(page.getByRole('button', { name: /open faceplate/i })).toBeVisible();

        await expect(page).toHaveScreenshot(`dashboard-${theme}-${width}.png`, {
          maxDiffPixelRatio: 0.02,
          animations: 'disabled',
        });
      });
    }
  }
});
