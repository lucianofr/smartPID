import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AnalogBar } from './AnalogBar';

const scale = { euMin: 0, euMax: 200, unit: '°C' };

describe('AnalogBar', () => {
  it('exposes a meter role with EU range and value text', () => {
    render(<AnalogBar label="PV" value={150.2} scale={scale} />);
    const meter = screen.getByRole('meter', { name: 'PV' });
    expect(meter).toHaveAttribute('aria-valuemin', '0');
    expect(meter).toHaveAttribute('aria-valuemax', '200');
    expect(meter).toHaveAttribute('aria-valuenow', '150.2');
    expect(meter).toHaveAttribute('aria-valuetext', '150.2 °C');
  });

  it('fill width tracks the clamped fraction (sanctioned dynamic inline style)', () => {
    render(<AnalogBar label="PV" value={100} scale={scale} />);
    // jsdom serializes "50.00%" → "50%" when reading element.style.width;
    // both forms assert the same fraction.
    expect(screen.getByTestId('analog-bar-fill').style.width).toMatch(/^50(\.\d+)?%$/);
  });

  it('alarm level swaps the fill token var, never a raw color', () => {
    render(<AnalogBar label="PV" value={100} scale={scale} alarm="crit" />);
    expect(screen.getByTestId('analog-bar-fill').style.background).toBe('var(--alarm-crit)');
  });

  it('renders the SP marker when spValue is given', () => {
    render(<AnalogBar label="PV" value={100} scale={scale} spValue={150} />);
    expect(screen.getByTestId('analog-bar-sp').style.left).toMatch(/^75(\.\d+)?%$/);
  });

  it('missing value: 0% fill, em dash, aria-valuetext "sem dados"', () => {
    render(<AnalogBar label="CO" value={null} scale={scale} />);
    expect(screen.getByTestId('analog-bar-fill').style.width).toMatch(/^0(\.\d+)?%$/);
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(screen.getByRole('meter', { name: 'CO' })).toHaveAttribute('aria-valuetext', 'sem dados');
  });

  /**
   * E2E-047 — a frozen reading must never be presented as the current one.
   * These three channels are independent on purpose: ink for a glance, the
   * `*` mark for a colour-blind or dimmed screen, `aria-valuetext` for a
   * screen reader.
   */
  it('a stale reading is dimmed, marked and announced as such', () => {
    render(<AnalogBar label="PV" value={150.2} scale={scale} stale />);
    const meter = screen.getByRole('meter', { name: 'PV' });
    expect(meter).toHaveAttribute('aria-valuetext', '150.2 °C (desatualizado)');
    expect(meter).toHaveAttribute('aria-valuenow', '150.2'); // the value is kept, not blanked
    expect(screen.getByText('*')).toBeInTheDocument();
    expect(screen.getByText('150.2').className).toContain('text-text-disabled');
  });

  it('a stale reading stops asserting an alarm level it can no longer see', () => {
    render(<AnalogBar label="PV" value={100} scale={scale} alarm="crit" stale />);
    expect(screen.getByTestId('analog-bar-fill').style.background).toBe('var(--text-disabled)');
  });

  it('a fresh reading carries no stale marking', () => {
    render(<AnalogBar label="PV" value={150.2} scale={scale} />);
    expect(screen.getByRole('meter', { name: 'PV' })).toHaveAttribute('aria-valuetext', '150.2 °C');
    expect(screen.queryByText('*')).not.toBeInTheDocument();
  });
});