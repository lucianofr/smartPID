import { expect, test, type Page } from '@playwright/test';
import { mockRest, seedSession, stubWebSocket } from './helpers/harness';

// Alarm GAP-3a lifecycle e2e. No real backend: the alarm REST endpoints are served
// by a stateful in-test double (page.route) layered over the shared phase-4 harness,
// auth is seeded into sessionStorage via addInitScript (so /alarms passes RequireAuth
// and the token survives page.reload), and the realtime WebSocket is stubbed.
//
// `mockRest` supplies BOTH prerequisites the panel silently depends on:
//   1. GET /api/auth/me — `useCan('alarms.ack')` is deny-by-default, so without it
//      the per-row ACK button never renders.
//   2. The full §7 resync set — React StrictMode double-invokes effects and always
//      resyncs on first load; a failure there recycles the socket forever.
// `stubWebSocket` emits monotonically increasing `seq`, so the phase-3 tracker never
// sees a fake gap and never forces an extra resync.
//
// The /alarms route mounts AppShell (top bar + command palette) around AlarmsPage:
// AlarmPanel on the default `Ativos` tab plus the persistent §6.9 alarm footer. Both
// AlarmPanel and the footer read GET /api/alarms/active; a row ack fires
// POST /api/alarms/{id}/ack.

// Stateful in-test backend double for the alarm endpoints.
const state = {
  alarms: [] as Array<Record<string, unknown>>,
};

test.beforeEach(async ({ page }) => {
  state.alarms = [
    {
      id: 1,
      controller_id: 7,
      controller_name: 'FIC-101',
      alarm_type: 'HIHI',
      priority: 'CRITICAL',
      value: 99,
      limit: 90,
      timestamp: new Date().toISOString(),
      cleared_at: null,
      acknowledged: 0,
      ack_by_user: null,
      ack_at: null,
      status: 'UNACKNOWLEDGED',
    },
  ];

  // Seed the auth session token so RequireAuth admits /alarms and it survives page.reload().
  await seedSession(page);
  await stubWebSocket(page);
  await mockRest(page);

  // Registered AFTER the harness so these stateful handlers take precedence:
  // Playwright matches the most recently registered route first.

  // Admin-only threshold CRUD — not part of the shared harness (the dashboard
  // never reads it), so the alarm page has to supply it.
  await page.route('**/api/controllers/*/alarm-config', (route) =>
    route.fulfill({
      json: {
        controller_id: 1,
        thresholds: [
          { alarm_type: 'HIHI', priority: 'CRITICAL', limit: 95, enabled: true, deadband: 0.5, delay_on_s: 0, delay_off_s: 0 },
          { alarm_type: 'HI', priority: 'WARNING', limit: 80, enabled: true, deadband: 0.5, delay_on_s: 0, delay_off_s: 0 },
          { alarm_type: 'LO', priority: 'WARNING', limit: 20, enabled: true, deadband: 0.5, delay_on_s: 0, delay_off_s: 0 },
          { alarm_type: 'LOLO', priority: 'CRITICAL', limit: 5, enabled: true, deadband: 0.5, delay_on_s: 0, delay_off_s: 0 },
        ],
      },
    }),
  );

  // get_active filters out alarms that are BOTH cleared AND acknowledged (NOT(cleared AND acked)).
  await page.route('**/api/alarms/active', (route) =>
    route.fulfill({ json: state.alarms.filter((a) => !(a.cleared_at && a.acknowledged)) }),
  );

  // Ack does NOT clear — it only flips acknowledged/status.
  await page.route('**/api/alarms/1/ack', (route) => {
    const a = state.alarms.find((x) => x.id === 1);
    if (a) {
      a.acknowledged = 1;
      a.ack_by_user = 'admin';
      a.status = a.cleared_at ? 'CLEARED_UNACK' : 'ACKNOWLEDGED';
    }
    return route.fulfill({ json: { status: 'acknowledged' } });
  });

  await page.route('**/api/alarms/ack-all', (route) => {
    for (const a of state.alarms) {
      a.acknowledged = 1;
      a.status = a.cleared_at ? 'CLEARED_UNACK' : 'ACKNOWLEDGED';
    }
    return route.fulfill({ json: { status: 'acknowledged', acknowledged_count: 1, controller_ids: [7] } });
  });
});

/**
 * This file sorts first, so its first navigation pays the dev server's cold
 * on-demand compile. Gate on the shell before the row assertions run on their
 * 5 s default — a slow first transform must not read as a missing panel.
 */
async function gotoAlarms(page: Page): Promise<void> {
  await page.goto('/alarms');
  await expect(page.getByRole('tab', { name: 'Ativos' })).toBeVisible({ timeout: 60_000 });
}

test('alarm fires → appears → ack → state ACKNOWLEDGED (not removed); clear only after condition ceases', async ({
  page,
}) => {
  await gotoAlarms(page);

  // Appears live from GET /alarms/active.
  const row = page.getByTestId('alarm-row-1');
  await expect(row).toBeVisible();
  await expect(row.getByText('UNACKNOWLEDGED')).toBeVisible();

  // Ack → state becomes ACKNOWLEDGED and the row is NOT removed (ack ≠ clear).
  await row.getByRole('button', { name: /ack/i }).click();
  await expect(page.getByTestId('alarm-row-1')).toBeVisible();
  await expect(page.getByTestId('alarm-row-1').getByText('ACKNOWLEDGED')).toBeVisible();

  // Condition ceases (cleared) AFTER ack → cleared+acked → row leaves the active list.
  const a = state.alarms.find((x) => x.id === 1);
  if (a) a.cleared_at = new Date().toISOString(); // get_active filters NOT(cleared AND acked)
  await gotoAlarms(page);
  await expect(page.getByTestId('alarm-row-1')).toHaveCount(0);
});

test('severity, history and admin configuration are all reachable from /alarms', async ({
  page,
}) => {
  await gotoAlarms(page);

  // Severity is text + shape, never color alone (§6.4).
  const row = page.getByTestId('alarm-row-1');
  await expect(row).toContainText('CRITICAL');
  await expect(row.locator('.sev-icon--octagon')).toBeVisible();

  // The plant-wide footer stays mounted on the alarm page itself.
  await expect(page.getByTestId('count-critical')).toContainText('CRIT');
  await expect(page.getByRole('button', { name: 'ACK ALL' })).toBeEnabled();

  await page.getByRole('tab', { name: 'Histórico' }).click();
  await expect(page.getByRole('button', { name: 'Aplicar filtros' })).toBeVisible();
  await expect(page.getByLabel('Prioridade')).toBeVisible();

  // alarms.configure is admin-only; the harness session is an admin.
  await page.getByRole('tab', { name: 'Configuração' }).click();
  await expect(page.getByRole('form', { name: 'Configuração de alarmes' })).toBeVisible();
});

test('bulk ACK ALL clears the unacknowledged demand from the footer', async ({ page }) => {
  await gotoAlarms(page);
  await expect(page.getByTestId('alarm-row-1').getByText('UNACKNOWLEDGED')).toBeVisible();

  await page.getByRole('button', { name: 'ACK ALL' }).click();

  await expect(page.getByTestId('alarm-row-1').getByText('ACKNOWLEDGED')).toBeVisible();
  await expect(page.getByRole('button', { name: 'ACK ALL' })).toBeDisabled();
});
