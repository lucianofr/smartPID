import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Button } from './Button';

describe('Button', () => {
  it('renders type=button by default with its accessible name', () => {
    render(<Button>Salvar</Button>);
    const btn = screen.getByRole('button', { name: 'Salvar' });
    expect(btn).toHaveAttribute('type', 'button');
  });

  it('meets the 44px touch floor and the ≥2px focus ring class contract (§12)', () => {
    render(<Button>Entrar</Button>);
    const btn = screen.getByRole('button', { name: 'Entrar' });
    expect(btn.className).toContain('min-h-11');
    expect(btn.className).toContain('min-w-11');
    expect(btn.className).toContain('focus-visible:ring-2');
    expect(btn.className).toContain('focus-visible:ring-focus-ring');
  });

  it('variant classes are token-only', () => {
    const { rerender } = render(<Button variant="primary">a</Button>);
    expect(screen.getByRole('button').className).toContain('bg-accent');
    // §10.5 bloom hook — primary only; secondary/ghost/destructive stay flat.
    expect(screen.getByRole('button').className).toContain('btn-primary');
    rerender(<Button variant="destructive">a</Button>);
    expect(screen.getByRole('button').className).toContain('bg-alarm-crit');
    expect(screen.getByRole('button').className).not.toContain('btn-primary');
    rerender(<Button variant="ghost">a</Button>);
    expect(screen.getByRole('button').className).toContain('text-text-soft');
    expect(screen.getByRole('button').className).not.toContain('btn-primary');
  });

  it('disabled blocks activation', () => {
    const onClick = vi.fn();
    render(
      <Button disabled onClick={onClick}>
        x
      </Button>,
    );
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).not.toHaveBeenCalled();
  });
});