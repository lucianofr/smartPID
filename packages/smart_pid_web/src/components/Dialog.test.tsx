import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from './Dialog';

function Harness() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <button type="button">Abrir</button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Excluir projeto</DialogTitle>
        <DialogDescription>Esta ação não pode ser desfeita.</DialogDescription>
      </DialogContent>
    </Dialog>
  );
}

describe('Dialog', () => {
  it('opens from the trigger with role=dialog and its accessible name', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Abrir' }));
    expect(screen.getByRole('dialog', { name: 'Excluir projeto' })).toBeInTheDocument();
  });

  it('ships the verbatim pt-BR close affordance "Fechar" at the 44px floor', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Abrir' }));
    const close = screen.getByRole('button', { name: 'Fechar' });
    expect(close.className).toContain('min-h-11');
    expect(close.className).toContain('min-w-11');
  });

  it('closes via Fechar', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Abrir' }));
    fireEvent.click(screen.getByRole('button', { name: 'Fechar' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('title carries the display face; overlay carries the scrim token', () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole('button', { name: 'Abrir' }));
    expect(screen.getByText('Excluir projeto').className).toContain('type-display');
    // Overlay lives in a Radix portal — query the document, not DOM siblings.
    const overlay = document.querySelector('[data-slot="dialog-overlay"]');
    expect(overlay?.className).toContain('bg-scrim');
  });
});