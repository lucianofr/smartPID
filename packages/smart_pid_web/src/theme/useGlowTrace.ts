import { useEffect, useState } from 'react';

/**
 * §10.5 / D12 — the PV halo is "the `--glow-trace` token is non-zero", not
 * "the theme is Phosphor". One mechanism serves the existing CRT halo (4px)
 * and the neon one (8px), and no component needs to know a theme id.
 *
 * The token carries `px` so `parseFloat` reads it, matching the
 * `--trend-*-width` convention that `tokenResolve.test.ts` already asserts.
 *
 * The observer mirrors the one in `components/Trend.tsx`: `data-theme` is set
 * by `index.html` before first paint in the browser, but by a ThemeProvider
 * effect in jsdom — which runs AFTER this component's effect — so reading once
 * on mount is not enough.
 */
function readGlowTrace(): boolean {
  const raw = getComputedStyle(document.documentElement).getPropertyValue('--glow-trace');
  return Number.parseFloat(raw) > 0;
}

export function useGlowTrace(): boolean {
  const [on, setOn] = useState(readGlowTrace);

  useEffect(() => {
    const read = () => setOn(readGlowTrace());
    read();
    const obs = new MutationObserver(read);
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => obs.disconnect();
  }, []);

  return on;
}
