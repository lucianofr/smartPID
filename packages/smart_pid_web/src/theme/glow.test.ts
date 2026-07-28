import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// Vitest runs from the package root (`npm run test` in packages/smart_pid_web).
const css = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf8');

describe('§10.5 glow is the salience channel, not decoration', () => {
  it('blooms the focus ring through the Tailwind ring composition variable', () => {
    expect(css).toMatch(/:focus-visible\s*\{\s*--tw-shadow:\s*var\(--glow-focus\);\s*\}/);
  });

  it('blooms unacked alarm rows without dropping the 3 px severity stripe', () => {
    expect(css).toMatch(
      /\.alarm-row\.is-unacked\s*\{\s*box-shadow:\s*inset 3px 0 0 0 currentColor,\s*var\(--glow-alarm\);\s*\}/,
    );
  });

  it('blooms severity badges and primary-button hover/active', () => {
    expect(css).toMatch(/\.badge-glow\s*\{\s*box-shadow:\s*var\(--glow-alarm\);\s*\}/);
    expect(css).toMatch(
      /\.btn-primary:hover,\s*\.btn-primary:active\s*\{\s*box-shadow:\s*var\(--glow-accent\);\s*\}/,
    );
  });

  it('reaches exactly four rules — no state dot, card border, header or body text blooms', () => {
    const uses = css.match(/var\(--glow-(?:alarm|focus|accent)\)/g) ?? [];
    expect(uses).toHaveLength(4);
  });

  it('adds no motion: the bloom is static and the only pulse stays reduced-motion safe', () => {
    expect(css).not.toMatch(/@keyframes\s+[a-z-]*glow/);
    const componentsRm = css.slice(
      css.indexOf('@media (prefers-reduced-motion: reduce)', css.indexOf('@layer components')),
    );
    expect(componentsRm).toMatch(/\.alarm-blink \.sev-icon\s*\{\s*animation:\s*none;/);
  });
});
