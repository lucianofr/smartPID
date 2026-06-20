import { expect, test, type Page } from '@playwright/test';

// Fatia 7 — OPC-UA connection e2e. No real backend: all /api/* is mocked via page.route and the
// WebSocket is stubbed via addInitScript (mirrors executive-dashboard.spec.ts / simulator.spec.ts).
// The /connection route is RequireAuth-gated, so the token is seeded into sessionStorage before
// load (STORAGE_KEY = 'smart-pid-token'); WITHOUT it /connection redirects to /login.
//
// The opcua routes are STATEFUL: a closure holds `opcState` + `endpoint`. POST /opcua/connect
// flips opcState to ONLINE, and the connect mutation's onSuccess does setQueryData(['opcua-status'])
// with the POST response — so the panel reads ONLINE immediately (no wait on the 5s poll).

// Stub the WebSocket: seed the auth token and emit `auth_ok` on send(). No live frames are needed
// for the connection page, but the RealtimeProvider still opens a socket on mount.
async function stubWebSocket(page: Page): Promise<void> {
  await page.addInitScript(() => {
    sessionStorage.setItem('smart-pid-token', 'jwt-e2e');
    // Skip the post-login WelcomeDialog, which renders as a modal overlay that intercepts clicks.
    sessionStorage.setItem('spid.welcome-seen', '1');

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

// Stateful OPC-UA REST doubles + AppShell deps (login, AlarmBar). One Variable node so browse and
// search both render a single FT-101 tag.
async function mockRest(page: Page): Promise<void> {
  let opcState = 'OFFLINE';
  let endpoint = 'opc.tcp://x:4840';
  const FT_101 = { node_id: 'ns=2;s=FT-101', display_name: 'FT-101', node_class: 'Variable' };

  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ json: { access_token: 'jwt-e2e', token_type: 'bearer' } }),
  );
  await page.route('**/api/alarms/active', (route) => route.fulfill({ json: [] }));

  await page.route('**/api/opcua/status', (route) =>
    route.fulfill({ json: { state: opcState, endpoint } }),
  );
  await page.route('**/api/opcua/endpoint', (route) => {
    const body = route.request().postDataJSON() as { endpoint?: string };
    if (body?.endpoint) endpoint = body.endpoint;
    return route.fulfill({ json: { state: opcState, endpoint } });
  });
  await page.route('**/api/opcua/connect', (route) => {
    const body = route.request().postDataJSON() as { endpoint?: string } | null;
    if (body?.endpoint) endpoint = body.endpoint;
    opcState = 'ONLINE';
    return route.fulfill({ json: { state: 'ONLINE', endpoint } });
  });
  // browse (folder children) and search both return the single FT-101 Variable.
  await page.route('**/api/opcua/browse/**', (route) =>
    route.fulfill({ json: { parent_node_id: 'i=85', children: [FT_101] } }),
  );
  await page.route('**/api/opcua/search**', (route) =>
    route.fulfill({ json: { query: 'FT', results: [FT_101] } }),
  );
}

test.describe('Connection page', () => {
  test.beforeEach(async ({ page }) => {
    await stubWebSocket(page);
    await mockRest(page);
  });

  test('configure OPC endpoint, connect, and browse/search tags', async ({ page }) => {
    await page.goto('/connection');

    // Fill endpoint and connect. The connect mutation setQueryData(['opcua-status']) makes the
    // panel state ONLINE immediately from the POST response.
    await page.getByLabel(/endpoint/i).fill('opc.tcp://127.0.0.1:4840');
    await page.getByRole('button', { name: /^connect$/i }).click();

    await expect(page.getByText(/ONLINE/)).toBeVisible();

    // Tag browser: searchbox is always present; typing triggers /opcua/search, which returns FT-101.
    const search = page.getByRole('searchbox');
    await expect(search).toBeVisible();
    await search.fill('FT');
    await expect(page.getByText('FT-101')).toBeVisible();
  });
});
