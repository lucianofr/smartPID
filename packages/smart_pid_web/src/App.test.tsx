import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';

/**
 * Composition-root smoke: the providers mount, the theme is applied, and an
 * anonymous session lands on /login instead of the guarded dashboard.
 */

class SilentWebSocket {
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  send(): void {}
  close(): void {}
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  document.documentElement.removeAttribute('data-theme');
  window.history.pushState({}, '', '/');
  vi.stubGlobal('WebSocket', SilentWebSocket);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('App composition root', () => {
  it('applies the default theme and guards the dashboard behind /login', async () => {
    render(<App />);
    expect(document.documentElement.getAttribute('data-theme')).toBe('neon');
    await waitFor(() => expect(window.location.pathname).toBe('/login'));
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeVisible();
  });
});
