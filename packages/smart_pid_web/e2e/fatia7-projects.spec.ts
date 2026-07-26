import { expect, test, type Page } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { mockRest, seedSession, stubWebSocket } from './helpers/harness';

// ESM: __dirname is not defined under Vite's "type": "module", so derive it from import.meta.url.
const here = path.dirname(fileURLToPath(import.meta.url));

// Fatia 7 — projects e2e. No real backend: the shared phase-4 harness stubs
// `/auth/me`, the complete §7 resync set and a monotonic-`seq` socket; the
// project doubles below are registered after it and therefore win.
//
// /projects is `adminOnly`, so the harness role must be admin and the token has
// to be seeded before first paint.
//
// The project routes are STATEFUL: a closure `projects` array is the source of
// truth. Each mutation (create / import / delete) mutates it and invalidates the
// ['projects','list'] query, so the page refetches GET /project/list and the
// table converges — Playwright's auto-retrying assertions wait for that refetch
// without any arbitrary sleep.

interface ProjectItem {
  name: string;
  controller_count: number;
  size_bytes: number;
}

async function mockProjects(page: Page): Promise<void> {
  const projects: ProjectItem[] = [];

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
    await seedSession(page);
    await stubWebSocket(page);
    await mockRest(page, { role: 'admin' });
    await mockProjects(page);
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

    // Open the imported project's Open button (POST /project/open). ProjectList.tsx navigates to
    // the dashboard (`/`) on success (commit 48c816d — mirrors WelcomeDialog), so the projects
    // table unmounts. Assert the navigation landed on the dashboard, then return to /projects.
    const sampleRow = page.getByRole('row', { name: /sample/i });
    await sampleRow.getByRole('button', { name: /^open$/i }).click();
    await expect(page).toHaveURL(/\/$/);

    // Back to the projects list to delete the temp project.
    await page.goto('/projects');
    await expect(page.getByRole('cell', { name: 'e2e-temp' })).toBeVisible();

    // Delete the created project: DELETE /project/e2e-temp -> filtered out -> refetch drops the row.
    const tempRow = page.getByRole('row', { name: /e2e-temp/i });
    await tempRow.getByRole('button', { name: /^delete$/i }).click();
    await expect(page.getByRole('cell', { name: 'e2e-temp' })).toHaveCount(0);
  });
});
