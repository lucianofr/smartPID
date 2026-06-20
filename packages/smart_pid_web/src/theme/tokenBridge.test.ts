import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// Vitest runs from the package root (`npm run test` in packages/smart_pid_web).
const indexCssPath = resolve(process.cwd(), 'src/index.css');

function readIndexCss(): string {
  return readFileSync(indexCssPath, 'utf8');
}

describe('Tailwind v4 token bridge (src/index.css)', () => {
  const css = readIndexCss();

  it('imports tailwindcss', () => {
    expect(css).toMatch(/@import\s+["']tailwindcss["']/);
  });

  it('imports the existing token-contract stylesheets', () => {
    expect(css).toMatch(/@import\s+["']\.\/theme\/tokens\.css["']/);
    expect(css).toMatch(/@import\s+["']\.\/theme\/themes\.css["']/);
  });

  it('declares an @theme inline block', () => {
    expect(css).toMatch(/@theme\s+inline\s*\{/);
  });

  it('does not use a plain (non-inline) @theme block for color/radius/font tokens', () => {
    // A plain `@theme {` (no `inline`) defining contract tokens would break runtime
    // re-resolution on data-theme flips. Only `@theme inline {` is permitted here.
    const plainTheme = /@theme\s*\{[^}]*--(?:color|radius|font)-[^}]*\}/;
    expect(css).not.toMatch(plainTheme);
  });

  it('maps required color tokens onto the existing contract variables', () => {
    expect(css).toMatch(/--color-bg:\s*var\(--bg\)/);
    expect(css).toMatch(/--color-surface:\s*var\(--surface\)/);
    expect(css).toMatch(/--color-text:\s*var\(--text\)/);
    expect(css).toMatch(/--color-alarm-critical:\s*var\(--alarm-critical\)/);
  });

  it('maps required radius and font tokens onto the existing contract variables', () => {
    expect(css).toMatch(/--radius-card:\s*var\(--radius-card\)/);
    expect(css).toMatch(/--font-ui:\s*var\(--font-ui\)/);
  });
});
