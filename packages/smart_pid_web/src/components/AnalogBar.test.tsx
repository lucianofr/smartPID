import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AnalogBar } from './AnalogBar';

const scale = { euMin: 0, euMax: 200, unit: '°C' };

function fillWidth(el: HTMLElement): number {
  // fill is a child with inline width: NN% (or scaleX transform); read the % number
  const fill = el.querySelector('[data-testid="bar-fill"]') as HTMLElement;
  const w = fill.style.width || fill.style.transform;
  const m = /([\d.]+)/.exec(w);
  return m ? parseFloat(m[1]) : NaN;
}

describe('AnalogBar instrumentation', () => {
  it('meter exposes aria value bounds and current value', () => {
    render(<AnalogBar label="PV" value={150.2} scale={scale} />);
    const meter = screen.getByRole('meter');
    expect(meter).toHaveAttribute('aria-valuemin', '0');
    expect(meter).toHaveAttribute('aria-valuemax', '200');
    expect(meter).toHaveAttribute('aria-valuenow', '150.2');
  });

  it('fill position maps measurably to PV vs scale (50 < 100 < 150)', () => {
    const { rerender, container } = render(<AnalogBar label="PV" value={50} scale={scale} />);
    const low = fillWidth(container);
    rerender(<AnalogBar label="PV" value={100} scale={scale} />);
    const mid = fillWidth(container);
    rerender(<AnalogBar label="PV" value={150} scale={scale} />);
    const high = fillWidth(container);
    expect(mid).toBeCloseTo(50, 1); // 100/200 = 50%
    expect(low).toBeLessThan(mid);
    expect(mid).toBeLessThan(high);
  });

  it('renders neutral fill when alarm is normal (no alarm token applied)', () => {
    const { container } = render(<AnalogBar label="PV" value={100} scale={scale} alarm="normal" />);
    const fill = container.querySelector('[data-testid="bar-fill"]') as HTMLElement;
    expect(fill.getAttribute('data-alarm')).toBe('normal');
  });

  it('applies critical alarm fill ONLY on abnormal state', () => {
    const { container } = render(<AnalogBar label="PV" value={195} scale={scale} alarm="critical" />);
    const fill = container.querySelector('[data-testid="bar-fill"]') as HTMLElement;
    expect(fill.getAttribute('data-alarm')).toBe('critical');
    const value = screen.getByTestId('bar-value');
    expect(value).toHaveStyle({ fontWeight: '600' });
  });

  it('shows SP marker only when spValue is given (PV-bar signature)', () => {
    const { rerender, container } = render(<AnalogBar label="PV" value={150} scale={scale} />);
    expect(container.querySelector('[data-testid="sp-marker"]')).toBeNull();
    rerender(<AnalogBar label="PV" value={150} scale={scale} spValue={152} />);
    expect(container.querySelector('[data-testid="sp-marker"]')).not.toBeNull();
  });

  it('renders placeholder and omits aria-valuenow when value is missing', () => {
    render(<AnalogBar label="PV" value={undefined} scale={scale} />);
    const meter = screen.getByRole('meter');
    expect(meter).not.toHaveAttribute('aria-valuenow');
    expect(screen.getByTestId('bar-value')).toHaveTextContent('—');
  });

  it('honors the decimals prop in the value readout', () => {
    render(<AnalogBar label="PV" value={12.345} scale={scale} decimals={2} />);
    expect(screen.getByTestId('bar-value')).toHaveTextContent('12.35');
  });

  it('defaults to 1 decimal when decimals prop is omitted', () => {
    render(<AnalogBar label="PV" value={12.345} scale={scale} />);
    expect(screen.getByTestId('bar-value')).toHaveTextContent('12.3');
  });
});
