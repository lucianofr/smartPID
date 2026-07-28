import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { EmptyState, ErrorState, LoadingState } from './MissingState';

describe('MissingState', () => {
  it('LoadingState: aria-busy, static bars, greyed last-known value', () => {
    render(<LoadingState label="Carregando controladores…" lastKnown={<span>150.2</span>} />);
    const region = screen.getByLabelText('Carregando controladores…');
    expect(region).toHaveAttribute('aria-busy', 'true');
    expect(region.querySelectorAll('[data-slot="loading-bar"]')).toHaveLength(4);
    expect(screen.getByText('150.2')).toBeInTheDocument();
  });

  it('LoadingState carries no animation utilities (motion must not draw the eye)', () => {
    render(<LoadingState label="x" />);
    expect(screen.getByLabelText('x').innerHTML).not.toContain('animate-');
  });

  it('EmptyState: message + hint + action slot', () => {
    render(<EmptyState message="Nenhum alarme ativo" hint="Tudo operando normalmente" />);
    expect(screen.getByText('Nenhum alarme ativo')).toBeInTheDocument();
    expect(screen.getByText('Tudo operando normalmente')).toBeInTheDocument();
  });

  it('ErrorState: role=alert with pt-BR retry affordance', () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Sem conexão com o servidor" onRetry={onRetry} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Sem conexão com o servidor');
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});