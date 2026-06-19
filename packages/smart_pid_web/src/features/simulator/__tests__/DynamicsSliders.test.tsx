import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { DynamicsSliders } from '../DynamicsSliders';

const base = { gain: 1.2, dead_time: 1.0, tau1: 3.0, tau2: null };

describe('DynamicsSliders', () => {
  it('renders gain, dead time, tau1, tau2 sliders with mono readouts', () => {
    render(<DynamicsSliders value={base} onCommit={() => {}} />);
    expect(screen.getByRole('slider', { name: /gain/i })).toHaveValue('1.2');
    expect(screen.getByRole('slider', { name: /dead time/i })).toHaveValue('1');
    expect(screen.getByRole('slider', { name: /tau1/i })).toHaveValue('3');
    expect(screen.getByTestId('readout-gain')).toHaveTextContent('1.20');
  });
  it('commits the full dynamics object when gain changes', () => {
    const onCommit = vi.fn();
    render(<DynamicsSliders value={base} onCommit={onCommit} />);
    fireEvent.change(screen.getByRole('slider', { name: /gain/i }), { target: { value: '2.0' } });
    expect(onCommit).toHaveBeenCalledWith({ gain: 2.0, dead_time: 1.0, tau1: 3.0, tau2: null });
  });
});
