import { expect, type Page } from '@playwright/test';

/**
 * Shared phase-4 E2E harness. No backend runs: every REST route the shell and
 * dashboard touch is stubbed and the WebSocket is replaced in an init script.
 *
 * Two rules this harness exists to enforce:
 *  1. `GET /api/auth/me` is ALWAYS stubbed. `useCan` is deny-by-default, so
 *     without it the admin-only controls never render.
 *  2. Emitted envelopes advance `seq` MONOTONICALLY. A constant `seq: 1` looks
 *     like a gap to the phase-3 tracker, which forces a §7 resync; under React
 *     StrictMode the second mount already runs one, so the whole resync set is
 *     stubbed too and a failure there would recycle the socket forever.
 */

export const SESSION_KEY = 'smart-pid-token';

export interface HarnessLoop {
  id: number;
  name: string;
  description: string;
  euMin?: number;
  euMax?: number;
  unit?: string;
  pv: number;
  sp: number;
  co: number;
  mode: string;
}

export const FIC101: HarnessLoop = {
  id: 1,
  name: 'FIC-101',
  description: 'Flow',
  euMin: 0,
  euMax: 100,
  unit: '%',
  pv: 50,
  sp: 55,
  co: 42,
  mode: 'AUTO',
};

export const TIC202: HarnessLoop = {
  id: 2,
  name: 'TIC-202',
  description: 'Temp',
  euMin: 0,
  euMax: 300,
  unit: '°C',
  pv: 180,
  sp: 185,
  co: 61,
  mode: 'AUTO',
};

function controllerPayload(loop: HarnessLoop): Record<string, unknown> {
  return {
    id: loop.id,
    name: loop.name,
    description: loop.description,
    mode: loop.mode,
    pv: loop.pv,
    sp: loop.sp,
    co: loop.co,
    pv_scale: { eu_min: loop.euMin ?? 0, eu_max: loop.euMax ?? 100, unit: loop.unit ?? '' },
    out_scale: { eu_min: 0, eu_max: 100, unit: '%' },
    permitted_modes: ['MAN', 'AUTO'],
    optimization_enabled: false,
  };
}

export interface RestOptions {
  loops?: HarnessLoop[];
  /** GET /alarms/active rows. */
  alarms?: Record<string, unknown>[];
  role?: 'admin' | 'user';
}

export async function mockRest(page: Page, options: RestOptions = {}): Promise<void> {
  const loops = options.loops ?? [FIC101];
  const role = options.role ?? 'admin';

  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ json: { access_token: 'jwt-e2e', token_type: 'bearer' } }),
  );
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { user_id: 1, username: role, role } }),
  );
  await page.route('**/api/controllers', (route) =>
    route.fulfill({ json: loops.map(controllerPayload) }),
  );
  await page.route('**/api/alarms/active', (route) =>
    route.fulfill({ json: options.alarms ?? [] }),
  );
  await page.route('**/api/alarms/ack-all', (route) => route.fulfill({ json: { acked: 0 } }));
  // §7 resync set — StrictMode's second mount runs a resync on first load.
  await page.route('**/api/alarms/history**', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/controllers/*/ai/status', (route) =>
    route.fulfill({ json: { controller_id: 1, running: false, engine: 'NONE' } }),
  );
  await page.route('**/api/opcua/status', (route) =>
    route.fulfill({ json: { state: 'ONLINE', endpoint: 'opc.tcp://localhost:4840' } }),
  );
  await page.route('**/api/simulator/status', (route) =>
    route.fulfill({ json: { running: false, controllers: [] } }),
  );
  await page.route('**/api/commands/**', (route) => route.fulfill({ json: { ok: true } }));
}

export interface SocketOptions {
  loops?: HarnessLoop[];
  /** Frames emitted per loop; >1 gives the recorder an actual trace. */
  samples?: number;
}

export async function stubWebSocket(page: Page, options: SocketOptions = {}): Promise<void> {
  const loops = (options.loops ?? [FIC101]).map((l) => ({
    id: l.id,
    pv: l.pv,
    sp: l.sp,
    co: l.co,
    mode: l.mode,
  }));
  const samples = options.samples ?? 3;

  await page.addInitScript(
    (arg: { loops: { id: number; pv: number; sp: number; co: number; mode: string }[]; samples: number }) => {
      const T0 = 1750000000;
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
          setTimeout(() => this.onopen?.(), 0);
        }
        send(): void {
          setTimeout(() => {
            this.onmessage?.(
              new MessageEvent('message', { data: JSON.stringify({ type: 'auth_ok' }) }),
            );
            for (let i = 0; i < arg.samples; i += 1) {
              for (const loop of arg.loops) {
                this.seq += 1;
                this.onmessage?.(
                  new MessageEvent('message', {
                    data: JSON.stringify({
                      type: 'status',
                      loop_id: loop.id,
                      seq: this.seq,
                      ts: T0 + i,
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
                        timestamp: T0 + i,
                      },
                    }),
                  }),
                );
              }
            }
          }, 0);
        }
        close(): void {
          this.onclose?.({ code: 1000 });
        }
      }
      // @ts-expect-error test double
      window.WebSocket = StubWS;
    },
    { loops, samples },
  );
}

/** Seed the guarded session (and optionally a stored theme) before first paint. */
export async function seedSession(page: Page, theme?: string): Promise<void> {
  await page.addInitScript(
    (arg: { key: string; theme?: string }) => {
      sessionStorage.setItem(arg.key, 'jwt-e2e');
      if (arg.theme !== undefined) localStorage.setItem('spid.theme', arg.theme);
    },
    { key: SESSION_KEY, theme },
  );
}

export interface DashboardOptions extends RestOptions, SocketOptions {
  width?: number;
  height?: number;
  theme?: string;
}

/** Seeded session → mocked REST → stubbed socket → `/` with a live first frame. */
export async function gotoDashboard(page: Page, options: DashboardOptions = {}): Promise<void> {
  const loops = options.loops ?? [FIC101];
  await seedSession(page, options.theme);
  await stubWebSocket(page, { loops, samples: options.samples });
  await mockRest(page, { loops, alarms: options.alarms, role: options.role });
  await page.setViewportSize({
    width: options.width ?? 1440,
    height: options.height ?? 900,
  });
  await page.goto('/');
  await expect(page.getByText(loops[0].name).first()).toBeVisible();
}

export const loopCard = (page: Page, tag: string) =>
  page.getByRole('listitem').filter({ hasText: tag });

export const faceplate = (page: Page, tag: string) =>
  page.getByRole('complementary', { name: `Faceplate ${tag}` });
