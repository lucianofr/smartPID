import { expect, test, type Page } from '@playwright/test';
import { FIC101, mockRest, seedSession } from './helpers/harness';

// Phase 9 — executive dashboard e2e. No backend runs: REST comes from the shared
// harness (which also stubs `/api/auth/me` and the whole §7 resync set, because
// StrictMode's second mount always resyncs) and the WebSocket is replaced in an
// init script.
//
// This spec keeps its own socket stub instead of the harness one for a single
// reason: it must hand the test a `__pushStats` handle so a live STATS frame can
// be injected mid-test. It obeys the same rule the harness enforces — `seq`
// advances MONOTONICALLY, or the phase-3 tracker reads a gap, forces a resync
// and recycles the socket forever.
//
// Two scenarios:
//  1. The page loads and the aggregate KPI cards + loop health render the stubbed REST values.
//  2. A live `stats` WS frame overlays the REST snapshot per loop (no reload), updating Avg IAE.

// REST StatsResponse field names (smart_pid_domain/dtos/ai.py StatsResponse). One loop only, so
// avgIae = iae = 12.5 -> "12.50" and avgVariabilityRange = variability_range = 0.04 -> "4.0%".
const STATS = [
  {
    controller_id: FIC101.id,
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

const SYSTEM = {
  status: 'running',
  uptime_s: 3661,
  active_controllers: 1,
  bus_active: true,
  api_version: '2.0.0',
};

/** Harness REST + the three routes only the executive dashboard reads. */
async function mockExecutiveRest(page: Page): Promise<void> {
  await mockRest(page, { loops: [FIC101] });
  // `**/api/controllers` (harness) cannot match `/api/controllers/stats`, and
  // `**/api/alarms/history**` cannot match `/api/alarms/ai-history` — no overlap.
  await page.route('**/api/controllers/stats', (route) => route.fulfill({ json: STATS }));
  await page.route('**/api/alarms/ai-history**', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/system/status', (route) => route.fulfill({ json: SYSTEM }));
}

// Emit `auth_ok` plus one STATUS frame on send(), then expose __pushStats so a test
// can inject a live STATS.{id} frame. The frame data is the snake_case StatsData
// shape (envelope.ts); RealtimeProvider routes `type:'stats'` to the subscribers and
// useStats overlays the polled row for that loop.
async function stubWebSocket(page: Page): Promise<void> {
  await page.addInitScript(
    (loop: { id: number; pv: number; sp: number; co: number; mode: string }) => {
      const T0 = 1750000000;
      // Test-double handle the stub publishes on `window`; the real page has no
      // such global, so the assertion is the whole point of the double.
      const handle = window as unknown as {
        __pushStats?: (loopId: number, iae: number) => void;
      };
      const ff = (value: number) => ({
        value,
        severity: 'GOOD',
        limit_bits: 'NONE',
        sub_status: 'NON_SPECIFIC',
      });

      class StubWS extends EventTarget {
        url: string;
        readyState = 1;
        seq = 0;
        onopen: (() => void) | null = null;
        onmessage: ((e: MessageEvent) => void) | null = null;
        onclose: ((e: { code: number }) => void) | null = null;

        constructor(url: string) {
          super();
          this.url = url;
          handle.__pushStats = (loopId: number, iae: number) => {
            this.emit({
              type: 'stats',
              loop_id: loopId,
              ts: T0 + this.seq,
              data: {
                iae,
                itae: 200,
                ise: 30,
                mse: 1.1,
                std_dev: 0.8,
                total_variation: 4.2,
                variability_sp: 0.03,
                variability_range: 0.04,
                sample_count: 600,
                mean_abs_error: 0,
                pk_pk_error: 0,
                reversals: 0,
                zero_crossings: 0,
                recent_pk_pk_error: 0,
                recent_reversals: 0,
                tv_per_sample: 0,
                osc: 0,
              },
            });
          };
          setTimeout(() => this.onopen?.(), 0);
        }

        /** The ONE place `seq` is stamped, so every frame advances it. */
        emit(envelope: Record<string, unknown>): void {
          this.seq += 1;
          this.onmessage?.(
            new MessageEvent('message', { data: JSON.stringify({ ...envelope, seq: this.seq }) }),
          );
        }

        send(): void {
          setTimeout(() => {
            this.onmessage?.(
              new MessageEvent('message', { data: JSON.stringify({ type: 'auth_ok' }) }),
            );
            this.emit({
              type: 'status',
              loop_id: loop.id,
              ts: T0,
              data: {
                controller_id: loop.id,
                pv: ff(loop.pv),
                sp: ff(loop.sp),
                co: ff(loop.co),
                bkcal_in: ff(0),
                bkcal_out: ff(0),
                mode: loop.mode,
                kp: 1,
                ti: 10,
                td: 0,
                integral_val: 0,
                timestamp: T0,
              },
            });
          }, 0);
        }

        close(): void {
          this.onclose?.({ code: 1000 });
        }
      }
      // @ts-expect-error test double
      window.WebSocket = StubWS;
    },
    { id: FIC101.id, pv: FIC101.pv, sp: FIC101.sp, co: FIC101.co, mode: FIC101.mode },
  );
}

test.describe('Executive Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await seedSession(page);
    await stubWebSocket(page);
    await mockExecutiveRest(page);
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

    // Push a live STATS frame for loop 1 with a new IAE. useStats overlays the REST snapshot,
    // so avgIae becomes 9.00 — no reload, the RealtimeProvider re-renders on the frame.
    await page.evaluate(() => {
      const handle = window as unknown as {
        __pushStats?: (loopId: number, iae: number) => void;
      };
      handle.__pushStats?.(1, 9.0);
    });

    await expect(page.getByTestId('kpi-iae')).toContainText('9.00');
  });
});
