import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ff, makeController, makeStatus } from '@/test/fixtures';
import { LoopCard } from './LoopCard';

const controller = makeController({
  id: 5,
  name: 'PIC-005',
  description: 'Pressure',
  pv_scale: { eu_min: 0, eu_max: 200, unit: '°C' },
});
const status = makeStatus({ controller_id: 5, pv: ff(150.2), sp: ff(152), co: ff(64) });

describe('LoopCard', () => {
  it('renders live values and emits configure id', () => {
    const open = vi.fn();
    render(<LoopCard controller={controller} status={status} onOpenConfig={open} />);
    expect(screen.getByText('PIC-005')).toBeVisible();
    expect(screen.getByText('AUTO', { selector: 'span.numeric' })).toBeVisible();
    expect(screen.getByText('150.2')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Configurar PIC-005' }));
    expect(open).toHaveBeenCalledWith(5);
  });

  it('exposes PV, SP and CO as meters on the controller scale', () => {
    render(<LoopCard controller={controller} status={status} onOpenConfig={vi.fn()} />);
    const pv = screen.getByRole('meter', { name: 'PV' });
    expect(pv).toHaveAttribute('aria-valuenow', '150.2');
    expect(pv).toHaveAttribute('aria-valuemax', '200');
    expect(screen.getByRole('meter', { name: 'SP' })).toHaveAttribute('aria-valuenow', '152');
    // CO is a valve percentage, never the PV engineering scale.
    expect(screen.getByRole('meter', { name: 'CO' })).toHaveAttribute('aria-valuemax', '100');
  });

  it('degrades to em dashes before the first status frame', () => {
    render(<LoopCard controller={controller} status={null} onOpenConfig={vi.fn()} />);
    expect(screen.getByText('PIC-005')).toBeVisible();
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('never wraps: the card keeps a fixed width and does not shrink', () => {
    const { container } = render(
      <LoopCard controller={controller} status={status} onOpenConfig={vi.fn()} />,
    );
    const card = container.firstElementChild;
    expect(card?.className).toContain('shrink-0');
  });

  it('borders with the alarm token only while signal quality is bad', () => {
    const { container, rerender } = render(
      <LoopCard controller={controller} status={status} onOpenConfig={vi.fn()} />,
    );
    expect(container.firstElementChild?.className).toContain('border-rule');
    expect(container.firstElementChild?.className).not.toContain('border-alarm-crit');

    rerender(
      <LoopCard
        controller={controller}
        status={makeStatus({ pv: ff(150.2, 'BAD_SENSOR_FAILURE') })}
        onOpenConfig={vi.fn()}
      />,
    );
    expect(container.firstElementChild?.className).toContain('border-alarm-crit');
  });

  it('renders the phase-5 controls slot', () => {
    render(
      <LoopCard
        controller={controller}
        status={status}
        onOpenConfig={vi.fn()}
        controlsSlot={<button type="button">Abrir</button>}
      />,
    );
    expect(screen.getByRole('button', { name: 'Abrir' })).toBeVisible();
  });

  it('has no sparkline canvas', () => {
    const { container } = render(
      <LoopCard controller={controller} status={status} onOpenConfig={vi.fn()} />,
    );
    expect(container.querySelector('canvas')).toBeNull();
  });
});
