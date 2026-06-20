import { expect, test, type Page } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// ESM: __dirname is not defined under Vite's "type": "module", so derive it from import.meta.url.
const here = path.dirname(fileURLToPath(import.meta.url));

// Fatia 7 — projects e2e. No real backend: all /api/* is mocked via page.route and the WebSocket
// is stubbed via addInitScript (mirrors executive-dashboard.spec.ts / simulator.spec.ts). The
// /projects route is RequireAuth-gated, so the token is seeded into sessionStorage before load.
//
// The project routes are STATEFUL: a closure `projects` array is the source of truth. Each
// mutation (create / import / delete) mutates it and invalidates the ['projects','list'] query,
// so the page refetches GET /project/list and the table converges — Playwright's auto-retrying
// assertions wait for that refetch without any arbitrary sleep.

interface ProjectItem {
  name: string;
  controller_count: number;
  size_bytes: number;
}

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

async function mockRest(page: Page): Promise<void> {
  const projects: ProjectItem[] = [];

  await page.route('**/api/auth/login', (route) =>
    route.fulfill({ json: { access_token: 'jwt-e2e', token_type: 'bearer' } }),
  );
  await page.route('**/api/alarms/active', (route) => route.fulfill({ json: [] }));
  await page.route('**/api/opcua/status', (route) =>
    route.fulfill({ json: { state: 'ONLINE', endpoint: 'opc.tcp://x:4840' } }),
  );

  await page.route('**/api/project/list', (route) => route.fulfill({ json: { projects } }));
  await page.route('**/api/project/new', (route) => {
    const body = route.request().postDataJSON() as { name: string };
    projects.push({ name: body.name, controller_count: 0, size_bytes: 100 });
    return route.fulfill({ json: { name: body.name, path: `/p/${body.name}.spid`, controller_count: 0 } });
  });
  // import is multipart — the file is not parsed; just record a `sample` project.
  await page.route('**/api/project/import', (route) => {
    projects.push({ name: 'sample', controller_count: 0, size_bytes: 200 });
    return route.fulfill({ json: { name: 'sample', path: '/p/sample.spid', controller_count: 0 } });
  });
  await page.route('**/api/project/open', (route) => {
    const body = route.request().postDataJSON() as { name: string };
    return route.fulfill({ json: { name: body.name, path: 'x', controller_count: 0 } });
  });
  // DELETE /project/<name> — decode the trailing path segment and filter it out.
  await page.route('**/api/project/**', (route) => {
    if (route.request().method() !== 'DELETE') return route.fallback();
    const segment = route.request().url().split('/').pop() ?? '';
    const name = decodeURIComponent(segment);
    const idx = projects.findIndex((p) => p.name === name);
    if (idx >= 0) projects.splice(idx, 1);
    return route.fulfill({ status: 204, body: '' });
  });
}

test.describe('Projects page', () => {
  test.beforeEach(async ({ page }) => {
    await stubWebSocket(page);
    await mockRest(page);
  });

  test('create a project, import a .spid, open it, then delete the created one', async ({ page }) => {
    // confirmDestructive defaults to true -> window.confirm fires on delete. Accept every dialog.
    page.on('dialog', (d) => void d.accept());

    await page.goto('/projects');

    // Create: form submit -> POST /project/new -> list invalidated -> refetch shows the new row.
    await page.getByLabel(/new project name/i).fill('e2e-temp');
    await page.getByRole('button', { name: /^create$/i }).click();
    await expect(page.getByRole('cell', { name: 'e2e-temp' })).toBeVisible();

    // Import: setInputFiles on the .spid input -> POST /project/import -> refetch shows `sample`.
    await page
      .getByLabel(/import .spid/i)
      .setInputFiles(path.join(here, 'fixtures', 'sample.spid'));
    await expect(page.getByRole('cell', { name: 'sample' })).toBeVisible();

    // Open the imported project's Open button (POST /project/open). Assert no crash: the row stays.
    const sampleRow = page.getByRole('row', { name: /sample/i });
    await sampleRow.getByRole('button', { name: /^open$/i }).click();
    await expect(page.getByRole('cell', { name: 'sample' })).toBeVisible();

    // Delete the created project: DELETE /project/e2e-temp -> filtered out -> refetch drops the row.
    const tempRow = page.getByRole('row', { name: /e2e-temp/i });
    await tempRow.getByRole('button', { name: /^delete$/i }).click();
    await expect(page.getByRole('cell', { name: 'e2e-temp' })).toHaveCount(0);
  });
});
