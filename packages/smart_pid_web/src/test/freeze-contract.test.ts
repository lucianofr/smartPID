/**
 * DOM-freeze contract guard (§3a) — see docs/freeze-inventory.md.
 *
 * The Tailwind/shadcn/ISA-101 refactor (Phases 1-8) is big-bang on styling but MUST keep the
 * existing Vitest behavior suite green by NOT changing structural bindings: data-testid,
 * accessible names / aria-label, asserted className, role, asserted data-*, and the dynamic
 * inline styles tests read.
 *
 * This is a FAST guard over the highest-risk *swapped* primitives. If any of these frozen hooks
 * disappears, this test fails immediately — before the full suite runs. It renders the components
 * standalone, mirroring each component's own test harness (mocks copied from the source tests, not
 * invented). It does not replace the per-component tests; it pins the contract those tests depend on.
 *
 * NOTE: this file is `.ts` (per the brief) but renders JSX via React.createElement so it needs no
 * .tsx transform — the assertions are what matter, not JSX ergonomics.
 */
import { createElement as h } from 'react';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { AnalogBar } from '../components/AnalogBar';
import { Dialog } from '../components/ui/Dialog';

const scale = { euMin: 0, euMax: 200, unit: '°C' };

describe('DOM-freeze contract §3a — AnalogBar (analog meter, riskiest swap)', () => {
  it('keeps structural classes, meter role, value bounds, and value testids', () => {
    const { container } = render(h(AnalogBar, { label: 'PV', value: 150.2, scale }));

    // structural classNames the design system must preserve
    expect(container.querySelector('.analog-bar')).not.toBeNull();
    expect(container.querySelector('.analog-bar__label')).not.toBeNull();
    expect(container.querySelector('.analog-bar__track')).not.toBeNull();
    expect(container.querySelector('.analog-bar__value')).not.toBeNull();

    // meter semantics + accessible name format `{label} {value} {unit}`
    const meter = screen.getByRole('meter');
    expect(meter).toHaveAttribute('aria-label', 'PV 150.2 °C');
    expect(meter).toHaveAttribute('aria-valuemin', '0');
    expect(meter).toHaveAttribute('aria-valuemax', '200');
    expect(meter).toHaveAttribute('aria-valuenow', '150.2');

    // testids
    expect(container.querySelector('[data-testid="bar-fill"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="bar-value"]')).not.toBeNull();
  });

  it('keeps the dynamic inline fill width and the data-alarm hook', () => {
    const { container } = render(
      h(AnalogBar, { label: 'PV', value: 100, scale, alarm: 'critical' }),
    );
    const fill = container.querySelector('[data-testid="bar-fill"]') as HTMLElement;
    // tests read fill.style.width (fallback transform) to derive %, so it must stay inline+dynamic
    const inline = fill.style.width || fill.style.transform;
    expect(/[\d.]+/.test(inline)).toBe(true);
    expect(fill.getAttribute('data-alarm')).toBe('critical');
  });

  it('renders sp-marker only when a setpoint is provided', () => {
    const { container, rerender } = render(h(AnalogBar, { label: 'PV', value: 150, scale }));
    expect(container.querySelector('[data-testid="sp-marker"]')).toBeNull();
    rerender(h(AnalogBar, { label: 'PV', value: 150, scale, spValue: 152 }));
    expect(container.querySelector('[data-testid="sp-marker"]')).not.toBeNull();
  });
});

describe('DOM-freeze contract §3a — Dialog (shadcn swap target)', () => {
  it('keeps dialog role, backdrop testid, and the Fechar accessible name', () => {
    render(
      h(Dialog, {
        open: true,
        onClose: () => {},
        title: 'Freeze',
        children: h('p', null, 'body'),
      }),
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    const backdrop = screen.getByTestId('dialog-backdrop');
    expect(backdrop).toHaveAttribute('aria-label', 'Fechar');
  });
});

describe('DOM-freeze contract §3a — AlarmBar (severity bar)', () => {
  // Mirror AlarmBar.test.tsx harness: mock api/client + useRealtime, wrap in QueryClient.
  beforeEach(() => vi.clearAllMocks());

  it('keeps the summary landmark, per-priority bucket testids, and is-unacked toggle', async () => {
    vi.resetModules();
    vi.doMock('../api/client', () => ({
      apiGet: vi.fn().mockResolvedValue([
        {
          id: 1,
          controller_id: 7,
          controller_name: 'FIC-101',
          alarm_type: 'HI',
          priority: 'CRITICAL',
          value: 80,
          limit: 75,
          timestamp: '2026-06-18T10:00:00Z',
          cleared_at: null,
          acknowledged: 0,
          ack_by_user: null,
          ack_at: null,
          status: 'UNACKNOWLEDGED',
        },
      ]),
      apiPost: vi.fn().mockResolvedValue({}),
    }));
    vi.doMock('../realtime/useRealtime', () => ({
      useRealtime: () => ({
        connected: true,
        lastStatus: new Map(),
        lastStats: new Map(),
        subscribe: () => () => {},
        onResync: () => () => {},
      }),
    }));
    const { AlarmBar } = await import('../features/alarms/AlarmBar');

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(h(QueryClientProvider, { client: qc }, h(AlarmBar)));

    // landmark accessible name
    expect(screen.getByLabelText('Alarm summary')).toBeInTheDocument();
    // bucket testids exist
    expect(screen.getByTestId('count-critical')).toBeInTheDocument();
    expect(screen.getByTestId('count-warning')).toBeInTheDocument();
    expect(screen.getByTestId('count-advisory')).toBeInTheDocument();
    // is-unacked is set once the unacked critical alarm resolves
    const critical = await screen.findByTestId('count-critical');
    await vi.waitFor(() => expect(critical).toHaveClass('is-unacked'));
  });
});

describe('DOM-freeze contract §3a — Faceplate CO field', () => {
  // Mirror Faceplate.test.tsx harness: mock useRealtime/useCommands/useAiControls, wrap in QueryClient.
  beforeEach(() => vi.clearAllMocks());

  it('keeps Faceplate {tag} landmark and the Manual CO / Setpoint accessible names', async () => {
    vi.resetModules();
    const statusMap = new Map<number, unknown>();
    statusMap.set(5, {
      pv: { value: 150.2, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
      sp: { value: 152.0, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
      co: { value: 64.0, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
      bkcal_in: { value: 0, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
      bkcal_out: { value: 0, severity: 'GOOD', limit_bits: 'NONE', sub_status: 'NON_SPECIFIC' },
      mode: 'MAN',
      kp: 1,
      ti: 30,
      td: 0,
      integral_val: 0,
      timestamp: 0,
    });
    vi.doMock('../realtime/useRealtime', () => ({
      useRealtime: () => ({
        connected: true,
        lastStatus: statusMap,
        lastStats: new Map(),
        subscribe: () => () => {},
        onResync: () => () => {},
      }),
    }));
    vi.doMock('../features/loop-config/useCommands', () => ({
      useModeMutation: () => ({ mutate: vi.fn(), isPending: false }),
      useSetpointMutation: () => ({ mutate: vi.fn(), isPending: false }),
      useOutputMutation: () => ({ mutate: vi.fn(), isPending: false }),
    }));
    vi.doMock('../features/loop-config/useAiControls', () => ({
      useTuningRecommendation: () => ({ data: undefined }),
    }));
    const { Faceplate } = await import('../components/Faceplate');

    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      h(
        QueryClientProvider,
        { client },
        h(Faceplate, { controllerId: 5, tag: 'TIC-101', scale }),
      ),
    );

    expect(screen.getByLabelText('Faceplate TIC-101')).toBeInTheDocument();
    // MAN mode -> Manual CO field is present and enabled (the structural CO binding)
    expect(screen.getByLabelText('Manual CO')).toBeInTheDocument();
    expect(screen.getByLabelText('Setpoint')).toBeInTheDocument();
    expect(screen.getByLabelText('Set setpoint')).toBeInTheDocument();
    expect(screen.getByRole('complementary')).toBeInTheDocument();
  });
});
