import { readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = process.cwd();
const fontsDir = resolve(root, 'src/assets/fonts');

/**
 * The smartPID Optimizer type system: Poppins (display), Inter (UI), IBM Plex
 * Mono (data). Orbitron survives as the neon display face only (§10.6).
 * Archivo and Geist Mono were retired with the pre-rewrite type system.
 */
const FILES = [
  'poppins-latin-600.woff2',
  'poppins-latin-700.woff2',
  'inter-latin-var.woff2',
  'plex-mono-latin-400.woff2',
  'plex-mono-latin-600.woff2',
  'plex-mono-latin-700.woff2',
  'orbitron-latin-var.woff2',
];

/** Only the faces above the fold are preloaded; the rest arrive with `swap`. */
const PRELOADED = [
  'inter-latin-var.woff2',
  'plex-mono-latin-400.woff2',
  'plex-mono-latin-600.woff2',
  'poppins-latin-700.woff2',
];

const FONT_BUDGET_BYTES = 160 * 1024; // §6.2: combined font transfer ≤ 160 KB

describe('§6.2 self-hosted fonts', () => {
  it('ships the seven committed woff2 files within the 160 KB combined budget', () => {
    let total = 0;
    for (const f of FILES) {
      const size = statSync(resolve(fontsDir, f)).size;
      expect(size, f).toBeGreaterThan(0);
      total += size;
    }
    expect(total, `combined ${Math.round(total / 1024)} KB`).toBeLessThanOrEqual(FONT_BUDGET_BYTES);
  });

  it('commits the SIL OFL 1.1 licence beside every redistributed family (legal requirement)', () => {
    const licences: ReadonlyArray<readonly [string, string]> = [
      ['OFL-Orbitron.txt', 'Orbitron'],
      ['OFL-Inter.txt', 'Inter'],
      ['OFL-Poppins.txt', 'Poppins'],
      ['OFL-IBMPlexMono.txt', 'Plex'], // the OFL Reserved Font Name is "Plex"
    ];
    for (const [file, family] of licences) {
      const licence = readFileSync(resolve(fontsDir, file), 'utf8');
      expect(licence, file).toContain('SIL OPEN FONT LICENSE Version 1.1');
      expect(licence, file).toContain(family);
    }
  });

  it('fonts.css declares swap-display faces matching the token stacks', () => {
    const css = readFileSync(resolve(fontsDir, 'fonts.css'), 'utf8');
    // Poppins: the two display weights the brand layer uses (600 / 700).
    expect((css.match(/font-family:\s*'Poppins'/g) ?? []).length).toBe(2);
    // Inter: one variable file spanning the UI weights.
    expect(css).toMatch(/font-family:\s*'Inter Variable'/);
    expect(css).toMatch(/font-weight:\s*400\s+700/);
    // IBM Plex Mono: 400 log / 600 value / 700 tag.
    expect((css.match(/font-family:\s*'IBM Plex Mono'/g) ?? []).length).toBe(3);
    // §10.6 display face for neon. wght only — Orbitron has no width axis.
    expect(css).toMatch(/font-family:\s*'Orbitron Variable'/);
    expect(css).toMatch(/font-weight:\s*400\s+900/);
    expect((css.match(/font-display:\s*swap/g) ?? []).length).toBe(FILES.length);
  });

  it('index.css imports fonts.css and index.html preloads the four critical files', () => {
    const indexCss = readFileSync(resolve(root, 'src/index.css'), 'utf8');
    expect(indexCss).toMatch(/@import\s+['"]\.\/assets\/fonts\/fonts\.css['"]/);
    const html = readFileSync(resolve(root, 'index.html'), 'utf8');
    for (const f of PRELOADED) {
      expect(html, f).toContain(`/src/assets/fonts/${f}`);
    }
    expect((html.match(/rel="preload"\s+href="\/src\/assets\/fonts\//g) ?? []).length).toBe(
      PRELOADED.length,
    );
    expect(html).toMatch(/as="font"\s+type="font\/woff2"\s+crossorigin/);
  });

  it('the retired Archivo and Geist Mono files are referenced by nothing', () => {
    // The prose in fonts.css still NAMES them (it records what they replaced);
    // what must be gone is every reference that would 404 at runtime.
    const html = readFileSync(resolve(root, 'index.html'), 'utf8');
    const css = readFileSync(resolve(fontsDir, 'fonts.css'), 'utf8');
    for (const gone of ['archivo-latin-var.woff2', 'geist-mono-latin']) {
      expect(html, gone).not.toContain(gone);
      expect(css, gone).not.toContain(gone);
    }
  });
});
