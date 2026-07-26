import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MultiTrendChart } from './MultiTrendChart';
import type { TimeSync } from './timeSync';

const SERIES = {
  keys: [
    { loopId: 1, signal: 'pv' as const },
    { loopId: 1, signal: 'co' as const },
  ],
  data: [
    [1, 2],
    [10, 11],
    [40, 41],
  ],
};

describe('MultiTrendChart', () => {
  it('renders an addressable, labelled chart host', () => {
    render(
      <MultiTrendChart id="slot-0" series={SERIES} ariaLabel="Tendência Loop 1" testId="slot-0" />,
    );
    expect(screen.getByTestId('slot-0')).toBeVisible();
    expect(screen.getByRole('region', { name: 'Tendência Loop 1' })).toBeInTheDocument();
  });

  it('joins the shared time sync and leaves it on unmount', () => {
    const off = vi.fn();
    const sync: TimeSync = { register: vi.fn(() => off), publish: vi.fn() };
    const { unmount } = render(
      <MultiTrendChart id="slot-2" series={SERIES} ariaLabel="Tendência Loop 1" sync={sync} />,
    );
    expect(sync.register).toHaveBeenCalledWith(expect.objectContaining({ id: 'slot-2' }));
    unmount();
    expect(off).toHaveBeenCalled();
  });
});
