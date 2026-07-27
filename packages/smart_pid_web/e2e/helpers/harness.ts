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
    sp_lo_lim: loop.euMin ?? 0,
    sp_hi_lim: loop.euMax ?? 100,
    process_speed: 'MEDIUM',
    ai_config: {
      engine: 'FUZZY',
      objective: 'SP_TRACKING',
      dead_time_l: 1,
      limit_min: 0.1,
      limit_max: 100,
      rl_fallback_kp: 0.6,
      rl_fallback_kd: 0.2,
      rl_learning_rate: 0.0003,
      rl_train_interval: 32,
    },
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
  // Phase 10: the WelcomeGate asks for the roster on the first authenticated
  // view. Empty keeps the gate shut AND keeps the proxy quiet in every spec.
  await page.route('**/api/project/list', (route) => route.fulfill({ json: { projects: [] } }));
  await page.route('**/api/commands/**', (route) => route.fulfill({ json: { ok: true } }));
}

export interface SocketOptions {
  loops?: HarnessLoop[];
  /** Frames emitted per loop; >1 gives the recorder an actual trace. */
  samples?: number;
  /**
   * Deterministic PV/CO excursion in engineering units. 0 (default) keeps the
   * flat trace every functional spec expects. The visual baselines pass a
   * non-zero amplitude so the §6.3 trace language — PV/SP/CO hues, per-series
   * widths and the SP dash, which ISA-101 alone renders solid — is actually
   * drawn into the recorded PNG instead of collapsing onto the axis bounds.
   *
   * The shape is an integer table, not `Math.sin`: IEEE add/multiply/divide are
   * exactly reproducible, transcendentals are not guaranteed to be.
   */
  wave?: number;
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
  const wave = options.wave ?? 0;

  await page.addInitScript(
    (arg: {
      loops: { id: number; pv: number; sp: number; co: number; mode: string }[];
      samples: number;
      wave: number;
    }) => {
      const T0 = 1750000000;
      const ff = (value: number) => ({
        value,
        severity: 'GOOD',
        limit_bits: 'NONE',
        sub_status: 'NON_SPECIFIC',
      });
      // Integer excursion tables, out of phase so PV and CO never overlap.
      const PV_WAVE = [0, 2, 3, 2, 0, -2, -3, -2];
      const CO_WAVE = [3, 2, 0, -2, -3, -2, 0, 2];
      const clamp = (v: number) => (v < 0 ? 0 : v > 100 ? 100 : v);

      class StubWS extends EventTarget {
        static live: StubWS | null = null;
        url: string;
        readyState = 1;
        seq = 0;
        frame = 0;
        onopen: (() => void) | null = null;
        onmessage: ((e: MessageEvent) => void) | null = null;
        onclose: ((e: { code: number }) => void) | null = null;
        constructor(url: string) {
          super();
          this.url = url;
          StubWS.live = this;
          setTimeout(() => this.onopen?.(), 0);
        }
        /**
         * Emit `count` status frames starting at frame index `from`, one
         * monotonic second apart. An explicit `from` makes a re-send byte
         * identical, which is what lets `emitFrames` probe idempotently.
         */
        emit(count: number, from = this.frame): void {
          for (let n = 0; n < count; n += 1) {
            const i = from + n;
            this.frame = i + 1;
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
                      pv: ff(loop.pv + arg.wave * PV_WAVE[i % PV_WAVE.length]),
                      sp: ff(loop.sp),
                      co: ff(clamp(loop.co + arg.wave * CO_WAVE[i % CO_WAVE.length])),
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
        }
        send(): void {
          setTimeout(() => {
            this.onmessage?.(
              new MessageEvent('message', { data: JSON.stringify({ type: 'auth_ok' }) }),
            );
            this.emit(arg.samples);
          }, 0);
        }
        close(): void {
          this.onclose?.({ code: 1000 });
        }
      }
      // @ts-expect-error test double
      window.WebSocket = StubWS;
      // `emitFrames` drives frames AFTER React has mounted and subscribed: the
      // realtime fan-out only reaches live subscribers, and the open-time burst
      // races the mount, so a spec that needs a known sample count in the trend
      // window must push them from here.
      // @ts-expect-error test hook
      window.__spidEmitFrames = (count: number, from?: number) =>
        StubWS.live?.emit(count, from);
    },
    { loops, samples, wave },
  );
}

/**
 * In-page predicate: has uPlot committed a frame to every trend canvas?
 * Serialized into the browser, so it must capture nothing from this module.
 *
 * This is a paint gate, not a content gate. A content gate ("a pixel of
 * `--trace-pv` is on the canvas") was tried and cannot be used yet: with 24
 * plotted rows confirmed through the CSV export, uPlot issues the PV/SP/CO
 * strokes with the right colours and widths and still leaves no trace pixel
 * behind, so the series path it builds is degenerate. That is a rendering
 * defect in its own right, tracked for the backend E2E gate; asserting on it
 * here would only wedge the baseline run.
 */
function trendCanvasPainted(): boolean {
  const wells = [...document.querySelectorAll('[role="img"][data-glow]')];
  if (wells.length === 0) return false;
  return wells.every((well) => {
    const canvas = well.querySelector('canvas');
    if (canvas === null || canvas.width === 0 || canvas.height === 0) return false;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (ctx === null) return false;
    const { data } = ctx.getImageData(0, 0, canvas.width, canvas.height);
    for (let i = 3; i < data.length; i += 4) if (data[i] !== 0) return true;
    return false;
  });
}

/**
 * The burst base, in frames-since-T0. Chosen so the burst is further from the
 * probe frames than the dashboard's default 30-minute window (1800 s), which
 * makes `windowBuffer.trim()` discard every probe sample: whatever the probe
 * loop happened to land, the window ends up holding the burst and nothing else.
 * A multiple of 8 keeps the excursion tables in phase with index 0.
 */
const BURST_BASE_FRAME = 2048;

/**
 * Leave exactly `count` samples in the trend window of a mounted app, at fixed
 * timestamps and a fixed excursion phase. Pair with `samples: 0`.
 *
 * Two races have to die for a screenshot to be reproducible. The realtime
 * fan-out only reaches live subscribers and the trend subscribes a task or two
 * after the loop list paints, so a burst sent too early is silently dropped;
 * and a *partially* dropped burst is worse than a lost one, because it shifts
 * the plotted timestamps and the wave phase.
 *
 * So: probe with frame 0 until the faceplate reports a value — the probe is
 * idempotent (same `t` every time, and the buffer rejects a non-increasing
 * `t`) — then send the real burst, synchronously and far enough in the future
 * that the window drops the probe residue. Synchronous fan-out is atomic with
 * respect to subscriber liveness, so the burst lands whole or not at all, and
 * waiting for the last frame's value to reach the DOM proves which.
 *
 * Verified with the panel's own CSV export ("exactly the plotted rows"): the
 * window ends up holding `count` rows, one second apart, starting at
 * T0+BURST_BASE_FRAME.
 */
export async function emitFrames(page: Page, count: number): Promise<void> {
  if (count < 2) throw new RangeError(`emitFrames needs at least 2 frames, got ${count}`);

  // aria-valuenow is omitted until a finite value arrives (AnalogBar), so its
  // presence is exactly "the realtime relay reached a mounted consumer".
  const pv = page.getByRole('complementary').first().getByRole('meter', { name: 'PV' });
  await expect
    .poll(
      async () => {
        await page.evaluate(() => {
          Reflect.get(window, '__spidEmitFrames')(1, 0);
        });
        return pv.getAttribute('aria-valuenow');
      },
      { message: 'the realtime relay never reached the faceplate', timeout: 15_000 },
    )
    .not.toBeNull();

  // The probe carries frame 0, whose excursion offset is 0, so this is the
  // loop's unperturbed PV. Read it BEFORE the burst moves it.
  const restingPv = Number(await pv.getAttribute('aria-valuenow'));

  const tail = await page.evaluate(
    (arg: { count: number; base: number }) => {
      Reflect.get(window, '__spidEmitFrames')(arg.count, arg.base);
      // Mirrors the stub's excursion table: the offset the last frame carries.
      const PV_WAVE = [0, 2, 3, 2, 0, -2, -3, -2];
      return PV_WAVE[(arg.base + arg.count - 1) % PV_WAVE.length];
    },
    { count, base: BURST_BASE_FRAME },
  );

  await expect(pv, 'the whole burst reached the faceplate').toHaveAttribute(
    'aria-valuenow',
    String(restingPv + tail),
  );
}

/**
 * Seed the guarded session (and optionally a stored theme) before first paint.
 *
 * `spid.welcome-seen` is part of the seed: the phase-10 WelcomeGate is an
 * admin-only modal that opens on the first authenticated view whenever the
 * project roster is non-empty, and its scrim would swallow clicks in every
 * spec that is not about the gate itself.
 */
export async function seedSession(page: Page, theme?: string): Promise<void> {
  await page.addInitScript(
    (arg: { key: string; theme?: string }) => {
      sessionStorage.setItem(arg.key, 'jwt-e2e');
      sessionStorage.setItem('spid.welcome-seen', '1');
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
  await stubWebSocket(page, { loops, samples: options.samples, wave: options.wave });
  await mockRest(page, { loops, alarms: options.alarms, role: options.role });
  await page.setViewportSize({
    width: options.width ?? 1440,
    height: options.height ?? 900,
  });
  await page.goto('/');
  await expect(page.getByText(loops[0].name).first()).toBeVisible();
}

/**
 * Phase 11 — freeze every source of screenshot flap before a visual baseline.
 *
 * Playwright's own `animations: 'disabled'` fast-forwards finite CSS animations
 * but leaves `alarm-blink` (1s step-start infinite) and every transition mid
 * flight, so they are killed outright here. The rest is ordering: webfonts must
 * have swapped in (Archivo/Geist change metrics), and uPlot paints into its
 * canvas from a rAF — a shot taken before that frame records an empty well.
 *
 * Readiness is `trendCanvasPainted`; the plotted content is pinned separately
 * by emitFrames. The rest of the determinism comes from the socket stub: fixed T0,
 * monotonic seq, an integer PV/CO excursion table, and a finite burst.
 */
export async function settleForShot(page: Page): Promise<void> {
  await page.addStyleTag({
    content:
      '*, *::before, *::after { animation: none !important; transition: none !important; ' +
      'caret-color: transparent !important; scroll-behavior: auto !important; }',
  });

  await page.waitForFunction(trendCanvasPainted);

  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise<void>((done) => {
      requestAnimationFrame(() => requestAnimationFrame(() => done()));
    });
  });
}

export const loopCard = (page: Page, tag: string) =>
  page.getByRole('listitem').filter({ hasText: tag });

export const faceplate = (page: Page, tag: string) =>
  page.getByRole('complementary', { name: `Faceplate ${tag}` });
