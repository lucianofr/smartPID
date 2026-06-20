import { render, screen } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { ThemeProvider, useTheme, THEMES } from './ThemeProvider';

function Probe() {
  const { theme, setTheme, themes } = useTheme();
  return (
    <div>
      <span data-testid="current">{theme}</span>
      <span data-testid="count">{themes.length}</span>
      <button onClick={() => setTheme('ocean')}>ocean</button>
    </div>
  );
}

describe('ThemeProvider registry', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('exposes all 5 themes', () => {
    const ids = THEMES.map((t) => t.id);
    expect(ids).toEqual(
      expect.arrayContaining(['isa101', 'dark-room', 'md3-dark', 'md3-light', 'ocean']),
    );
    expect(ids).toHaveLength(5);
  });

  it('defaults to isa101 and sets data-theme on the html element', () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('current').textContent).toBe('isa101');
    expect(document.documentElement.getAttribute('data-theme')).toBe('isa101');
  });
});
