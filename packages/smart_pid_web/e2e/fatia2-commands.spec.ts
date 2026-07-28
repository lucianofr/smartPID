import { expect, test } from '@playwright/test';

// Command surface e2e. No real backend: every /api/* route is mocked with
// page.route and the WebSocket is stubbed via addInitScript. The stub re-emits
// an updated `status` frame on demand so SP/mode readouts can be asserted live.
//
// Two harness rules apply here as well (see helpers/harness.ts): GET /auth/me is
// always stubbed — `useCan` is deny-by-default, so the admin surfaces would not
// render without it — and every emitted envelope advances `seq` monotonically,
// because a repeated seq reads as a gap and forces a §7 resync (which React
// StrictMode already runs once on mount), so the whole resync set is stubbed.

const FULL_CONTROLLER = {
  id: 5,
  name: 'PIC-005',
  description: 'Pressure',
  mode: 'AUTO',
  pv: 150.2,
  sp: 152,
  co: 64,
  pv_scale: { eu_min: 0, eu_max: 300, unit: '°C' },
  out_scale: { eu_min: 0, eu_max: 100, unit: '%' },
  permitted_modes: ['MAN', 'AUTO'],
  sp_lo_lim: 0,
  sp_hi_lim: 300,
  process_speed: 'MEDIUM',
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
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ json: { user_id: 1, username: 'admin', role: 'admin' } }),
  );
  await page.route('**/api/controllers', (route) => route.fulfill({ json: [FULL_CONTROLLER] }));
  await page.route('**/api/opcua/status', (route) =>
    route.fulfill({ json: { state: 'ONLINE', endpoint: 'opc.tcp://localhost:4840' } }),
  );
  // §7 resync set — StrictMode's second mount runs a resync on first load.
  await page.route('**/api/alarms/active', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/alarms/history**', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/alarms/ack-all', (route) => route.fulfill({ json: { acked: 0 } }));
  await page.route('**/api/simulator/status', (route) =>
    route.fulfill({ json: { running: false, controllers: [] } }),
  );
  await page.route('**/api/controllers/5/ai/status', (route) => route.fulfill({ json: AI_STATUS }));
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
    let seq = 0;
    const statusFrame = (sp: number, mode: string) => {
      seq += 1;
      return JSON.stringify({
        type: 'status',
        loop_id: 5,
        seq,
        ts: 1750000000 + seq,
        data: {
          controller_id: 5,
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
    };

    class StubWS extends EventTarget {
      url: string;
      readyState = 1;
      onopen: (() => void) | null = null;
      onmessage: ((e: MessageEvent) => void) | null = null;
      onclose: ((e: { code: number }) => void) | null = null;
      constructor(url: string) {
        super();
        this.url = url;
        // Expose a pusher so the test can emit fresh frames.
        const hooked = window as unknown as {
          __pushStatus?: (sp: number, mode: string) => void;
        };
        hooked.__pushStatus = (sp: number, mode: string) =>
          this.onmessage?.(new MessageEvent('message', { data: statusFrame(sp, mode) }));
        setTimeout(() => this.onopen?.(), 0);
      }
      send() {
        setTimeout(() => {
          this.onmessage?.(new MessageEvent('message', { data: JSON.stringify({ type: 'auth_ok' }) }));
          this.onmessage?.(new MessageEvent('message', { data: statusFrame(152, 'AUTO') }));
        }, 0);
      }
      close() {
        this.onclose?.({ code: 1000 });
      }
    }
    // @ts-expect-error override
    window.WebSocket = StubWS;
  });

  // Suppress the post-login WelcomeDialog so its overlay does not intercept clicks.
  await page.addInitScript(() => sessionStorage.setItem('spid.welcome-seen', '1'));

  await page.goto('/login');
  await page.getByLabel('Usuário').fill('admin');
  await page.getByLabel('Senha').fill('pw');
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page.getByText('PIC-005').first()).toBeVisible();
  // The card mode badge reflects the AUTO status frame. Scoped to the card: the
  // faceplate renders the same live mode in an identical `span.numeric` badge.
  const card = page.getByRole('listitem').filter({ hasText: 'PIC-005' });
  await expect(card.locator('span.numeric', { hasText: /^AUTO$/ })).toBeVisible();

  // --- Setpoint: change SP and click Set -> POST /commands/setpoint fires.
  await page.getByRole('spinbutton', { name: 'Setpoint' }).fill('60');
  await page.getByRole('button', { name: 'Set setpoint' }).click();
  await expect.poll(() => calls.setpoint).toBe(1);

  // --- Mode: switch to MAN -> POST /commands/mode fires; live frame flips the badge.
  await page.getByRole('combobox', { name: 'Mode' }).selectOption('MAN');
  await expect.poll(() => calls.mode).toBe(1);
  await page.evaluate(() => {
    // Installed by the WebSocket stub above; the compiler cannot see that.
    const hooked = window as unknown as { __pushStatus?: (sp: number, mode: string) => void };
    hooked.__pushStatus?.(152, 'MAN');
  });
  await expect(card.locator('span.numeric', { hasText: /^MAN$/ })).toBeVisible();

  // --- Apply tuning: NOT written until the confirmation "Confirm Write" is clicked.
  await page.getByRole('button', { name: 'Apply tuning' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  expect(calls.applyTuning).toBe(0);
  await page.getByRole('button', { name: /confirm write/i }).click();
  await expect.poll(() => calls.applyTuning).toBe(1);
  await expect(page.getByRole('dialog')).toHaveCount(0);

  // --- AI actions: Start / Pause / Stop each POST /controllers/5/ai/{action}.
  await page.getByRole('button', { name: 'Start', exact: true }).click();
  await expect.poll(() => calls.aiActions).toContain('start');
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await expect.poll(() => calls.aiActions).toContain('pause');
  await page.getByRole('button', { name: 'Stop', exact: true }).click();
  await expect.poll(() => calls.aiActions).toContain('stop');
});
