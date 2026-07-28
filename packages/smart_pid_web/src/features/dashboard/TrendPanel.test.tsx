import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { queryKeys } from '@/api/queryKeys';
import { makeController } from '@/test/fixtures';
import { createFakeRealtime, createQueryClient, TestProviders } from '@/test/providers';
import { TrendPanel, buildTrendCsv, windowSeconds } from './TrendPanel';

const here = dirname(fileURLToPath(import.meta.url));
const scale = { euMin: 0, euMax: 200, unit: '°C' };

function renderPanel() {
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.controllers, [makeController({ id: 5, name: 'PIC-005' })]);
  const realtime = createFakeRealtime();
  return {
    ...render(
      <TestProviders queryClient={queryClient} realtime={realtime.value}>
        <TrendPanel controllerId={5} scale={scale} />
      </TestProviders>,
    ),
    realtime,
  };
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
});

describe('trend signature invariants', () => {
  it('never reaches for ctx.shadowBlur — the banned §6.7 per-frame path', () => {
    // Prose may name the ban; executable code may not contain it.
    const code = (file: string): string =>
      readFileSync(resolve(here, file), 'utf8')
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/(^|[^:])\/\/[^\n]*/g, '$1');
    expect(code('TrendPanel.tsx')).not.toContain('shadowBlur');
    expect(code('../../components/Trend.tsx')).not.toContain('shadowBlur');
  });

  it('converts the window control to seconds per unit', () => {
    expect(windowSeconds(30, 'segundo')).toBe(30);
    expect(windowSeconds(30, 'minuto')).toBe(1800);
    expect(windowSeconds(2, 'hora')).toBe(7200);
  });

  it('serialises exactly the plotted rows to CSV', () => {
    const csv = buildTrendCsv({ t: [10, 20], pv: [1, null], sp: [2, 2.5], co: [3, 4] }, scale);
    const lines = csv.split('\n');
    expect(lines[0]).toBe('timestamp,pv_°C,sp_°C,co_%');
    expect(lines).toHaveLength(3);
    expect(lines[1]).toBe('1970-01-01T00:00:10.000Z,1,2,3');
    // A null column stays empty rather than fabricating a value.
    expect(lines[2]).toBe('1970-01-01T00:00:20.000Z,,2.5,4');
  });
});

describe('TrendPanel', () => {
  it('renders the recorder controls with their defaults', () => {
    renderPanel();
    expect(screen.getByLabelText('Janela de tempo')).toHaveValue(30);
    expect(screen.getByLabelText('Autoescala')).toBeChecked();
    expect(screen.getByRole('img', { name: 'Tendência PIC-005' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Exportar CSV' })).toBeVisible();
    expect(screen.getByRole('combobox', { name: 'Unidade da janela' })).toHaveTextContent('minutos');
  });

  it('reveals manual PV and CO bounds only when auto-scale is off', () => {
    renderPanel();
    expect(screen.queryByLabelText('PV mínimo')).not.toBeInTheDocument();
    fireEvent.click(screen.getByLabelText('Autoescala'));
    expect(screen.getByLabelText('Autoescala')).not.toBeChecked();
    expect(screen.getByLabelText('PV mínimo')).toHaveValue(0);
    expect(screen.getByLabelText('PV máximo')).toHaveValue(200);
    expect(screen.getByLabelText('CO mínimo')).toHaveValue(0);
    expect(screen.getByLabelText('CO máximo')).toHaveValue(100);
  });

  it('turns the halo on from --glow-trace, never from a theme id', async () => {
    const style = document.createElement('style');
    style.textContent =
      '[data-theme="recorder"] { --glow-trace: 0px; } [data-theme="neon"] { --glow-trace: 8px; }';
    document.head.appendChild(style);

    localStorage.setItem('spid.theme', 'recorder');
    const recorder = renderPanel();
    expect(recorder.getByRole('img', { name: 'Tendência PIC-005' })).toHaveAttribute(
      'data-glow',
      'off',
    );
    recorder.unmount();

    localStorage.setItem('spid.theme', 'neon');
    renderPanel();
    await waitFor(() =>
      expect(screen.getByRole('img', { name: 'Tendência PIC-005' })).toHaveAttribute(
        'data-glow',
        'on',
      ),
    );

    style.remove();
  });

  it('names no theme in its source — the halo is token-driven (§10.5/D12)', () => {
    const code = (file: string): string =>
      readFileSync(resolve(here, file), 'utf8')
        .replace(/\/\*[\s\S]*?\*\//g, '')
        .replace(/(^|[^:])\/\/[^\n]*/g, '$1');
    expect(code('TrendPanel.tsx')).not.toContain("'phosphor'");
    expect(code('../simulator/TwinTrend.tsx')).not.toContain("'phosphor'");
  });

  it('exports a CSV blob named after the loop', () => {
    const createObjectURL = vi.fn(() => 'blob:csv');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined);

    renderPanel();
    fireEvent.click(screen.getByRole('button', { name: 'Exportar CSV' }));

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:csv');

    click.mockRestore();
    vi.unstubAllGlobals();
  });
});
