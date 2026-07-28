import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './DropdownMenu';

describe('DropdownMenu', () => {
  it('defaultOpen renders the menu with items, label and separator', () => {
    render(
      <DropdownMenu defaultOpen>
        <DropdownMenuTrigger asChild>
          <button type="button">Configurações</button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuLabel>Projeto</DropdownMenuLabel>
          <DropdownMenuItem>Abrir projeto</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem destructive>Excluir projeto</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(screen.getAllByRole('menuitem')).toHaveLength(2);
    expect(screen.getByText('Projeto')).toBeInTheDocument();
  });

  it('destructive items carry the sanctioned crit token, min-h-11, selection highlight', () => {
    render(
      <DropdownMenu defaultOpen>
        <DropdownMenuTrigger asChild>
          <button type="button">m</button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem destructive>Excluir</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );
    const item = screen.getByRole('menuitem', { name: 'Excluir' });
    expect(item.className).toContain('text-alarm-crit');
    expect(item.className).toContain('min-h-11');
    expect(item.className).toContain('data-[highlighted]:bg-selection');
  });
});