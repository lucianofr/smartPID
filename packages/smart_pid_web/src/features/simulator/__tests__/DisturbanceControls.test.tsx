import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { DisturbanceControls } from '../DisturbanceControls';

describe('DisturbanceControls', () => {
  it('injects a step disturbance with the entered amplitude', () => {
    const onInject = vi.fn();
    render(<DisturbanceControls active={false} onInject={onInject} onRemove={() => {}} />);
    fireEvent.change(screen.getByRole('spinbutton', { name: /amplitude/i }), { target: { value: '15' } });
    fireEvent.click(screen.getByRole('button', { name: /inject/i }));
    expect(onInject).toHaveBeenCalledWith('step', 15);
  });
  it('disables Remove when no disturbance is active', () => {
    render(<DisturbanceControls active={false} onInject={() => {}} onRemove={() => {}} />);
    expect(screen.getByRole('button', { name: /remove/i })).toBeDisabled();
  });
  it('calls onRemove when active and Remove clicked', () => {
    const onRemove = vi.fn();
    render(<DisturbanceControls active onInject={() => {}} onRemove={onRemove} />);
    fireEvent.click(screen.getByRole('button', { name: /remove/i }));
    expect(onRemove).toHaveBeenCalled();
  });
});
