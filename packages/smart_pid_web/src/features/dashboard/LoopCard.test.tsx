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
    render(
      <LoopCard controller={controller} status={status} onOpenConfig={open} onSelect={vi.fn()} />,
    );
    expect(screen.getByText('PIC-005')).toBeVisible();
    expect(screen.getByText('AUTO', { selector: 'span.numeric' })).toBeVisible();
    expect(screen.getByText('150.2')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Configurar PIC-005' }));
    expect(open).toHaveBeenCalledWith(5);
  });

  it('exposes PV, SP and CO as meters on the controller scale', () => {
    render(
      <LoopCard controller={controller} status={status} onOpenConfig={vi.fn()} onSelect={vi.fn()} />,
    );
    const pv = screen.getByRole('meter', { name: 'PV' });
    expect(pv).toHaveAttribute('aria-valuenow', '150.2');
    expect(pv).toHaveAttribute('aria-valuemax', '200');
    expect(screen.getByRole('meter', { name: 'SP' })).toHaveAttribute('aria-valuenow', '152');
    // CO is a valve percentage, never the PV engineering scale.
    expect(screen.getByRole('meter', { name: 'CO' })).toHaveAttribute('aria-valuemax', '100');
  });

  it('degrades to em dashes before the first status frame', () => {
    render(<LoopCard controller={controller} status={null} onOpenConfig={vi.fn()} onSelect={vi.fn()} />);
    expect(screen.getByText('PIC-005')).toBeVisible();
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('never wraps: the card keeps a fixed width and does not shrink', () => {
    const { container } = render(
      <LoopCard controller={controller} status={status} onOpenConfig={vi.fn()} onSelect={vi.fn()} />,
    );
    const card = container.firstElementChild;
    expect(card?.className).toContain('shrink-0');
  });

  it('borders with the same color as the card when no alarm is active', () => {
    const { container } = render(
      <LoopCard controller={controller} status={status} onOpenConfig={vi.fn()} onSelect={vi.fn()} />,
    );
    expect(container.firstElementChild?.className).toContain('border-surface');
    expect(container.firstElementChild?.className).not.toContain('border-alarm');
  });

  it('borders with the active alarm priority color', () => {
    const { container, rerender } = render(
      <LoopCard
        controller={controller}
        status={status}
        onOpenConfig={vi.fn()}
        onSelect={vi.fn()}
        alarmSeverity="CRITICAL"
      />,
    );
    expect(container.firstElementChild?.className).toContain('border-alarm-crit');

    rerender(
      <LoopCard
        controller={controller}
        status={status}
        onOpenConfig={vi.fn()}
        onSelect={vi.fn()}
        alarmSeverity="WARNING"
      />,
    );
    expect(container.firstElementChild?.className).toContain('border-alarm-warn');
    expect(container.firstElementChild?.className).not.toContain('border-alarm-crit');
  });

  it('still marks bad fieldbus quality with a corner dot, independent of the alarm border', () => {
    render(
      <LoopCard
        controller={controller}
        status={makeStatus({ pv: ff(150.2, 'BAD_SENSOR_FAILURE') })}
        onOpenConfig={vi.fn()}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByTestId('loop-card-quality-dot')).toBeVisible();
  });

  it('selects the loop when the card is clicked, without triggering configure', () => {
    const onSelect = vi.fn();
    const onOpenConfig = vi.fn();
    render(
      <LoopCard
        controller={controller}
        status={status}
        onOpenConfig={onOpenConfig}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'PIC-005' }));
    expect(onSelect).toHaveBeenCalledWith(5);
    expect(onOpenConfig).not.toHaveBeenCalled();
  });

  it('does not select the loop when only the configure button is clicked', () => {
    const onSelect = vi.fn();
    render(
      <LoopCard controller={controller} status={status} onOpenConfig={vi.fn()} onSelect={onSelect} />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Configurar PIC-005' }));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it('has no sparkline canvas', () => {
    const { container } = render(
      <LoopCard controller={controller} status={status} onOpenConfig={vi.fn()} onSelect={vi.fn()} />,
    );
    expect(container.querySelector('canvas')).toBeNull();
  });

  it('labels the config button with a slider icon, not a bracketed glyph', () => {
    render(
      <LoopCard controller={controller} status={status} onOpenConfig={vi.fn()} onSelect={vi.fn()} />,
    );
    const config = screen.getByRole('button', { name: 'Configurar PIC-005' });
    expect(config).toHaveTextContent('');
    expect(config.querySelector('svg')).not.toBeNull();
    expect(config.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });
});
