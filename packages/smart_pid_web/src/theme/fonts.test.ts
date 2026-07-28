import { readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = process.cwd();
const fontsDir = resolve(root, 'src/assets/fonts');
const FILES = [
  'archivo-latin-var.woff2',
  'geist-mono-latin-400.woff2',
  'geist-mono-latin-500.woff2',
  'orbitron-latin-var.woff2',
];
const FONT_BUDGET_BYTES = 160 * 1024; // §6.2: combined font transfer ≤ 160 KB

describe('§6.2 self-hosted fonts', () => {
  it('ships the four committed woff2 files within the 160 KB combined budget', () => {
    let total = 0;
    for (const f of FILES) {
      const size = statSync(resolve(fontsDir, f)).size;
      expect(size, f).toBeGreaterThan(0);
      total += size;
    }
    expect(total, `combined ${Math.round(total / 1024)} KB`).toBeLessThanOrEqual(FONT_BUDGET_BYTES);
  });

  it('commits the SIL OFL 1.1 licence beside the Orbitron file (§10.6, legal requirement)', () => {
    const licence = readFileSync(resolve(fontsDir, 'OFL-Orbitron.txt'), 'utf8');
    expect(licence).toContain('SIL OPEN FONT LICENSE Version 1.1');
    expect(licence).toContain('Orbitron');
  });

  it('fonts.css declares swap-display faces matching the token stacks', () => {
    const css = readFileSync(resolve(fontsDir, 'fonts.css'), 'utf8');
    expect(css).toMatch(/font-family:\s*'Archivo Variable'/);
    expect(css).toMatch(/font-stretch:\s*62\.5%\s+125%/);
    expect(css).toMatch(/font-weight:\s*100\s+900/);
    expect((css.match(/font-family:\s*'Geist Mono'/g) ?? []).length).toBe(2);
    // §10.6 display face for neon. wght only — Orbitron has no width axis.
    expect(css).toMatch(/font-family:\s*'Orbitron Variable'/);
    expect(css).toMatch(/font-weight:\s*400\s+900/);
    expect((css.match(/font-display:\s*swap/g) ?? []).length).toBe(4);
  });

  it('index.css imports fonts.css and index.html preloads all four files', () => {
    const indexCss = readFileSync(resolve(root, 'src/index.css'), 'utf8');
    expect(indexCss).toMatch(/@import\s+['"]\.\/assets\/fonts\/fonts\.css['"]/);
    const html = readFileSync(resolve(root, 'index.html'), 'utf8');
    for (const f of FILES) {
      expect(html, f).toContain(`/src/assets/fonts/${f}`);
    }
    expect((html.match(/rel="preload"\s+href="\/src\/assets\/fonts\//g) ?? []).length).toBe(4);
    expect(html).toMatch(/as="font"\s+type="font\/woff2"\s+crossorigin/);
  });
});