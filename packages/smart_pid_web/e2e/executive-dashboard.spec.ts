import { expect, test, type Page } from '@playwright/test';

// Fatia 6 — executive-dashboard e2e. No real backend: all /api/* is mocked via page.route and
// the WebSocket is stubbed via addInitScript (mirrors multitrend.spec.ts / fatia2-commands).
// The /executive route is RequireAuth-gated, so the token is seeded into sessionStorage before
// load (STORAGE_KEY = 'smart-pid-token'); WITHOUT it /executive redirects to /login and every
// assertion fails. The route mocks do not validate the token.
//
// Two scenarios:
//  1. The page loads and the aggregate KPI cards + loop health render the stubbed REST values.
//  2. A live `stats` WS frame overlays the REST snapshot per loop (no reload), updating Avg IAE.

// REST StatsResponse field names (smart_pid_domain/dtos/ai.py StatsResponse). One loop only, so
// avgIae = iae = 12.5 -> "12.50" and avgVariabilityRange = variability_range = 0.04 -> "4.0%".
const STATS = [
  {
    controller_id: 1,
    iae: 12.5,
    itae: 200,
    ise: 30,
    mse: 1.1,
    std_dev: 0.8,
    total_variation: 4.2,
    variability_sp: 0.03,
    variability_range: 0.04,
    sample_count: 600,
  },
];
const CONTROLLERS = [{ id: 1, name: 'FIC-101', mode: 'AUTO' }];

// AppShell + page shell REST dependencies. No backend runs, so every endpoint the page +
// AppShell touch must be stubbed or the unstubbed ones hang/404.
async function mockRest(page: Page): Promise<void> {
  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ json: { access_token: 'jwt-e2e', token_type: 'bearer' } }),
  );
  // /controllers and /controllers/stats share a prefix — register /stats first so the more
  // specific glob wins over the bare /controllers handler.
  await page.route('**/api/controllers/stats', (route) => route.fulfill({ json: STATS }));
  await page.route('**/api/controllers', (route) => route.fulfill({ json: CONTROLLERS }));
  await page.route('**/api/opcua/status', (route) =>
    route.fulfill({ json: { state: 'ONLINE', endpoint: 'opc.tcp://x:4840' } }),
  );
  await page.route('**/api/alarms/active', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/alarms/ai-history**', (route) => route.fulfill({ json: [] }));
  // Per-loop AI status + tuning recommendation: 404 = no AI worker / no pending recommendation.
  // The page treats both as null (retry:false), so this is the correct "nothing pending" state.
  await page.route('**/api/controllers/1/ai/status', (route) =>
    route.fulfill({ status: 404, json: { detail: 'none' } }),
  );
  await page.route('**/api/commands/tuning-recommendations/1', (route) =>
    route.fulfill({ status: 404, json: { detail: 'none' } }),
  );
}

// Stub the WebSocket: emit `auth_ok` on send(), then expose __pushStats so a test can push a
// live STATS.{id} frame. The frame data is the snake_case StatsData shape (envelope.ts); the
// RealtimeProvider routes `type:'stats'` into lastStats and the page overlays it via fromWsStats.
async function stubWebSocket(page: Page): Promise<void> {
  await page.addInitScript(() => {
    sessionStorage.setItem('smart-pid-token', 'jwt-e2e');

    const statsFrame = (loopId: number, iae: number) =>
      JSON.stringify({
        type: 'stats',
        loop_id: loopId,
        seq: 1,
        ts: 1,
        data: {
          controller_id: loopId,
          iae,
          itae: 200,
          ise: 30,
          mse: 1.1,
          std_dev: 0.8,
          total_variation: 4.2,
          variability_range: 0.04,
          variability_sp: 0.03,
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
        (
          window as unknown as { __pushStats?: (loopId: number, iae: number) => void }
        ).__pushStats = (loopId: number, iae: number) => {
          this.onmessage?.(
            new MessageEvent('message', { data: statsFrame(loopId, iae) }),
          );
        };
        setTimeout(() => this.onopen?.(), 0);
      }
      send() {
        setTimeout(() => {
          this.onmessage?.(
            new MessageEvent('message', { data: JSON.stringify({ type: 'auth_ok' }) }),
          );
        }, 0);
      }
      close() {
        this.onclose?.();
      }
    }
    // @ts-expect-error override
    window.WebSocket = StubWS;
  });
}

test.describe('Executive Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await stubWebSocket(page);
    await mockRest(page);
  });

  test('loads and renders aggregate KPI + health values from REST', async ({ page }) => {
    await page.goto('/executive');

    await expect(page.getByTestId('executive-dashboard')).toBeVisible();
    // One loop: avgIae = 12.5 -> "12.50"; avgVariabilityRange = 0.04 -> "4.0%".
    await expect(page.getByTestId('kpi-iae')).toContainText('12.50');
    await expect(page.getByTestId('kpi-variability')).toContainText('4.0%');
    await expect(page.getByTestId('health-FIC-101-opc')).toContainText('ONLINE');
  });

  test('a live stats frame updates Avg IAE without reload', async ({ page }) => {
    await page.goto('/executive');
    await expect(page.getByTestId('kpi-iae')).toContainText('12.50');

    // Push a live STATS frame for loop 1 with a new IAE. fromWsStats overlays the REST snapshot,
    // so avgIae becomes 9.00 — no reload, the RealtimeProvider re-renders on the frame.
    await page.evaluate(() => {
      (window as unknown as { __pushStats?: (loopId: number, iae: number) => void }).__pushStats?.(
        1,
        9.0,
      );
    });

    await expect(page.getByTestId('kpi-iae')).toContainText('9.00');
  });
});
