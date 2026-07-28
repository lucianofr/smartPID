import { expect, test, type Page } from '@playwright/test';
import { mockRest, seedSession, stubWebSocket } from './helpers/harness';

// Fatia 7 — OPC-UA connection e2e. No real backend: the shared phase-4 harness
// stubs `/auth/me`, the complete §7 resync set and a monotonic-`seq` socket, and
// this spec layers the stateful opcua doubles on top. Playwright matches routes
// in REVERSE registration order, so the overrides below win over the harness.
//
// /connection is `adminOnly`, so the harness role must be admin AND the token
// must be seeded before first paint — without it the guard bounces to /login.
//
// The opcua routes are STATEFUL: a closure holds `opcState` + `endpoint`. POST
// /opcua/connect flips opcState to ONLINE, and the connect mutation's onSuccess
// does setQueryData(queryKeys.opcuaStatus) with the POST response — so the panel
// reads ONLINE immediately (no wait on the 5s poll).

// Stateful OPC-UA REST doubles. One Variable node so browse and search both
// render a single FT-101 tag.
async function mockOpcua(page: Page): Promise<void> {
  let opcState = 'OFFLINE';
  let endpoint = 'opc.tcp://x:4840';
  const FT_101 = { node_id: 'ns=2;s=FT-101', display_name: 'FT-101', node_class: 'Variable' };

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
    await seedSession(page);
    await stubWebSocket(page);
    await mockRest(page, { role: 'admin' });
    await mockOpcua(page);
  });

  test('configure OPC endpoint, connect, and browse/search tags', async ({ page }) => {
    await page.goto('/connection');

    // Fill endpoint and connect. The connect mutation setQueryData(opcuaStatus)
    // makes the panel state ONLINE immediately from the POST response.
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
