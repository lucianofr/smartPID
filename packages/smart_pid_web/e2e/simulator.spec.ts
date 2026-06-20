import { expect, test, type Page, type Route } from '@playwright/test';

// Fatia 5 — simulator e2e. No real backend: all /api/* is mocked via page.route and the
// WebSocket is stubbed via addInitScript (mirrors multitrend.spec.ts / fatia2-commands.spec.ts).
// The /simulator route self-shells (AppShell + AlarmBar + /opcua/status poll); the live twin
// trend is fed by stubbed WS `status` frames, while every control value the panel reads comes
// from the REST GET /simulator/status refetch that each mutation triggers via query invalidation.
//
// The simulator routes are STATEFUL: a closure `sim` object holds the running flag and the single
// controller's status. Mutation routes mutate `sim`, and GET /simulator/status returns the live
// `sim` snapshot — so after a mutation invalidates ['simulator','status'], the refetch reflects
// the change and Playwright's auto-retrying assertions converge without arbitrary sleeps.

// Stub the WebSocket: emit `auth_ok` on send(), then expose __pushStatus so the test can emit
// live `status` frames for any loop on demand. pv/sp/co are FFSignal objects and `timestamp` is
// an ISO string (twinTrend derives the x axis via Date.parse). Copied from multitrend.spec.ts.
async function stubWebSocket(page: Page): Promise<void> {
  await page.addInitScript(() => {
    sessionStorage.setItem('smart-pid-token', 'jwt-e2e');
    // Suppress the post-login WelcomeDialog so its overlay does not intercept clicks.
    sessionStorage.setItem('spid.welcome-seen', '1');

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
        // Push a fresh status frame for a loop; each call uses a distinct ISO timestamp so the
        // twin trend's de-dupe (last-t equality) does not drop it.
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

// AppShell + page shell dependencies (login, OPC poll, AlarmBar).
async function mockShell(page: Page): Promise<void> {
  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ json: { access_token: 'jwt-e2e', token_type: 'bearer' } }),
  );
  await page.route('**/api/opcua/status', (route) =>
    route.fulfill({ json: { state: 'ONLINE', endpoint: 'opc.tcp://localhost:4840' } }),
  );
  await page.route('**/api/alarms/active', (route) => route.fulfill({ json: [] }));
}

// Drive several live twin frames into the trend for the given loop.
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

// Mutable per-test simulator state, shaped like a single ControllerSimStatus (id 1) plus the
// top-level running flag. The control panel derives `running`, `disturbanceActive`, the preset
// <select> value, etc. from the REST snapshot — so mutating this is what makes assertions pass.
interface SimState {
  running: boolean;
  c: {
    preset: string;
    gain: number;
    tau1: number;
    tau2: number | null;
    dead_time: number;
    step_active: boolean;
    step_amplitude: number;
    noise_active: boolean;
    noise_amplitude: number;
    pid_enabled: boolean;
    pid_kp: number;
    pid_ti: number;
    pid_td: number;
    pid_mode: number;
    pid_cv: number;
    co: number;
    sp: number;
    pv: number;
    error: number;
    process_input: number;
    process_output: number;
    disturbance_output: number;
    auto_sp: null;
    auto_disturbance: null;
  };
}

function freshSimState(): SimState {
  return {
    running: false,
    c: {
      preset: 'FLOW',
      gain: 1.2,
      tau1: 3,
      tau2: null,
      dead_time: 1,
      step_active: false,
      step_amplitude: 0,
      noise_active: false,
      noise_amplitude: 0,
      pid_enabled: false,
      pid_kp: 1,
      pid_ti: 10,
      pid_td: 0,
      pid_mode: 0,
      pid_cv: 0,
      co: 0,
      sp: 50,
      pv: 50,
      error: 0,
      process_input: 0,
      process_output: 0,
      disturbance_output: 0,
      auto_sp: null,
      auto_disturbance: null,
    },
  };
}

// Register the stateful simulator routes. Single controller (id 1) -> no loop selector renders.
async function mockSimulator(page: Page, sim: SimState): Promise<void> {
  const ok = (route: Route) => route.fulfill({ json: { ok: true } });
  const statusBody = () => ({ enabled: true, running: sim.running, controllers: { 1: sim.c } });

  await page.route('**/api/simulator/status', (route) => route.fulfill({ json: statusBody() }));
  await page.route('**/api/simulator/start', (route) => {
    sim.running = true;
    return ok(route);
  });
  await page.route('**/api/simulator/stop', (route) => {
    sim.running = false;
    return ok(route);
  });
  await page.route('**/api/simulator/preset', (route) => {
    const body = route.request().postDataJSON() as { preset: string };
    sim.c.preset = body.preset;
    return ok(route);
  });
  await page.route('**/api/simulator/parameters', ok);
  // POST inject (base path) registered before DELETE remove (/1). The base glob has no trailing
  // wildcard so it cannot match /disturbance/1; branching on method is belt-and-suspenders.
  await page.route('**/api/simulator/disturbance', (route) => {
    if (route.request().method() === 'POST') sim.c.step_active = true;
    return ok(route);
  });
  await page.route('**/api/simulator/disturbance/1', (route) => {
    if (route.request().method() === 'DELETE') sim.c.step_active = false;
    return ok(route);
  });
  await page.route('**/api/simulator/1/co', ok);
  await page.route('**/api/simulator/1/pid/mode', ok);
  await page.route('**/api/simulator/1/auto-sp', ok);
  await page.route('**/api/simulator/1/auto-disturbance', ok);
}

test.describe('Simulator page', () => {
  let sim: SimState;

  test.beforeEach(async ({ page }) => {
    sim = freshSimState();
    await stubWebSocket(page);
    await mockShell(page);
    await mockSimulator(page, sim);

    await page.goto('/simulator');
    await expect(page.getByRole('status', { name: /simulation mode/i })).toBeVisible();

    // Start the twin: /start flips sim.running -> status refetch -> sim-running reads "Running".
    const start = page.getByRole('button', { name: /^start$/i });
    if (await start.isEnabled()) await start.click();
    await expect(page.getByTestId('sim-running')).toHaveText(/running/i);

    // Feed a few live frames so the twin trend has real data.
    await pushFrames(page, 1, 4);
  });

  test('applying a preset is reflected in the panel and keeps the twin trend alive', async ({
    page,
  }) => {
    const trend = page.getByLabel(/twin response trend/i);
    await expect(trend).toBeVisible();

    await page.getByRole('combobox', { name: /process preset/i }).selectOption('TEMPERATURE');

    // The /preset POST sets sim.c.preset and invalidates the status query; the refetch returns
    // the new preset, so the <select> value converges (Playwright auto-retries this assertion).
    await expect(page.getByRole('combobox', { name: /process preset/i })).toHaveValue('TEMPERATURE');

    // Trend stays mounted after the preset change.
    await expect(trend).toBeVisible();
  });

  test('injecting a disturbance enables Remove, removing it disables Remove', async ({ page }) => {
    const remove = page.getByRole('button', { name: /^remove$/i });
    await expect(remove).toBeDisabled();

    await page.getByRole('spinbutton', { name: /amplitude/i }).fill('20');
    await page.getByRole('button', { name: /inject disturbance/i }).click();

    // Inject POST sets step_active:true -> refetch -> disturbanceActive -> Remove enabled.
    await expect(remove).toBeEnabled();

    await remove.click();

    // DELETE sets step_active:false -> refetch -> Remove disabled.
    await expect(remove).toBeDisabled();
  });
});
