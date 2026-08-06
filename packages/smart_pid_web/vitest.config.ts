import { fileURLToPath, URL } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      // Repo root has no package.json (uv workspace); allow cross-package tests/.
      allow: ['../..'],
    },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    passWithNoTests: true,
    include: ['src/**/*.test.{ts,tsx}', '../../tests/**/*.test.js'],
  },
});
