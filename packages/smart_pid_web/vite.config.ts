import { fileURLToPath, URL } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [tailwindcss(), react()],
  // Emit dist/.vite/manifest.json so the perf-budget gate (scripts/check-bundle.mjs)
  // can reliably resolve the app-page entry chunk + its CSS.
  build: {
    manifest: true,
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // NO changeOrigin here: the backend authorises the WebSocket upgrade
      // against the browser's Origin (allowed_ws_origins). Rewriting it to the
      // proxy target makes every dev-server socket fail auth with close 4401.
      '/ws': { target: 'http://127.0.0.1:8000', ws: true },
    },
  },
});
