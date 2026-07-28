import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { useGlowTrace } from './useGlowTrace';

/**
 * jsdom resolves custom properties from a real stylesheet (the same technique
 * tokenResolve.test.ts uses), so this drives the hook exactly the way the
 * browser does: flip <html data-theme> and let the cascade answer.
 */
const TOKENS = `
  [data-theme="recorder"] { --glow-trace: 0px; }
  [data-theme="phosphor"] { --glow-trace: 4px; }
  [data-theme="isa101"]   { --glow-trace: 0px; }
  [data-theme="neon"]     { --glow-trace: 8px; }
`;

let styleEl: HTMLStyleElement | null = null;

function withTokens(): void {
  styleEl = document.createElement('style');
  styleEl.textContent = TOKENS;
  document.head.appendChild(styleEl);
}

async function setTheme(id: string): Promise<void> {
  await act(async () => {
    document.documentElement.setAttribute('data-theme', id);
    // MutationObserver callbacks land on a microtask.
    await Promise.resolve();
  });
}

afterEach(() => {
  styleEl?.remove();
  styleEl = null;
  document.documentElement.removeAttribute('data-theme');
});

describe('useGlowTrace (§10.5 — glow is "the token is non-zero")', () => {
  it('is on wherever --glow-trace is non-zero and off where it is 0px', async () => {
    withTokens();
    document.documentElement.setAttribute('data-theme', 'recorder');
    const { result } = renderHook(() => useGlowTrace());
    expect(result.current).toBe(false);

    await setTheme('phosphor');
    expect(result.current).toBe(true);

    await setTheme('neon');
    expect(result.current).toBe(true);

    await setTheme('isa101');
    expect(result.current).toBe(false);
  });

  it('picks the token up when the attribute arrives after mount', async () => {
    withTokens();
    const { result } = renderHook(() => useGlowTrace());
    expect(result.current).toBe(false);

    await setTheme('neon');
    expect(result.current).toBe(true);
  });
});
