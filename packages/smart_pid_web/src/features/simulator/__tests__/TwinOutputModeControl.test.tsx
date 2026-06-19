import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TwinOutputModeControl } from '../TwinOutputModeControl';

describe('TwinOutputModeControl', () => {
  it('sets twin CO within 0-100 on apply', () => {
    const onSetCo = vi.fn();
    render(<TwinOutputModeControl co={0} mode="MAN" onSetCo={onSetCo} onSetMode={() => {}} />);
    fireEvent.change(screen.getByRole('spinbutton', { name: /output co/i }), { target: { value: '42' } });
    fireEvent.click(screen.getByRole('button', { name: /apply output/i }));
    expect(onSetCo).toHaveBeenCalledWith(42);
  });
  it('toggles twin mode to AUTO', () => {
    const onSetMode = vi.fn();
    render(<TwinOutputModeControl co={0} mode="MAN" onSetCo={() => {}} onSetMode={onSetMode} />);
    fireEvent.click(screen.getByRole('button', { name: /auto/i }));
    expect(onSetMode).toHaveBeenCalledWith('AUTO');
  });
  it('disables CO apply when in AUTO (CO is computed by the twin PID)', () => {
    render(<TwinOutputModeControl co={0} mode="AUTO" onSetCo={() => {}} onSetMode={() => {}} />);
    expect(screen.getByRole('button', { name: /apply output/i })).toBeDisabled();
  });
});
