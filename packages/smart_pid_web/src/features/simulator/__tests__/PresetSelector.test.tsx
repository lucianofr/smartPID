import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { PresetSelector } from '../PresetSelector';

describe('PresetSelector', () => {
  it('renders all five preset options and reflects value', () => {
    render(<PresetSelector value="FLOW" onChange={() => {}} />);
    const select = screen.getByRole('combobox', { name: /process preset/i }) as HTMLSelectElement;
    ['FLOW', 'PRESSURE', 'LEVEL', 'TEMPERATURE', 'CUSTOM'].forEach((p) =>
      expect(screen.getByRole('option', { name: p })).toBeInTheDocument());
    expect(select.value).toBe('FLOW');
  });
  it('calls onChange with the selected preset', () => {
    const onChange = vi.fn();
    render(<PresetSelector value="FLOW" onChange={onChange} />);
    fireEvent.change(screen.getByRole('combobox', { name: /process preset/i }), { target: { value: 'LEVEL' } });
    expect(onChange).toHaveBeenCalledWith('LEVEL');
  });
});
