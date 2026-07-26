import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { CONTRACT_TOKENS, THEME_IDS } from './contract';

const CSS_FILES = ['src/theme/tokens.css', 'src/theme/themes.css'];
let styleEl: HTMLStyleElement;

function resolved(token: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim();
}

beforeAll(() => {
  styleEl = document.createElement('style');
  styleEl.textContent = CSS_FILES.map((p) => readFileSync(resolve(process.cwd(), p), 'utf8')).join('\n');
  document.head.appendChild(styleEl);
});

afterAll(() => {
  styleEl.remove();
  document.documentElement.removeAttribute('data-theme');
});

describe('§6.4 token contract resolves under every [data-theme]', () => {
  it.each(THEME_IDS)('%s: every contract token resolves non-empty', (id) => {
    document.documentElement.setAttribute('data-theme', id);
    for (const token of CONTRACT_TOKENS) {
      expect(resolved(token), `${id} ${token}`).not.toBe('');
    }
  });

  it('--bg re-resolves on a data-theme flip (runtime swap, not a static snapshot)', () => {
    document.documentElement.setAttribute('data-theme', 'recorder');
    expect(resolved('--bg')).toBe('#F7F8FA');
    document.documentElement.setAttribute('data-theme', 'phosphor');
    expect(resolved('--bg')).toBe('#0A0E14');
  });

  it('trend widths carry px units consumable by parseFloat (uplotTheme contract)', () => {
    document.documentElement.setAttribute('data-theme', 'recorder');
    expect(resolved('--trend-pv-width')).toBe('2px');
    expect(Number.parseFloat(resolved('--trend-sp-width'))).toBe(1.5);
  });
});