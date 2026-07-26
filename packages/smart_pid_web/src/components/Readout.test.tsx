import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Readout } from './Readout';

describe('Readout', () => {
  it('shows label, formatted value and unit', () => {
    render(<Readout label="PV" value={150.25} unit="°C" decimals={1} />);
    expect(screen.getByText('PV')).toBeInTheDocument();
    expect(screen.getByText('150.3')).toBeInTheDocument();
    expect(screen.getByText('°C')).toBeInTheDocument();
  });

  it('every numeral is Geist Mono — value carries the .numeric class (§6.2)', () => {
    render(<Readout label="SP" value={148} />);
    expect(screen.getByText('148.0').className).toContain('numeric');
  });

  it('renders the em dash when the value is missing', () => {
    render(<Readout label="CO" value={null} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});