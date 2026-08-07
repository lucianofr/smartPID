import { expect, test, type Page } from '@playwright/test';
import { gotoDashboard, loopCard, type HarnessLoop } from './helpers/harness';

/**
 * E2E-047 — backend outage and resync.
 *
 * Measured defect, against the real daemon behind the Vite dev proxy: killing
 * the backend left the browser socket in `readyState: OPEN` with no `error`
 * and no `close` — for 31 s the dashboard showed no banner, no reconnect cue
 * and no error while rendering pre-outage PV as if live. After the daemon was
 * restarted and the plant driven to 47.9 / 18.0 / 108.0 / 42.0, the UI still
 * read 14.0 / 54.0 / 83.9 / 113.9. Only a manual reload recovered.
 *
 * Both outage shapes are covered here. The second — open and silent — is the
 * shape that actually happened; a spec that only closes the socket would pass
 * against the broken build.
 */

const TIC047: HarnessLoop = {
  id: 1,
  name: 'TIC-047',
  description: 'Temperatura',
  euMin: 0,
  euMax: 200,
  unit: '°C',
  pv: 40,
  sp: 50,
  co: 25,
  mode: 'AUTO',
  executionMode: 'DDC',
};

const banner = (page: Page) => page.getByTestId('connection-banner');
const cardPv = (page: Page) => loopCard(page, TIC047.name).getByRole('meter', { name: 'PV' });

/** Upstream up/down — the harness stub's model of a dead daemon. */
const blockSocket = (page: Page, blocked: boolean) =>
  page.evaluate((b: boolean) => Reflect.get(window, '__spidBlockSocket')(b), blocked);

/** Both halves of "this number is current", asserted together on purpose. */
async function expectLiveValue(page: Page, pv: number): Promise<void> {
  await expect(cardPv(page)).toHaveAttribute('aria-valuenow', String(pv));
  await expect(cardPv(page)).toHaveAttribute('aria-valuetext', `${pv.toFixed(1)} °C`);
}

test.beforeEach(async ({ page }) => {
  await gotoDashboard(page, { loops: [TIC047] });
  await expectLiveValue(page, TIC047.pv);
});

test('a healthy load says nothing — the banner is not background noise', async ({ page }) => {
  await expect(banner(page)).toBeHidden();
});

test('a dropped socket raises the offline banner and marks every reading', async ({ page }) => {
  await blockSocket(page, true);
  await page.evaluate(() => Reflect.get(window, '__spidCloseSocket')(1006));

  // Immediate, because the close is reported. Persistent, because every
  // reconnect attempt keeps failing while upstream is down.
  await expect(banner(page)).toHaveText(/SEM CONEXÃO/);
  await expect(banner(page)).toHaveAttribute('aria-live', 'assertive');
  await expect(banner(page)).toHaveText(/NÃO são atuais/);

  // The reading is retained — blanking it would throw away the operator's last
  // known state — but nothing about it still claims to be current.
  await expect(cardPv(page)).toHaveAttribute('aria-valuetext', /desatualizado/, {
    timeout: 15_000,
  });
  await expect(cardPv(page)).toHaveAttribute('aria-valuenow', String(TIC047.pv));
});

test('an open socket that goes silent is caught, recycled and resynced — no reload', async ({
  page,
}) => {
  test.slow(); // the dead-man timer is deliberately generous vs the 1 Hz frame rate

  // THE DEFECT: upstream dies but the socket never closes. No `onclose`, no
  // `onerror` — the client is entirely on its own here.
  await blockSocket(page, true);

  await expect(banner(page)).toHaveText(/DADOS DESATUALIZADOS/, { timeout: 15_000 });
  await expect(cardPv(page)).toHaveAttribute('aria-valuetext', /desatualizado/);
  await expect(cardPv(page)).toHaveAttribute('aria-valuenow', String(TIC047.pv));

  // The watchdog presumes the socket dead and replaces it; upstream is still
  // down, so the replacement closes 1006 and the banner escalates.
  await expect(banner(page)).toHaveText(/SEM CONEXÃO/, { timeout: 20_000 });

  // The plant moves while the operator is blind to it, exactly as in the live run.
  await page.evaluate(() => Reflect.get(window, '__spidSetPv')(1, 96));

  // Upstream comes back. Nobody reloads anything.
  await blockSocket(page, false);
  await expect(banner(page)).toBeHidden({ timeout: 30_000 });

  await page.evaluate(() => Reflect.get(window, '__spidEmitFrames')(1));
  await expectLiveValue(page, 96);
});
