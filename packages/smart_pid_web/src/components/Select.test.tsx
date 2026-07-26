import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './Select';

describe('Select', () => {
  it('renders trigger with accessible name and sunk styling', () => {
    render(
      <Select defaultValue="pid">
        <SelectTrigger aria-label="Tipo de controlador">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="pid">PID</SelectItem>
        </SelectContent>
      </Select>,
    );
    const trigger = screen.getByRole('combobox', { name: 'Tipo de controlador' });
    expect(trigger.className).toContain('bg-surface-sunk');
    expect(trigger.className).toContain('min-h-11');
  });

  it('defaultOpen renders the listbox with options and selection highlight class', () => {
    render(
      <Select defaultOpen defaultValue="pid">
        <SelectTrigger aria-label="Tipo">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="pid">PID</SelectItem>
          <SelectItem value="fuzzy">Fuzzy</SelectItem>
        </SelectContent>
      </Select>,
    );
    expect(screen.getByRole('listbox')).toBeInTheDocument();
    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(2);
    expect(options[0].className).toContain('data-[highlighted]:bg-selection');
  });
});