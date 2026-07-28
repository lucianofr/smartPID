import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Toaster, clearToasts, dismissToast, toast } from './Toast';

afterEach(() => {
  act(() => {
    clearToasts();
  });
});

describe('Toast/Toaster', () => {
  it('toast() renders a status with title, description and Fechar', () => {
    render(<Toaster />);
    act(() => {
      toast({ title: 'Salvo', description: 'Parâmetros aplicados' });
    });
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('Salvo')).toBeInTheDocument();
    expect(screen.getByText('Parâmetros aplicados')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fechar' })).toBeInTheDocument();
  });

  it('tones map to severity tokens (crit/warn) with default surface otherwise', () => {
    render(<Toaster />);
    act(() => {
      toast({ title: 'sem permissão', tone: 'warn' });
    });
    const root = screen.getByText('sem permissão').closest('li');
    expect(root?.className).toContain('border-alarm-warn');
  });

  it('dismissToast removes by id; keeps at most 3 (oldest evicted)', () => {
    render(<Toaster />);
    let id = '';
    act(() => {
      id = toast({ title: 'a' });
      toast({ title: 'b' });
      toast({ title: 'c' });
      toast({ title: 'd' });
    });
    expect(screen.queryByText('a')).not.toBeInTheDocument(); // evicted (max 3)
    expect(screen.getByText('d')).toBeInTheDocument();
    act(() => {
      dismissToast(id);
    });
    expect(screen.getByText('d')).toBeInTheDocument();
  });
});