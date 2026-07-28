import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
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

// Every production dialog (LoopConfigDialog, NewLoopDialog, UserDialog, etc.)
// is opened by a button OUTSIDE the <Dialog> tree via external `open` state —
// there is no <DialogTrigger> anywhere in real usage. This harness mirrors
// that pattern; the button below is a sibling of <Dialog>, not its trigger.
function ExternalHarness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Abrir externo
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogTitle>Configurar malha</DialogTitle>
          <DialogDescription>Ajuste os parâmetros do controlador.</DialogDescription>
        </DialogContent>
      </Dialog>
    </>
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

  it('restores focus to the external opener button (no DialogTrigger) on close via Fechar', async () => {
    render(<ExternalHarness />);
    const opener = screen.getByRole('button', { name: 'Abrir externo' });
    // jsdom's fireEvent.click does not simulate the browser's click-focus default
    // action (unlike real Chrome/Firefox, and unlike a keyboard Enter/Space
    // activation everywhere). Focus the opener explicitly so the scenario
    // matches what real users hit: focus on the opener at the moment it opens
    // the dialog.
    opener.focus();
    fireEvent.click(opener);
    await screen.findByRole('dialog', { name: 'Configurar malha' });
    fireEvent.click(screen.getByRole('button', { name: 'Fechar' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await waitFor(() => expect(document.activeElement).toBe(opener));
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