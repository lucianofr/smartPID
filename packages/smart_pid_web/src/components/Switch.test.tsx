import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Switch } from './Switch';

describe('Switch', () => {
  it('toggles aria-checked on click', () => {
    render(<Switch aria-label="Otimização contínua" />);
    const sw = screen.getByRole('switch', { name: 'Otimização contínua' });
    expect(sw).toHaveAttribute('aria-checked', 'false');
    fireEvent.click(sw);
    expect(sw).toHaveAttribute('aria-checked', 'true');
  });

  it('carries the pseudo hit-area extension and accent checked state', () => {
    render(<Switch aria-label="x" />);
    const sw = screen.getByRole('switch');
    expect(sw.className).toContain('after:absolute');
    expect(sw.className).toContain('data-[state=checked]:bg-accent');
  });

  it('disabled blocks toggling', () => {
    render(<Switch aria-label="x" disabled />);
    const sw = screen.getByRole('switch');
    fireEvent.click(sw);
    expect(sw).toHaveAttribute('aria-checked', 'false');
  });
});