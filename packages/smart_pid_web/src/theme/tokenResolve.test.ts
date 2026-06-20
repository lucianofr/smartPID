import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { type ThemeId } from './themeContrast';

// Proves the `@theme inline` bridge (Task 0.2) re-resolves at runtime: Tailwind utilities like
// `bg-surface` map to `var(--surface)`, so once `--surface`/`--bg` re-resolve on a `data-theme`
// flip every utility tracks the new theme. We assert the underlying contract tokens re-resolve.
//
// jsdom does not apply imported .css files, so we inject themes.css into a <style> element — jsdom
// then resolves `[data-theme]` custom properties through getComputedStyle exactly as a browser does.

const THEMES: ThemeId[] = ['isa101', 'dark-room', 'md3-dark', 'md3-light', 'ocean'];
const BRIDGED_TOKENS = ['--bg', '--surface', '--surface-container-high', '--text'] as const;

const themesCssPath = resolve(process.cwd(), 'src/theme/themes.css');
let styleEl: HTMLStyleElement;

function resolved(token: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim();
}

beforeAll(() => {
  styleEl = document.createElement('style');
  styleEl.textContent = readFileSync(themesCssPath, 'utf8');
  document.head.appendChild(styleEl);
});

afterAll(() => {
  styleEl.remove();
  document.documentElement.removeAttribute('data-theme');
});

describe('@theme inline bridge re-resolves contract tokens on data-theme flip', () => {
  it.each(THEMES)('%s: every bridged token resolves to a non-empty value', (id) => {
    document.documentElement.setAttribute('data-theme', id);
    for (const token of BRIDGED_TOKENS) {
      expect(resolved(token), `${id} ${token}`).not.toBe('');
    }
  });

  it('--bg re-resolves to a DIFFERENT value when [data-theme] flips (runtime swap, not static)', () => {
    document.documentElement.setAttribute('data-theme', 'isa101');
    const isa = resolved('--bg');
    document.documentElement.setAttribute('data-theme', 'md3-light');
    const md3Light = resolved('--bg');
    expect(isa).not.toBe('');
    expect(md3Light).not.toBe('');
    expect(md3Light).not.toBe(isa);
  });

  it('--surface (the bg-surface utility target) differs across at least two themes', () => {
    const values = new Set<string>();
    for (const id of THEMES) {
      document.documentElement.setAttribute('data-theme', id);
      values.add(resolved('--surface'));
    }
    // All five surfaces are distinct in the committed palette; require at least two to prove the swap.
    expect(values.size).toBeGreaterThanOrEqual(2);
  });
});
