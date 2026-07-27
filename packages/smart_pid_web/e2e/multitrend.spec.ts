import { expect, test, type Page } from '@playwright/test';
import { FIC101, mockRest, seedSession, TIC202 } from './helpers/harness';

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
//
// `mockRest` supplies GET /auth/me — `useCan` is deny-by-default, so without it the export
// control never renders — plus the whole §7 resync set. React StrictMode mounts twice, and
// the second `auth_ok` always runs a resync: a hole in that set fails the resync, which
// recycles the socket forever.
async function mockShell(page: Page): Promise<void> {
  await mockRest(page, { loops: [FIC101, TIC202] });
  await page.route('**/api/controllers/stats', (route) =>
    route.fulfill({ json: [STATS_ROW(1), STATS_ROW(2)] }),
  );
}

// Stub the WebSocket: emit `auth_ok` on send(), then expose __pushStatus so the test can
// emit live `status` frames for any loop on demand. pv/sp/co are FFSignal objects and
// `timestamp` is an ISO string (the live model derives its time axis via Date.parse).
async function stubWebSocket(page: Page): Promise<void> {
  await seedSession(page);
  await page.addInitScript(() => {
    // Suppress the post-login WelcomeDialog so its overlay does not intercept clicks.
    sessionStorage.setItem('spid.welcome-seen', '1');

    const statusFrame = (
      loopId: number,
      seq: number,
      pv: number,
      sp: number,
      co: number,
      isoTs: string,
    ) =>
      JSON.stringify({
        type: 'status',
        loop_id: loopId,
        // MONOTONIC per connection: a repeated seq reads as a gap to the phase-3
        // tracker, which forces a resync on every single frame.
        seq,
        ts: seq,
        data: {
          controller_id: loopId,
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
      seq = 0;
      onopen: (() => void) | null = null;
      onmessage: ((e: MessageEvent) => void) | null = null;
      onclose: ((e: { code: number }) => void) | null = null;
      constructor(url: string) {
        super();
        this.url = url;
        // Push a fresh status frame for a loop; each call uses a distinct ISO timestamp so
        // the model's de-dupe (last-t equality) does not drop it.
        // Test-injected global: the page never declares it, so the shape is ours to state.
        const testWindow = window as unknown as {
          __pushStatus?: (loopId: number, sec: number) => void;
        };
        testWindow.__pushStatus = (loopId: number, sec: number) => {
          const iso = new Date(Date.UTC(2026, 5, 19, 0, 0, sec)).toISOString();
          this.seq += 1;
          this.onmessage?.(
            new MessageEvent('message', {
              data: statusFrame(loopId, this.seq, 50 + loopId, 60 + loopId, 40 + loopId, iso),
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
        this.onclose?.({ code: 1000 });
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
        // Test-injected global (see stubWebSocket).
        const testWindow = window as unknown as {
          __pushStatus?: (loopId: number, sec: number) => void;
        };
        testWindow.__pushStatus?.(id, sec);
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

  test('replays a bounded history window and scores the loops from REST stats', async ({
    page,
  }) => {
    const frame = (sec: number, pv: number) => ({
      timestamp: new Date(Date.UTC(2026, 5, 19, 0, 0, sec)).toISOString(),
      pv,
      sp: 60,
      co: 40,
      mode: 'AUTO',
      status: 'GOOD',
    });
    await page.route('**/api/history/1**', (route) =>
      route.fulfill({
        json: { controller_id: 1, count: 3, frames: [frame(1, 50), frame(2, 51), frame(3, 52)] },
      }),
    );

    await page.goto('/multitrend');

    // The stats roster scores every loop, selected or not — one column per metric.
    await expect(page.getByRole('columnheader', { name: 'IAE' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: '2σ/SP' })).toBeVisible();
    await expect(page.getByRole('rowheader', { name: 'Loop 2' })).toBeVisible();
    await expect(page.getByRole('cell', { name: '20.0%' }).first()).toBeVisible();

    // No loop is checked, so the history target falls back to the first stats loop.
    await page.getByLabel('Janela').fill('2');
    await page.getByLabel('Unidade').selectOption('hora');
    const [request] = await Promise.all([
      page.waitForRequest(/\/api\/history\/1\?/),
      page.getByRole('button', { name: 'Carregar histórico' }).click(),
    ]);

    // Duration → explicit ISO bounds spanning exactly two hours, plus a row cap.
    const params = new URL(request.url()).searchParams;
    const span = Date.parse(params.get('end')!) - Date.parse(params.get('start')!);
    expect(span).toBe(2 * 60 * 60 * 1000);
    expect(Number(params.get('limit'))).toBeGreaterThan(0);

    await expect(page.getByText('3 amostras')).toBeVisible();
    await expect(page.getByTestId('multitrend-history-chart')).toBeVisible();

    // Live accumulation is stoppable without leaving the page.
    await page.getByRole('button', { name: 'Pausar' }).click();
    await expect(page.getByRole('button', { name: 'Retomar' })).toBeVisible();
  });

  test('a trend selection survives a full page reload', async ({ page }) => {
    await page.goto('/multitrend');

    await page.getByLabel('Loop 1 · PV').check();
    await page.getByLabel('Loop 2 · CO').check();
    await expect(page.getByLabel('Loop 1 · PV')).toBeChecked();

    await page.reload();

    await expect(page.getByLabel('Loop 1 · PV')).toBeChecked();
    await expect(page.getByLabel('Loop 2 · CO')).toBeChecked();
    await expect(page.getByLabel('Loop 1 · SP')).not.toBeChecked();
    expect(
      await page.evaluate(() => localStorage.getItem('spid.multitrend')),
    ).not.toBeNull();
  });
});
