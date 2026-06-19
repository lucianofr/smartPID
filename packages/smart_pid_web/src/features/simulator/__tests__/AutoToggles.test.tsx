import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AutoToggles } from '../AutoToggles';

describe('AutoToggles', () => {
  it('enables auto-SP with default bounds when toggled on', () => {
    const onSetAutoSp = vi.fn();
    render(<AutoToggles autoSp={null} autoDisturbance={null}
      onSetAutoSp={onSetAutoSp} onSetAutoDisturbance={() => {}} />);
    fireEvent.click(screen.getByRole('switch', { name: /auto.?sp/i }));
    expect(onSetAutoSp).toHaveBeenCalledWith({ enabled: true, sp_min_pct: 30, sp_max_pct: 70 });
  });
  it('enables auto-disturbance with default amplitude when toggled on', () => {
    const onSetAutoDisturbance = vi.fn();
    render(<AutoToggles autoSp={null} autoDisturbance={null}
      onSetAutoSp={() => {}} onSetAutoDisturbance={onSetAutoDisturbance} />);
    fireEvent.click(screen.getByRole('switch', { name: /auto.?disturbance/i }));
    expect(onSetAutoDisturbance).toHaveBeenCalledWith({ enabled: true, max_amplitude_pct: 10 });
  });
  it('reflects an already-enabled auto-SP as checked', () => {
    render(<AutoToggles autoSp={{ enabled: true, sp_min_pct: 20, sp_max_pct: 80 }} autoDisturbance={null}
      onSetAutoSp={() => {}} onSetAutoDisturbance={() => {}} />);
    expect(screen.getByRole('switch', { name: /auto.?sp/i })).toBeChecked();
  });
});
