import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { App } from './App';

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
});

describe('App shell (phase-2 foundation)', () => {
  it('mounts ThemeProvider (data-theme applied) and shows the wordmark', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: 'SMART PID' })).toBeInTheDocument();
    expect(document.documentElement.getAttribute('data-theme')).toBe('recorder');
  });
});