import { expect, test } from '@playwright/test';

test('login then dashboard receives a status frame', async ({ page }) => {
  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ json: { access_token: 'jwt-e2e', token_type: 'bearer' } }),
  );
  await page.route('**/api/controllers', (route) =>
    route.fulfill({
      json: [{ id: 5, name: 'PIC-005', description: 'Pressure', pv_decimals: 1, pv_unit: '°C' }],
    }),
  );
  await page.route('**/api/opcua/status', (route) =>
    route.fulfill({ json: { state: 'ONLINE', endpoint: 'opc.tcp://localhost:4840' } }),
  );

  // Stub the WebSocket: emit one auth_ok + one status frame after the auth send.
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
      send() {
        setTimeout(() => {
          this.onmessage?.(new MessageEvent('message', { data: JSON.stringify({ type: 'auth_ok' }) }));
          this.onmessage?.(
            new MessageEvent('message', {
              data: JSON.stringify({
                type: 'status', loop_id: 5, seq: 1, ts: 1,
                data: { pv: 150.2, sp: 152, co: 64, mode: 'AUTO' },
              }),
            }),
          );
        }, 0);
      }
      close() { this.onclose?.(); }
    }
    // @ts-expect-error override
    window.WebSocket = StubWS;
  });

  await page.goto('/login');
  await page.getByLabel('Usuário').fill('admin');
  await page.getByLabel('Senha').fill('pw');
  await page.getByRole('button', { name: 'Entrar' }).click();

  await expect(page.getByText('PIC-005')).toBeVisible();
  await expect(page.getByText(/150\.2/)).toBeVisible();
});
