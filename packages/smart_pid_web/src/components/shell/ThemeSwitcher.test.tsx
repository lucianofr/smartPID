import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { ThemeProvider } from '../../theme/ThemeProvider';
import { ThemeSwitcher } from './ThemeSwitcher';

describe('ThemeSwitcher', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('lists all 5 themes and switches on select', () => {
    render(
      <ThemeProvider>
        <ThemeSwitcher />
      </ThemeProvider>,
    );
    const select = screen.getByLabelText('Theme') as HTMLSelectElement;
    expect(select.options).toHaveLength(5);
    fireEvent.change(select, { target: { value: 'dark-room' } });
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark-room');
    expect(localStorage.getItem('spid.theme')).toBe('dark-room');
  });
});
