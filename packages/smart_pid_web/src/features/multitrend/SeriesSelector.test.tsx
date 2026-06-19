import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SeriesSelector } from './SeriesSelector';

describe('SeriesSelector', () => {
  it('renders a checkbox per loop×variable and toggles selection', () => {
    const onChange = vi.fn();
    render(<SeriesSelector loops={[1, 2]} selected={[]} onChange={onChange} />);
    // 2 loops × 3 variables = 6 checkboxes
    expect(screen.getAllByRole('checkbox')).toHaveLength(6);
    fireEvent.click(screen.getByLabelText('Loop 1 · PV'));
    expect(onChange).toHaveBeenCalledWith([{ loopId: 1, variable: 'pv' }]);
  });
});
