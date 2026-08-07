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

  it('normal fill matches the trend line color for the same variable', () => {
    const { rerender } = render(<AnalogBar label="PV" value={100} scale={scale} />);
    expect(screen.getByTestId('analog-bar-fill').style.background).toBe('var(--trace-pv)');

    rerender(<AnalogBar label="SP" value={100} scale={scale} />);
    expect(screen.getByTestId('analog-bar-fill').style.background).toBe('var(--trace-sp)');

    rerender(<AnalogBar label="CO" value={100} scale={scale} />);
    expect(screen.getByTestId('analog-bar-fill').style.background).toBe('var(--trace-co)');
  });

  it('faceplate sizing no longer singles out PV — same bar and figure size as SP/CO', () => {
    render(<AnalogBar label="PV" value={100} scale={scale} size="faceplate" />);
    const meter = screen.getByRole('meter', { name: 'PV' });
    expect(meter.className).toContain('h-2.5');
    expect(meter.className).not.toContain('h-3.5');
    const figure = screen.getByText('100.0');
    expect(figure.className).toContain('text-lg');
    expect(figure.className).not.toContain('text-3xl');
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

  // The unit was previously only in `aria-valuetext`: a sighted operator read
  // "150.2" with no way to know whether that was °C, bar or %.
  it('prints the engineering unit next to the figure', () => {
    render(<AnalogBar label="PV" value={150.2} scale={scale} />);
    expect(screen.getByText('°C')).toBeVisible();
    // Its own element, never appended to the numeral: the figure column is
    // right-aligned mono and e2e anchors read the number alone.
    expect(screen.getByText('150.2')).toBeInTheDocument();
  });

  it('prints nothing when the loop has no unit configured', () => {
    const { container } = render(
      <AnalogBar label="CO" value={42} scale={{ euMin: 0, euMax: 100, unit: '' }} />,
    );
    expect(container.textContent).toBe('CO42.0');
  });
});