import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from './Command';

function Harness() {
  return (
    <Command label="Paleta de comandos">
      <CommandInput />
      <CommandList>
        <CommandEmpty />
        <CommandItem onSelect={() => {}}>Ir para alarmes</CommandItem>
        <CommandItem onSelect={() => {}}>Trocar tema</CommandItem>
      </CommandList>
    </Command>
  );
}

describe('Command palette', () => {
  it('renders the pt-BR input placeholder and all items', () => {
    render(<Harness />);
    expect(screen.getByPlaceholderText('Buscar comando…')).toBeInTheDocument();
    expect(screen.getAllByRole('option')).toHaveLength(2);
  });

  it('filters items as the user types', () => {
    render(<Harness />);
    fireEvent.change(screen.getByPlaceholderText('Buscar comando…'), { target: { value: 'tema' } });
    expect(screen.getByText('Trocar tema')).toBeInTheDocument();
    expect(screen.queryByText('Ir para alarmes')).not.toBeInTheDocument();
  });

  it('shows the pt-BR empty state when nothing matches', () => {
    render(<Harness />);
    fireEvent.change(screen.getByPlaceholderText('Buscar comando…'), { target: { value: 'zzz' } });
    expect(screen.getByText('Nenhum resultado.')).toBeInTheDocument();
  });

  it('Enter selects the highlighted item', () => {
    const onSelect = vi.fn();
    render(
      <Command label="p">
        <CommandInput />
        <CommandList>
          <CommandItem onSelect={onSelect}>Única ação</CommandItem>
        </CommandList>
      </Command>,
    );
    const input = screen.getByRole('combobox');
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledTimes(1);
  });
});