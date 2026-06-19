import { expect, test } from '@playwright/test';

// Fatia 2 — command surface e2e. No real backend: all /api/* is mocked via page.route and
// the WebSocket is stubbed via addInitScript (mirrors login-dashboard.spec.ts). The stub
// re-emits an updated `status` frame on demand so SP/mode readouts can be asserted live.

const FULL_CONTROLLER = {
  id: 5,
  name: 'PIC-005',
  description: 'Pressure',
  pv_decimals: 1,
  pv_unit: '°C',
  pid_params: { gain: 1.2, reset: 30, rate: 0, alpha: 0.1, deadband: 0 },
  pid_structure: 'ISA',
  ai_config: {
    engine: 'FUZZY',
    objective: 'SP_TRACKING',
    dead_time_l: 5,
    limit_min: 0.5,
    limit_max: 2,
    rl_fallback_kp: 1,
    rl_fallback_kd: 0,
    rl_learning_rate: 0.001,
    rl_train_interval: 100,
  },
  optimization_enabled: false,
  out_hi_lim: 100,
  out_lo_lim: 0,
  arw_hi_lim: 100,
  arw_lo_lim: 0,
  pv_ftime: 0,
  sp_ftime: 0,
  sp_rate_up: 0,
  sp_rate_dn: 0,
};

const PENDING_REC = {
  controller_id: 5,
  current_kp: 1.2,
  current_ti: 30,
  current_td: 0,
  recommended_kp: 1.5,
  recommended_ti: 25,
  recommended_td: 0,
  reason: 'Fuzzy converged',
  timestamp: 1,
  status: 'pending',
  source: 'FUZZY',
};

const AI_STATUS = {
  controller_id: 5,
  engine: 'FUZZY',
  objective: 'SP_TRACKING',
  speed: 'MEDIUM',
  current_ki: 0.03,
  last_gamma: null as number | null,
  enabled: false,
};

test('fatia 2 commands: setpoint, mode, guarded apply-tuning, AI actions', async ({ page }) => {
  const calls: { setpoint: number; mode: number; applyTuning: number; aiActions: string[] } = {
    setpoint: 0,
    mode: 0,
    applyTuning: 0,
    aiActions: [],
  };

  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ json: { access_token: 'jwt-e2e', token_type: 'bearer' } }),
  );
  await page.route('**/api/controllers', (route) =>
    route.fulfill({ json: [FULL_CONTROLLER] }),
  );
  await page.route('**/api/opcua/status', (route) =>
    route.fulfill({ json: { state: 'ONLINE', endpoint: 'opc.tcp://localhost:4840' } }),
  );
  await page.route('**/api/controllers/5/ai/status', (route) =>
    route.fulfill({ json: AI_STATUS }),
  );
  await page.route('**/api/commands/tuning-recommendations/5', (route) =>
    route.fulfill({ json: PENDING_REC }),
  );

  await page.route('**/api/commands/setpoint', (route) => {
    calls.setpoint += 1;
    route.fulfill({ json: { ok: true, controller_id: 5, detail: null } });
  });
  await page.route('**/api/commands/mode', (route) => {
    calls.mode += 1;
    route.fulfill({ json: { ok: true, controller_id: 5, detail: null } });
  });
  await page.route('**/api/commands/apply-tuning/5', (route) => {
    calls.applyTuning += 1;
    route.fulfill({ json: { ok: true } });
  });
  // POST /controllers/5/ai/{start|stop|pause}
  await page.route(/\/api\/controllers\/5\/ai\/(start|stop|pause)$/, (route) => {
    const m = route.request().url().match(/ai\/(start|stop|pause)$/);
    if (m) calls.aiActions.push(m[1]);
    route.fulfill({ json: { ok: true } });
  });

  // Stub the WebSocket: auth_ok + an initial AUTO status frame; expose a hook to push
  // a fresh status frame from the test so live SP/mode updates can be asserted.
  await page.addInitScript(() => {
    const statusFrame = (sp: number, mode: string) =>
      JSON.stringify({
        type: 'status',
        loop_id: 5,
        seq: 1,
        ts: 1,
        data: {
          pv: { value: 150.2, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
          sp: { value: sp, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
          co: { value: 64, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
          bkcal_in: { value: 0, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
          bkcal_out: { value: 0, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
          mode,
          kp: 1.2,
          ti: 30,
          td: 0,
          integral_val: 0,
          timestamp: '2026-06-19T00:00:00Z',
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
        // Expose a pusher so the test can emit fresh frames.
        (window as unknown as { __pushStatus?: (sp: number, mode: string) => void }).__pushStatus = (
          sp: number,
          mode: string,
        ) => this.onmessage?.(new MessageEvent('message', { data: statusFrame(sp, mode) }));
        setTimeout(() => this.onopen?.(), 0);
      }
      send() {
        setTimeout(() => {
          this.onmessage?.(new MessageEvent('message', { data: JSON.stringify({ type: 'auth_ok' }) }));
          this.onmessage?.(new MessageEvent('message', { data: statusFrame(152, 'AUTO') }));
        }, 0);
      }
      close() {
        this.onclose?.();
      }
    }
    // @ts-expect-error override
    window.WebSocket = StubWS;
  });

  await page.goto('/login');
  await page.getByLabel('Usuário').fill('admin');
  await page.getByLabel('Senha').fill('pw');
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page.getByText('PIC-005')).toBeVisible();
  // Footer mode reflects the AUTO status frame.
  await expect(page.locator('span.numeric', { hasText: /^AUTO$/ })).toBeVisible();

  // --- Setpoint: change SP and click Set -> POST /commands/setpoint fires.
  await page.getByRole('spinbutton', { name: 'Setpoint' }).fill('60');
  await page.getByRole('button', { name: 'Set setpoint' }).click();
  await expect.poll(() => calls.setpoint).toBe(1);

  // --- Mode: switch to MAN -> POST /commands/mode fires; live frame flips the footer.
  await page.getByRole('combobox', { name: 'Mode' }).selectOption('MAN');
  await expect.poll(() => calls.mode).toBe(1);
  await page.evaluate(() => {
    (window as unknown as { __pushStatus?: (sp: number, mode: string) => void }).__pushStatus?.(
      152,
      'MAN',
    );
  });
  await expect(page.locator('span.numeric', { hasText: /^MAN$/ })).toBeVisible();

  // --- Apply tuning: NOT written until the confirmation "Confirm Write" is clicked.
  await page.getByRole('button', { name: 'Apply tuning' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  expect(calls.applyTuning).toBe(0);
  await page.getByRole('button', { name: /confirm write/i }).click();
  await expect.poll(() => calls.applyTuning).toBe(1);

  // --- AI actions: Start / Pause / Stop each POST /controllers/5/ai/{action}.
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await expect.poll(() => calls.aiActions).toContain('start');
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await expect.poll(() => calls.aiActions).toContain('pause');
  await page.getByRole('button', { name: 'Stop', exact: true }).click();
  await expect.poll(() => calls.aiActions).toContain('stop');
});
