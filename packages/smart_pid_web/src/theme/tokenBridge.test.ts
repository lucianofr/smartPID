import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// Vitest runs from the package root (`npm run test` in packages/smart_pid_web).
const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

describe('Tailwind v4 token bridge (src/index.css)', () => {
  it('imports tailwindcss and the token-contract stylesheets', () => {
    expect(css).toMatch(/@import\s+['"]tailwindcss['"]/);
    expect(css).toMatch(/@import\s+['"]\.\/theme\/tokens\.css['"]/);
    expect(css).toMatch(/@import\s+['"]\.\/theme\/themes\.css['"]/);
  });

  it('declares an @theme inline block (plain @theme would freeze values at build time)', () => {
    expect(css).toMatch(/@theme\s+inline\s*\{/);
    const plainTheme = /@theme\s*\{[^}]*--(?:color|radius|font)-[^}]*\}/;
    expect(css).not.toMatch(plainTheme);
  });

  it('maps every §6.4 color token onto the contract variable', () => {
    for (const name of [
      'bg', 'surface', 'surface-sunk', 'rule', 'rule-strong', 'text', 'text-soft',
      'text-disabled', 'focus-ring', 'selection', 'scrim', 'accent', 'accent-hover',
      'accent-sunk', 'accent-soft', 'on-accent', 'alarm-crit', 'alarm-crit-bg',
      'alarm-warn', 'alarm-warn-bg', 'alarm-adv', 'alarm-adv-bg', 'alarm-log',
      'on-alarm', 'state-running', 'state-stopped', 'state-error', 'state-oos',
      'trace-pv', 'trace-sp', 'trace-co', 'trend-grid', 'trend-axis', 'trend-bg',
      'bar-track', 'bar-fill', 'bar-marker',
    ]) {
      expect(css, name).toMatch(new RegExp(`--color-${name}:\\s*var\\(--${name}\\)`));
    }
  });

  it('bridges fonts, sizes and radii', () => {
    expect(css).toMatch(/--font-display:\s*var\(--font-display\)/);
    expect(css).toMatch(/--font-data:\s*var\(--font-data\)/);
    expect(css).toMatch(/--text-2xs:\s*var\(--text-2xs\)/);
    expect(css).toMatch(/--radius-pill:\s*var\(--radius-pill\)/);
  });

  it('carries the §11 reduced-motion kill-switch and the two type classes', () => {
    expect(css).toMatch(/prefers-reduced-motion:\s*reduce/);
    expect(css).toMatch(/\.type-display\s*\{/);
    expect(css).toMatch(/\.numeric\s*\{/);
    expect(css).toMatch(/font-feature-settings:\s*'zero'\s*1/);
  });
});