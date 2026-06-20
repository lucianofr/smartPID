import { expect, test } from '@playwright/test';

// Fatia 3 — alarm GAP-3a lifecycle e2e. No real backend: the alarm REST endpoints are
// served by a stateful in-test double (page.route), auth is seeded into sessionStorage via
// addInitScript (so /alarms passes RequireAuth and the token survives page.reload), and the
// realtime WebSocket is stubbed (mirrors login-dashboard.spec.ts / fatia2-commands.spec.ts).
//
// The /alarms route mounts AppShell (TopBar + NavRail + AlarmBar) + AlarmPanel inside
// RealtimeProvider. Both AlarmBar and AlarmPanel read GET /api/alarms/active; ack fires
// POST /api/alarms/{id}/ack. AppShell receives opcDown={false} (hardcoded) so no OPC fetch.

const STORAGE_KEY = 'smart-pid-token';

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

  // Seed the auth session token so RequireAuth admits /alarms and it survives page.reload().
  await page.addInitScript(
    ({ key }) => {
      sessionStorage.setItem(key, 'jwt-e2e');
      // Suppress the post-login WelcomeDialog so its overlay does not intercept clicks.
      sessionStorage.setItem('spid.welcome-seen', '1');
    },
    { key: STORAGE_KEY },
  );

  // Stub the WebSocket opened by RealtimeProvider (alarm rows come from REST, not the WS).
  await page.addInitScript(() => {
    class StubWS extends EventTarget {
      url: string;
      readyState = 1;
      onopen: (() => void) | null = null;
      onmessage: ((e: MessageEvent) => void) | null = null;
      onclose: (() => void) | null = null;
      constructor(url: string) {
        super();
        this.url = url;
        setTimeout(() => this.onopen?.(), 0);
      }
      send() {}
      close() {
        this.onclose?.();
      }
    }
    // @ts-expect-error override
    window.WebSocket = StubWS;
  });
});

test('alarm fires → appears → ack → state ACKNOWLEDGED (not removed); clear only after condition ceases', async ({
  page,
}) => {
  await page.goto('/alarms');

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
  await page.goto('/alarms');
  await expect(page.getByTestId('alarm-row-1')).toHaveCount(0);
});
