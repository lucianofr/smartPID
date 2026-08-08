import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Legend, type LegendGroup } from './Legend';

const GROUPS: readonly LegendGroup[] = [
  {
    title: 'Integrais de erro',
    entries: [
      { term: 'IAE', description: 'Integral do erro absoluto' },
      { term: 'ISE', description: 'Integral do erro quadrático' },
    ],
  },
  {
    title: 'osc',
    entries: [{ term: 'HIGH', description: 'Oscilação forte' }],
  },
];

describe('Legend', () => {
  it('renders every term with its description, grouped', () => {
    render(<Legend groups={GROUPS} />);
    const integrals = screen.getByRole('region', { name: 'Integrais de erro' });
    expect(within(integrals).getByText('IAE')).toBeInTheDocument();
    expect(within(integrals).getByText('Integral do erro absoluto')).toBeInTheDocument();
    expect(within(integrals).getByText('ISE')).toBeInTheDocument();
  });

  it('scopes a term to its group so the same token can mean two things', () => {
    // `HIGH` under `iae` is a large error; under `osc` it is a strong
    // oscillation. Merging the groups would make one of them a lie.
    render(
      <Legend
        groups={[
          { title: 'iae', entries: [{ term: 'HIGH', description: 'Erro grande' }] },
          { title: 'osc', entries: [{ term: 'HIGH', description: 'Oscilação forte' }] },
        ]}
      />,
    );
    expect(
      within(screen.getByRole('region', { name: 'iae' })).getByText('Erro grande'),
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'osc' })).getByText('Oscilação forte'),
    ).toBeInTheDocument();
  });

  it('is collapsed by default so it never pushes the data off screen', () => {
    const { container } = render(<Legend groups={GROUPS} />);
    expect(container.querySelector('details')).not.toHaveAttribute('open');
    expect(screen.getByText('Legenda')).toBeInTheDocument();
  });

  it('drops empty groups and renders nothing when no group has entries', () => {
    const { container } = render(
      <Legend groups={[{ title: 'Vazio', entries: [] }, GROUPS[0]]} />,
    );
    expect(screen.queryByRole('region', { name: 'Vazio' })).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Integrais de erro' })).toBeInTheDocument();

    const { container: empty } = render(<Legend groups={[{ title: 'Vazio', entries: [] }]} />);
    expect(empty.querySelector('details')).toBeNull();
    expect(container.querySelector('details')).not.toBeNull();
  });
});
