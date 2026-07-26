import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { Trend, type TrendSeriesData } from './Trend';

const data: TrendSeriesData = {
  t: [1000, 1001, 1002],
  pv: [150.1, 150.2, 150.4],
  sp: [148, 148, 148],
  co: [42.0, 42.1, 42.3],
};

afterEach(() => {
  document.documentElement.removeAttribute('data-theme');
});

describe('Trend', () => {
  it('renders an accessible chart region (role=img + pt-BR name)', () => {
    render(<Trend data={data} ariaLabel="Tendência FIC-101" height={200} />);
    expect(screen.getByRole('img', { name: 'Tendência FIC-101' })).toBeInTheDocument();
  });

  it('mounts with penTip, aiTicks and glow without crashing (jsdom canvas stubbed)', () => {
    render(
      <Trend
        data={data}
        ariaLabel="t"
        penTip={{ t: 1002, pv: 150.4 }}
        aiTicks={[1001]}
        glow
        height={200}
      />,
    );
    expect(screen.getByRole('img', { name: 't' })).toBeInTheDocument();
  });

  it('re-instantiates the plot when [data-theme] flips (themeKey pattern)', async () => {
    render(<Trend data={data} ariaLabel="t" height={200} />);
    const region = screen.getByRole('img', { name: 't' });
    expect(region).toHaveAttribute('data-theme-key', '0');
    act(() => {
      document.documentElement.setAttribute('data-theme', 'phosphor');
    });
    await waitFor(() => expect(region).toHaveAttribute('data-theme-key', '1'));
  });
});