import { fileURLToPath, URL } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

/** The monorepo root — where the daemon's `.env` lives, one level above `packages/`. */
const REPO_ROOT = fileURLToPath(new URL('../..', import.meta.url));

/**
 * The dev proxy follows the daemon instead of hardcoding its port.
 *
 * Pinning 8000 here meant that any operator whose `.env` set a different port
 * got a dev server that looked healthy and answered every `/api` call with a
 * connection error — the two numbers drifted silently because nothing compared
 * them. A real `.env` in this repo carries `SPID_API_PORT=8537`.
 *
 * Two subtleties this has to get right:
 *
 * 1. The daemon's `.env` sits at the REPO ROOT, while Vite's `envDir` defaults
 *    to its own root (`packages/smart_pid_web`). So `loadEnv` is pointed at the
 *    repo root explicitly — otherwise it reads a file that does not exist and
 *    the drift survives. The empty prefix loads unprefixed `SPID_*` names;
 *    those values stay in Node and are NEVER handed to `define`, so nothing
 *    from `.env` (which also holds `SPID_JWT_SECRET`) reaches the client bundle.
 *
 * 2. `SPID_API_HOST` is a BIND address on the backend side, so `0.0.0.0` is a
 *    legal value there and a meaningless one here: as a proxy target it has to
 *    become a routable host. Map it to loopback rather than passing it through.
 *
 * Shell environment wins over the file, matching how the daemon itself resolves
 * settings (pydantic-settings reads the process env first).
 */
function resolveApiTarget(mode: string): string {
  const fileEnv = loadEnv(mode, REPO_ROOT, '');
  const pick = (key: string, fallback: string): string =>
    process.env[key] ?? fileEnv[key] ?? fallback;

  const rawHost = pick('SPID_API_HOST', '127.0.0.1');
  const host = rawHost === '0.0.0.0' || rawHost === '' ? '127.0.0.1' : rawHost;
  return `http://${host}:${pick('SPID_API_PORT', '8000')}`;
}

/** Kept in sync with playwright.config.ts, which drives `npm run dev`. */
const WEB_PORT = Number(process.env.SPID_WEB_PORT ?? 5173);

export default defineConfig(({ mode }) => {
  const apiTarget = resolveApiTarget(mode);

  return {
    plugins: [tailwindcss(), react()],
    // Emit dist/.vite/manifest.json so the perf-budget gate
    // (scripts/check-bundle.mjs) can reliably resolve the app-page entry chunk
    // and its CSS.
    build: {
      manifest: true,
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      // `true` (not '127.0.0.1'): Node's dual-stack wildcard bind is the only
      // way to accept both 127.0.0.1 and ::1. This host resolves "localhost"
      // to the IPv6 loopback first, so a plain '127.0.0.1' bind is unreachable
      // by any tool (e.g. the TestSprite tunnel agent) that addresses the dev
      // server as "localhost" instead of the literal IPv4 address — it hits
      // dead ::1 and the request never arrives (ERR_EMPTY_RESPONSE).
      host: true,
      port: WEB_PORT,
      // A worktree checkout must never silently borrow the sibling checkout's
      // dev server: without this, `reuseExistingServer` in playwright.config.ts
      // runs the whole suite against the wrong source tree and still reports
      // green. That cost a full round of false green in this repo.
      strictPort: true,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
        // NO changeOrigin here: the backend authorises the WebSocket upgrade
        // against the browser's Origin (allowed_ws_origins). Rewriting it to
        // the proxy target makes every dev-server socket fail auth with 4401.
        '/ws': { target: apiTarget, ws: true },
      },
    },
    preview: {
      // host and proxy inherit from `server` above; only port needs pinning
      // to match the port already registered with the TestSprite tunnel.
      port: WEB_PORT,
    },
  };
});
