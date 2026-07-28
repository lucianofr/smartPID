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

  it('the contract holds 60 tokens — 48 palette + 3 type + 4 glow + 2 shadow + the brand layer', () => {
    expect(CONTRACT_TOKENS).toHaveLength(60);
    for (const token of ['--glow-alarm', '--glow-focus', '--glow-accent', '--glow-trace']) {
      expect(CONTRACT_TOKENS, token).toContain(token);
    }
    // The design-system additions: the brand layer, the AI strategy chip, the
    // comms dot and the two elevation steps the Optimizer cards rest on.
    for (const token of [
      '--brand-ink', '--brand-ink-deep', '--brand-accent', '--brand-accent-hover',
      '--brand-accent-soft', '--on-brand-accent', '--kpi-band',
      '--state-ai', '--state-ai-soft', '--live',
      '--shadow-card', '--shadow-lifted',
    ]) {
      expect(CONTRACT_TOKENS, token).toContain(token);
    }
  });

  it('--glow-trace carries px so parseFloat reads it (the halo is "token non-zero")', () => {
    document.documentElement.setAttribute('data-theme', 'phosphor');
    expect(resolved('--glow-trace')).toBe('4px');
    expect(Number.parseFloat(resolved('--glow-trace'))).toBe(4);
    document.documentElement.setAttribute('data-theme', 'recorder');
    expect(Number.parseFloat(resolved('--glow-trace'))).toBe(0);
    document.documentElement.setAttribute('data-theme', 'isa101');
    expect(Number.parseFloat(resolved('--glow-trace'))).toBe(0);
  });

  it('the bloom tokens are valid <shadow> values, never the uncomposable `none`', () => {
    for (const id of ['recorder', 'phosphor', 'isa101']) {
      document.documentElement.setAttribute('data-theme', id);
      for (const token of ['--glow-alarm', '--glow-focus', '--glow-accent']) {
        expect(resolved(token), `${id} ${token}`).toBe('0 0 #0000');
      }
    }
  });

  it('--font-display is per-theme while --font-ui and --font-data stay global', () => {
    const tokensCss = readFileSync(resolve(process.cwd(), 'src/theme/tokens.css'), 'utf8');
    expect(tokensCss).not.toMatch(/--font-display\s*:/);
    expect(tokensCss).toMatch(/--font-ui\s*:/);
    expect(tokensCss).toMatch(/--font-data\s*:/);

    // Five of the six themes share the Poppins display face; neon keeps Orbitron
    // (§10.6) because its identity is carried by its lettering, not its chrome.
    const poppins = "'Poppins', system-ui, -apple-system, 'Segoe UI', sans-serif";
    for (const id of ['optimizer', 'optimizer-dark', 'recorder', 'phosphor', 'isa101']) {
      document.documentElement.setAttribute('data-theme', id);
      expect(resolved('--font-display'), id).toBe(poppins);
    }
    document.documentElement.setAttribute('data-theme', 'neon');
    expect(resolved('--font-display')).toMatch(/^'Orbitron Variable'/);
  });
});