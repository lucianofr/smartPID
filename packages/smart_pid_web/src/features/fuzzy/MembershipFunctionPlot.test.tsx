import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  MembershipFunctionPlot,
  PLOT_BOTTOM,
  PLOT_LEFT,
  PLOT_RIGHT,
  PLOT_TOP,
  clampToDomain,
  mfPolylinePoints,
  scaleX,
  scaleY,
} from './MembershipFunctionPlot';
import type { FuzzyInput } from './types';

// domain 0..8, both breakpoints chosen so every scaled coordinate is an
// integer (no floating-point rounding ambiguity in the assertions below).
const INPUT: FuzzyInput = {
  name: 'iae',
  value: 4,
  domainMin: 0,
  domainMax: 8,
  functions: [
    { label: 'LOW', kind: 'tri', params: [0, 0, 4], degree: 0 },
    { label: 'MEDIUM', kind: 'tri', params: [0, 4, 8], degree: 0.6 },
  ],
};

function parsePoints(points: string): Array<[number, number]> {
  return points
    .trim()
    .split(' ')
    .map((pair) => {
      const [x, y] = pair.split(',').map(Number);
      return [x, y] as [number, number];
    });
}

describe('scaleX / scaleY / clampToDomain (pure)', () => {
  it('maps the domain bounds to the plot edges', () => {
    expect(scaleX(0, 0, 8)).toBe(PLOT_LEFT);
    expect(scaleX(8, 0, 8)).toBe(PLOT_RIGHT);
    expect(scaleX(4, 0, 8)).toBe(PLOT_LEFT + (PLOT_RIGHT - PLOT_LEFT) / 2);
  });

  it('maps membership degree 0/1 to the plot bottom/top (SVG y grows downward)', () => {
    expect(scaleY(0)).toBe(PLOT_BOTTOM);
    expect(scaleY(1)).toBe(PLOT_TOP);
    expect(scaleY(0.5)).toBe(PLOT_BOTTOM - (PLOT_BOTTOM - PLOT_TOP) / 2);
  });

  it('clamps a domain value that overflows the domain instead of extrapolating', () => {
    expect(clampToDomain(-5, 0, 8)).toBe(0);
    expect(clampToDomain(1e9, 0, 8)).toBe(8);
    expect(clampToDomain(4, 0, 8)).toBe(4);
  });
});

describe('mfPolylinePoints (pure)', () => {
  it('scales a triangular MF to the expected plot coordinates', () => {
    const mf = { label: 'MEDIUM', kind: 'tri', params: [0, 4, 8], degree: 0.6 };
    expect(mfPolylinePoints(mf, 0, 8)).toBe(
      `${PLOT_LEFT},${PLOT_BOTTOM} 167,${PLOT_TOP} ${PLOT_RIGHT},${PLOT_BOTTOM}`,
    );
  });

  it('clamps a saturated trapezoid plateau to the domain max, never past it', () => {
    // MF_E_MAX_DR / MF_T_REC_DR shape: right-side breakpoints saturate at 1e9.
    const mf = { label: 'MF_E_MAX_DR', kind: 'trap', params: [0, 1, 1e9, 1e9], degree: 0 };
    const points = parsePoints(mfPolylinePoints(mf, 0, 20));
    expect(points).toHaveLength(4);
    for (const [x, y] of points) {
      expect(x).toBeGreaterThanOrEqual(PLOT_LEFT);
      expect(x).toBeLessThanOrEqual(PLOT_RIGHT);
      expect(y).toBeGreaterThanOrEqual(PLOT_TOP);
      expect(y).toBeLessThanOrEqual(PLOT_BOTTOM);
    }
    // The plateau terminates cleanly at the domain's right edge, not beyond it.
    expect(points[2][0]).toBe(PLOT_RIGHT);
    expect(points[3][0]).toBe(PLOT_RIGHT);
  });
});

describe('MembershipFunctionPlot', () => {
  it('renders one curve per membership function', () => {
    const { container } = render(<MembershipFunctionPlot input={INPUT} />);
    expect(container.querySelectorAll('polyline')).toHaveLength(INPUT.functions.length);
  });

  it('renders the exact scaled points for a known triangular MF', () => {
    render(<MembershipFunctionPlot input={INPUT} />);
    expect(screen.getByTestId('mf-polyline-MEDIUM')).toHaveAttribute(
      'points',
      `${PLOT_LEFT},${PLOT_BOTTOM} 167,${PLOT_TOP} ${PLOT_RIGHT},${PLOT_BOTTOM}`,
    );
  });

  it('places the crisp-input marker at the scaled value — the reason SVG was chosen over uPlot', () => {
    render(<MembershipFunctionPlot input={INPUT} />);
    const marker = screen.getByTestId('crisp-input-marker');
    const expectedX = String(scaleX(INPUT.value, INPUT.domainMin, INPUT.domainMax));
    expect(marker).toHaveAttribute('x1', expectedX);
    expect(marker).toHaveAttribute('x2', expectedX);
  });

  it('draws a membership-degree dot only for MFs the crisp input activates', () => {
    render(<MembershipFunctionPlot input={INPUT} />);
    expect(screen.getByTestId('mf-degree-dot-MEDIUM')).toBeInTheDocument();
    expect(screen.queryByTestId('mf-degree-dot-LOW')).not.toBeInTheDocument();
  });

  it('labels each MF, adding the membership degree only when active', () => {
    render(<MembershipFunctionPlot input={INPUT} />);
    expect(screen.getByText('LOW')).toBeInTheDocument();
    expect(screen.getByText('MEDIUM 0.60')).toBeInTheDocument();
  });

  it('labels both domain bounds and the crisp value', () => {
    render(<MembershipFunctionPlot input={INPUT} />);
    expect(screen.getByText('0.00')).toBeInTheDocument();
    expect(screen.getByText('8.00')).toBeInTheDocument();
    expect(screen.getByText('4.00')).toBeInTheDocument();
  });

  it('drops the domain-bound label the crisp readout would sit on top of', () => {
    // Crisp value AT the domain minimum: both labels would land on the same
    // x and render as one unreadable run (`0.000.00`).
    const atMin: FuzzyInput = { ...INPUT, value: 0 };
    render(<MembershipFunctionPlot input={atMin} />);
    // The crisp readout survives; the lower bound it collides with does not.
    expect(screen.getAllByText('0.00')).toHaveLength(1);
    expect(screen.getByText('8.00')).toBeInTheDocument();
  });

  it('staggers neighbouring MF labels onto separate rows so they cannot run together', () => {
    // MF_OVS-shaped: NONE and MOD peak a few domain units apart, which on one
    // row renders as `NONE 1.00MOD`.
    const crowded: FuzzyInput = {
      name: 'ovs',
      value: 0,
      domainMin: 0,
      domainMax: 1,
      functions: [
        { label: 'NONE', kind: 'trap', params: [0, 0, 0.02, 0.06], degree: 1 },
        { label: 'MOD', kind: 'tri', params: [0.04, 0.12, 0.22], degree: 0 },
        { label: 'HIGH', kind: 'trap', params: [0.15, 0.3, 1, 1], degree: 0 },
      ],
    };
    render(<MembershipFunctionPlot input={crowded} />);
    const noneRow = screen.getByText('NONE 1.00').getAttribute('y');
    expect(screen.getByText('MOD').getAttribute('y')).not.toBe(noneRow);
    // Alternating rows: the third label shares a row with the first, and the
    // gap between them is wide enough that they cannot collide.
    expect(screen.getByText('HIGH').getAttribute('y')).toBe(noneRow);
  });

  it('keeps an edge-peaked MF label inside the plot area instead of overhanging it', () => {
    const atEdges: FuzzyInput = {
      ...INPUT,
      functions: [
        // Both plateau against a domain edge, so a centred label would hang
        // outside the plot area (`SMOOTH 1.00` spilling left of the y axis).
        { label: 'SMOOTH', kind: 'trap', params: [0, 0, 1.6, 3.2], degree: 1 },
        { label: 'EXCESS', kind: 'trap', params: [6.4, 8, 8, 8], degree: 0 },
      ],
    };
    render(<MembershipFunctionPlot input={atEdges} />);
    const left = screen.getByText('SMOOTH 1.00');
    const right = screen.getByText('EXCESS');
    expect(left).toHaveAttribute('x', String(PLOT_LEFT));
    expect(left).toHaveAttribute('text-anchor', 'start');
    expect(right).toHaveAttribute('x', String(PLOT_RIGHT));
    expect(right).toHaveAttribute('text-anchor', 'end');
  });

  it('does not let a saturated trapezoid overflow the plot viewBox when rendered', () => {
    const input: FuzzyInput = {
      name: 'e_max_dr',
      value: 12,
      domainMin: 0,
      domainMax: 20,
      functions: [{ label: 'MF_E_MAX_DR', kind: 'trap', params: [0, 1, 1e9, 1e9], degree: 0 }],
    };
    render(<MembershipFunctionPlot input={input} />);
    const points = parsePoints(
      screen.getByTestId('mf-polyline-MF_E_MAX_DR').getAttribute('points') ?? '',
    );
    expect(points.length).toBeGreaterThan(0);
    for (const [x, y] of points) {
      expect(x).toBeGreaterThanOrEqual(PLOT_LEFT);
      expect(x).toBeLessThanOrEqual(PLOT_RIGHT);
      expect(y).toBeGreaterThanOrEqual(PLOT_TOP);
      expect(y).toBeLessThanOrEqual(PLOT_BOTTOM);
    }
  });
});
