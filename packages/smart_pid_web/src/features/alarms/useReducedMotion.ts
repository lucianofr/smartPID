import { useSyncExternalStore } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';

function subscribe(onChange: () => void): () => void {
  if (typeof window === 'undefined' || !window.matchMedia) return () => {};
  const mql = window.matchMedia(QUERY);
  mql.addEventListener('change', onChange);
  return () => mql.removeEventListener('change', onChange);
}

function getSnapshot(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia(QUERY).matches;
}

/**
 * Tracks `prefers-reduced-motion: reduce`. When true, the alarm UI swaps its
 * blink animation for motion-free encodings (weight/underline/filled icon in CSS,
 * plus a persistent unacked count badge + assertive live region in the DOM) so the
 * new-vs-seen distinction survives without motion (a11y review, §4).
 */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, () => false);
}
