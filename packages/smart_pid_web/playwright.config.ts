import { defineConfig } from '@playwright/test';

/**
 * The port is configurable because this repo is worked on in git worktrees, and
 * `reuseExistingServer` cannot tell one checkout's dev server from another's: a
 * vite already listening on the default port makes Playwright silently test the
 * OTHER tree — every assertion still runs, against the wrong source. `--strictPort`
 * turns that collision into a startup error instead of a silent port hop.
 *
 *   SPID_WEB_PORT=5174 npm run test:e2e
 */
const PORT = process.env.SPID_WEB_PORT ?? '5173';
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: './e2e',
  use: { baseURL: BASE_URL },
  webServer: {
    command: `npm run dev -- --port ${PORT} --strictPort`,
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
  },
});
