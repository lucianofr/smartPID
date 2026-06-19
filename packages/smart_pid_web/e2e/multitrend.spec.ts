import { expect, test, type Page } from '@playwright/test';

// Fatia 4 — multi-trend e2e. No real backend: all /api/* is mocked via page.route and the
// WebSocket is stubbed via addInitScript (mirrors fatia2-commands.spec.ts). The /multitrend
// route is RequireAuth-gated, so the token is seeded into sessionStorage before load
// (STORAGE_KEY = 'smart-pid-token'); the route mocks do not validate the token.
//
// Two scenarios:
//  1. Multiple live series render after selecting signals for two distinct loops.
//  2. Export reaches an authenticated blob download (the done state is a <button>, not a link).

// Real StatsResponse field names (smart_pid_domain/dtos/ai.py StatsResponse): the selector
// loop list derives from these controller_id values.
const STATS_ROW = (controllerId: number) => ({
  controller_id: controllerId,
  iae: 1,
  itae: 2,
  ise: 3,
  mse: 4,
  std_dev: 5,
  total_variation: 6,
  variability_range: 0.1,
  variability_sp: 0.2,
  sample_count: 100,
});

// AppShell + page shell dependencies (OPC poll, AlarmBar, stats-derived loop list).
async function mockShell(page: Page): Promise<void> {
  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ json: { access_token: 'jwt-e2e', token_type: 'bearer' } }),
  );
  await page.route('**/api/controllers/stats', (route) =>
    route.fulfill({ json: [STATS_ROW(1), STATS_ROW(2)] }),
  );
  await page.route('**/api/opcua/status', (route) =>
    route.fulfill({ json: { state: 'ONLINE', endpoint: 'opc.tcp://localhost:4840' } }),
  );
  await page.route('**/api/alarms/active', (route) => route.fulfill({ json: [] }));
}

// Stub the WebSocket: emit `auth_ok` on send(), then expose __pushStatus so the test can
// emit live `status` frames for any loop on demand. pv/sp/co are FFSignal objects and
// `timestamp` is an ISO string (the live model derives its time axis via Date.parse).
async function stubWebSocket(page: Page): Promise<void> {
  await page.addInitScript(() => {
    sessionStorage.setItem('smart-pid-token', 'jwt-e2e');

    const statusFrame = (loopId: number, pv: number, sp: number, co: number, isoTs: string) =>
      JSON.stringify({
        type: 'status',
        loop_id: loopId,
        seq: 1,
        ts: 1,
        data: {
          pv: { value: pv, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
          sp: { value: sp, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
          co: { value: co, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
          bkcal_in: { value: 0, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
          bkcal_out: { value: 0, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
          mode: 'AUTO',
          kp: 1,
          ti: 10,
          td: 0,
          integral_val: 0,
          timestamp: isoTs,
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
        // Push a fresh status frame for a loop; each call uses a distinct ISO timestamp so
        // the model's de-dupe (last-t equality) does not drop it.
        (
          window as unknown as { __pushStatus?: (loopId: number, sec: number) => void }
        ).__pushStatus = (loopId: number, sec: number) => {
          const iso = new Date(Date.UTC(2026, 5, 19, 0, 0, sec)).toISOString();
          this.onmessage?.(
            new MessageEvent('message', {
              data: statusFrame(loopId, 50 + loopId, 60 + loopId, 40 + loopId, iso),
            }),
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

// Drive several live frames into a loop's buffer (selection must already include the loop).
async function pushFrames(page: Page, loopId: number, count: number): Promise<void> {
  for (let i = 1; i <= count; i += 1) {
    await page.evaluate(
      ([id, sec]) => {
        (
          window as unknown as { __pushStatus?: (loopId: number, sec: number) => void }
        ).__pushStatus?.(id, sec);
      },
      [loopId, i] as const,
    );
  }
}

test.describe('Multi-trend', () => {
  test.beforeEach(async ({ page }) => {
    await stubWebSocket(page);
    await mockShell(page);
  });

  test('plots multiple live series after selecting signals for two loops', async ({ page }) => {
    await page.goto('/multitrend');

    // Loop list (1 and 2) comes from the mocked /controllers/stats rows.
    const loop1Pv = page.getByLabel('Loop 1 · PV');
    const loop2Co = page.getByLabel('Loop 2 · CO');
    await expect(loop1Pv).toBeVisible();
    await expect(loop2Co).toBeVisible();

    await loop1Pv.check();
    await loop2Co.check();

    // The buffers only accumulate frames for currently-selected loops, so push after
    // selecting. A handful of frames each gives the chart real data for both series.
    await pushFrames(page, 1, 4);
    await pushFrames(page, 2, 4);

    // Chart canvas mounts and the uPlot legend lists both selected series (L{loopId} {VAR}).
    await expect(page.getByTestId('multitrend-chart')).toBeVisible();
    await expect(page.getByText('L1 PV')).toBeVisible();
    await expect(page.getByText('L2 CO')).toBeVisible();
  });

  test('export produces an authenticated blob download', async ({ page }) => {
    // create -> poll(done) -> authenticated blob download. Register general before specific
    // so the more specific /export/e1 and /export/e1/download handlers win.
    await page.route('**/api/export', (route) =>
      route.fulfill({
        status: 201,
        json: {
          id: 'e1',
          controller_id: 1,
          start: 's',
          end: 'e',
          format: 'csv',
          status: 'running',
          progress: 0,
          file_path: null,
        },
      }),
    );
    await page.route('**/api/export/e1', (route) =>
      route.fulfill({
        json: {
          id: 'e1',
          controller_id: 1,
          start: 's',
          end: 'e',
          format: 'csv',
          status: 'done',
          progress: 100,
          file_path: '/tmp/e1.csv',
        },
      }),
    );
    await page.route('**/api/export/e1/download', (route) =>
      route.fulfill({
        headers: {
          'content-type': 'text/csv',
          'content-disposition': 'attachment; filename=export_e1.csv',
        },
        body: 'timestamp,pv,sp,co\n0,1,2,3\n',
      }),
    );

    await page.goto('/multitrend');

    // Selecting Loop 1 · PV makes exportLoop = 1 (selection[0].loopId).
    await page.getByLabel('Loop 1 · PV').check();

    await page.getByRole('button', { name: /export/i }).click();

    // Done state is an authenticated-blob-download <button> labelled "Download" (NOT a link).
    const downloadBtn = page.getByRole('button', { name: /download/i });
    await expect(downloadBtn).toBeVisible();

    const [download] = await Promise.all([page.waitForEvent('download'), downloadBtn.click()]);
    expect(download.suggestedFilename()).toContain('export_e1.csv');
  });
});
