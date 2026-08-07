import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { ControllerResponse, Role } from '@/api/types';
import { makeController } from '@/test/fixtures';
import { createQueryClient, TestProviders } from '@/test/providers';
import { DDC_TABS, LoopConfigDialog } from '../LoopConfigDialog';

const fetchMock = vi.fn();

function renderDialog(
  overrides: Partial<ControllerResponse> = {},
  role: Role = 'admin',
  onClose = vi.fn(),
) {
  localStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
  const controller = makeController({ id: 5, name: 'PIC-005', description: 'Pressure', ...overrides });
  const queryClient = createQueryClient();
  queryClient.setQueryData(queryKeys.controllers, [controller]);
  return {
    onClose,
    controller,
    ...render(
      <TestProviders queryClient={queryClient}>
        <LoopConfigDialog controller={controller} open onClose={onClose} />
      </TestProviders>,
    ),
  };
}

/**
 * Radix Tabs runs in automatic activation mode and jsdom's `click` does not
 * move focus reliably (same workaround `Tabs.test.tsx` documents): activate
 * through the keyboard, which is the API a keyboard operator uses anyway.
 */
async function openTab(name: string): Promise<void> {
  const tab = await screen.findByRole('tab', { name });
  // `focus()` is a raw DOM call, so the Radix state update it triggers needs
  // its own act() — fireEvent alone would not cover it.
  await act(async () => {
    tab.focus();
    fireEvent.keyDown(tab, { key: 'Enter' });
  });
}

// jsdom reports every element as 0×0, so @tanstack/react-virtual windows the
// picker's tag list down to nothing. Same fix the VirtualList suite uses.
const offsetWidthDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');
const offsetHeightDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 600 });
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 400 });
  fetchMock.mockReset();
  fetchMock.mockResolvedValue(
    new Response(JSON.stringify({ id: 5 }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
  vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  if (offsetWidthDesc) Object.defineProperty(HTMLElement.prototype, 'offsetWidth', offsetWidthDesc);
  if (offsetHeightDesc)
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', offsetHeightDesc);
});

describe('LoopConfigDialog — execution mode gating', () => {
  it('pins the DDC-only tab list', () => {
    expect(DDC_TABS).toEqual(['Sintonia', 'Avançado']);
  });

  it('keeps Integral Type visible in SUPERVISORY — the optimizer needs it there', async () => {
    renderDialog({ execution_mode: 'SUPERVISORY' });
    await openTab('IA');
    expect(screen.getByRole('region', { name: 'Integral Type' })).toBeVisible();
  });

  it('hides every DCS-owned tab while the loop is SUPERVISORY', async () => {
    renderDialog({ execution_mode: 'SUPERVISORY' });
    await screen.findByLabelText('Modo de execução');
    for (const name of DDC_TABS) {
      expect(screen.queryByRole('tab', { name })).not.toBeInTheDocument();
    }
  });

  it('reveals them all as soon as the loop is switched to DDC', async () => {
    renderDialog({ execution_mode: 'SUPERVISORY' });
    fireEvent.change(await screen.findByLabelText('Modo de execução'), {
      target: { value: 'DDC' },
    });
    for (const name of DDC_TABS) {
      expect(screen.getByRole('tab', { name })).toBeVisible();
    }
  });

  it('keeps the Limites tab in SUPERVISORY — display scales are not DCS-owned', async () => {
    renderDialog({ execution_mode: 'SUPERVISORY' });
    await openTab('Limites');
    expect(screen.getByRole('region', { name: 'PV' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'CO' })).toBeVisible();
  });

  it('keeps identification, scan rate and the OPC-UA bindings in both modes', async () => {
    const identity = ['Nome', 'Descrição', 'Taxa de varredura (s)'];
    const bindings = [
      'NodeID PV', 'NodeID SP', 'NodeID CO',
      'NodeID Kp', 'NodeID Ki/Ti', 'NodeID Kd/Td',
    ];
    const view = renderDialog({ execution_mode: 'SUPERVISORY' });
    for (const label of identity) expect(await screen.findByLabelText(label)).toBeInTheDocument();
    await openTab('Tags');
    for (const label of bindings) expect(screen.getByLabelText(label)).toBeInTheDocument();
    view.unmount();

    renderDialog({ execution_mode: 'DDC' });
    for (const label of identity) expect(await screen.findByLabelText(label)).toBeInTheDocument();
    await openTab('Tags');
    for (const label of bindings) expect(screen.getByLabelText(label)).toBeInTheDocument();
  });
});

describe('LoopConfigDialog — writes', () => {
  it('PUTs the edited fields', async () => {
    const { onClose } = renderDialog({ execution_mode: 'DDC' });
    fireEvent.change(await screen.findByLabelText('Nome'), { target: { value: 'PIC-006' } });
    await openTab('Sintonia');
    fireEvent.change(screen.getByLabelText('Ganho (Kp)'), { target: { value: '2.5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/controllers/5');
    expect((init as RequestInit).method).toBe('PUT');
    const body = JSON.parse((init as RequestInit).body as string) as Record<string, unknown>;
    expect(body.name).toBe('PIC-006');
    expect(body.pid_params).toMatchObject({ gain: 2.5 });
  });

  it('refuses to save an invalid gain band and says why', async () => {
    renderDialog({ execution_mode: 'DDC' });
    await openTab('Sintonia');
    fireEvent.change(screen.getByLabelText('Reset (Ti)'), { target: { value: '0' } });
    expect(await screen.findByText('Reset (Ti) deve ser maior que 0')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('LoopConfigDialog — integral type (radio)', () => {
  it('renders both alternatives as radios, defaulting to the loop value', async () => {
    renderDialog({ execution_mode: 'SUPERVISORY', integral_type: 'TIME_TI' });
    await openTab('IA');
    const time = screen.getByRole('radio', { name: 'Tempo Integral (Ti)' });
    const gain = screen.getByRole('radio', { name: 'Ganho Integral (Ki)' });
    expect(time).toBeChecked();
    expect(gain).not.toBeChecked();
  });

  it('PUTs the picked type even for a SUPERVISORY loop', async () => {
    const { onClose } = renderDialog({
      execution_mode: 'SUPERVISORY',
      integral_type: 'TIME_TI',
    });
    await openTab('IA');
    fireEvent.click(screen.getByRole('radio', { name: 'Ganho Integral (Ki)' }));
    expect(screen.getByRole('radio', { name: 'Ganho Integral (Ki)' })).toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse((init as RequestInit).body as string) as Record<string, unknown>;
    expect(body.integral_type).toBe('GAIN_KI');
  });

  it('comes back checked on the saved value when the dialog is reopened', async () => {
    // What the server now returns for this loop after the PUT above.
    renderDialog({ execution_mode: 'SUPERVISORY', integral_type: 'GAIN_KI' });
    await openTab('IA');
    expect(screen.getByRole('radio', { name: 'Ganho Integral (Ki)' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'Tempo Integral (Ti)' })).not.toBeChecked();
  });
});

describe('LoopConfigDialog — optimizer stability band', () => {
  it('shows a blank box for a loop that inherits the global band', async () => {
    renderDialog({ stability_band_pct: null });
    await openTab('IA');
    expect(screen.getByLabelText('Banda de estabilidade (% do SP)')).toHaveValue(null);
  });

  it('round-trips a per-loop override', async () => {
    const { onClose } = renderDialog({ stability_band_pct: 0.5 });
    await openTab('IA');
    const field = screen.getByLabelText('Banda de estabilidade (% do SP)');
    expect(field).toHaveValue(0.5);

    fireEvent.change(field, { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());

    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse((init as RequestInit).body as string) as Record<string, unknown>;
    expect(body.stability_band_pct).toBe(5);
  });

  it('sends null when the box is cleared — that is "inherit the global"', async () => {
    const { onClose } = renderDialog({ stability_band_pct: 0.5 });
    await openTab('IA');
    fireEvent.change(screen.getByLabelText('Banda de estabilidade (% do SP)'), {
      target: { value: '' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());

    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse((init as RequestInit).body as string) as Record<string, unknown>;
    expect(body.stability_band_pct).toBeNull();
  });
});

describe('LoopConfigDialog — PID em uso binding', () => {
  it('offers the PLC process-running tag alongside the other bindings', async () => {
    renderDialog({ execution_mode: 'SUPERVISORY' });
    await openTab('Tags');
    const field = screen.getByLabelText('NodeID PID em uso');
    fireEvent.change(field, { target: { value: 'ns=2;s=Process_Running' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse((init as RequestInit).body as string) as Record<string, unknown>;
    expect(body.tag_bindings).toMatchObject({ node_id_enabled: 'ns=2;s=Process_Running' });
  });
});

describe('LoopConfigDialog — role gating', () => {
  it('gives the user role a read-only view with no write affordances', async () => {
    renderDialog({ execution_mode: 'DDC' }, 'user');
    expect(await screen.findByLabelText('Nome')).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Salvar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Excluir' })).not.toBeInTheDocument();
  });

  it('requires the tag to be typed back before it will delete', async () => {
    renderDialog();
    fireEvent.click(await screen.findByRole('button', { name: 'Excluir' }));

    const confirm = await screen.findByRole('alertdialog');
    const remove = within(confirm).getByRole('button', { name: 'Excluir definitivamente' });
    expect(remove).toBeDisabled();

    fireEvent.change(within(confirm).getByLabelText('Digite PIC-005 para confirmar'), {
      target: { value: 'PIC-00' },
    });
    expect(remove).toBeDisabled();

    fireEvent.change(within(confirm).getByLabelText('Digite PIC-005 para confirmar'), {
      target: { value: 'PIC-005' },
    });
    expect(remove).toBeEnabled();

    fireEvent.click(remove);
    await waitFor(() => {
      expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe('DELETE');
    });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/controllers/5');
  });
});

// ---- OPC-UA tag picker (§6.10, E2E-020) ----

const PID_FOLDER = { node_id: 'ns=2;i=4', display_name: 'PID', node_class: 'Object' };
const PV_NODE = { node_id: 'ns=2;i=5', display_name: 'PV', node_class: 'Variable' };
const CO_NODE = { node_id: 'ns=2;i=7', display_name: 'CO', node_class: 'Variable' };
/** A second loop's PV. The plant repeats display names — only the id separates them,
 *  and it is reachable ONLY through search, so clicking it proves the search path ran. */
const PV_HIT = { node_id: 'ns=2;i=25', display_name: 'PV', node_class: 'Variable' };

const NODE_ID_LABELS = [
  'NodeID PV',
  'NodeID SP',
  'NodeID CO',
  'NodeID Kp',
  'NodeID Ki/Ti',
  'NodeID Kd/Td',
] as const;

/** Distinct per field, so "only the target moved" is an assertion and not a coincidence. */
const SEEDED = {
  'NodeID PV': 'ns=2;i=900',
  'NodeID SP': 'ns=2;i=901',
  'NodeID CO': 'ns=2;i=902',
  'NodeID Kp': 'ns=2;i=903',
  'NodeID Ki/Ti': 'ns=2;i=904',
  'NodeID Kd/Td': 'ns=2;i=905',
} as const;

function seededController(): Partial<ControllerResponse> {
  return {
    execution_mode: 'DDC',
    tag_bindings: {
      ...makeController().tag_bindings,
      node_id_pv: SEEDED['NodeID PV'],
      node_id_sp: SEEDED['NodeID SP'],
      node_id_co: SEEDED['NodeID CO'],
      node_id_kp: SEEDED['NodeID Kp'],
      node_id_ti: SEEDED['NodeID Ki/Ti'],
      node_id_td: SEEDED['NodeID Kd/Td'],
    },
  };
}

function mockAddressSpace() {
  vi.spyOn(endpoints, 'opcuaBrowse').mockResolvedValue({
    parent_node_id: 'i=85',
    children: [PID_FOLDER, PV_NODE, CO_NODE],
  });
  vi.spyOn(endpoints, 'opcuaSearch').mockResolvedValue({ query: 'PV', results: [PV_HIT] });
}

/** Current value of every NodeID input, keyed by its label. */
function readBindings(): Record<string, string> {
  return Object.fromEntries(
    NODE_ID_LABELS.map((label) => [label, (screen.getByLabelText(label) as HTMLInputElement).value]),
  );
}

async function openPicker(label: string): Promise<HTMLElement> {
  await openTab('Tags');
  fireEvent.click(screen.getByRole('button', { name: `Procurar ${label}` }));
  return screen.findByRole('dialog', { name: `Selecionar tag para ${label}` });
}

describe('LoopConfigDialog — OPC-UA tag picker', () => {
  it('gives each NodeID field its own picker without touching the typed input', async () => {
    renderDialog(seededController());
    await openTab('Tags');
    for (const label of NODE_ID_LABELS) {
      expect(screen.getByRole('button', { name: `Procurar ${label}` })).toBeEnabled();
      expect(screen.getByLabelText(label)).not.toHaveAttribute('readonly');
    }
  });

  // The crux: a picker opened from CO must never write into PV. Run the same
  // selection from all four buttons — an implementation hard-wired to one
  // binding passes exactly one of these rows.
  it.each(NODE_ID_LABELS)('binds the chosen node to %s and leaves the rest alone', async (label) => {
    mockAddressSpace();
    renderDialog(seededController());

    const picker = await openPicker(label);
    fireEvent.click(await within(picker).findByRole('button', { name: `CO ${CO_NODE.node_id}` }));

    await waitFor(() => expect(screen.getByLabelText(label)).toHaveValue(CO_NODE.node_id));
    const after = readBindings();
    for (const other of NODE_ID_LABELS) {
      if (other !== label) expect(after[other]).toBe(SEEDED[other]);
    }
  });

  it('searches the address space and binds the hit (E2E-020)', async () => {
    mockAddressSpace();
    renderDialog(seededController());

    const picker = await openPicker('NodeID PV');
    fireEvent.change(within(picker).getByRole('searchbox'), { target: { value: 'PV' } });

    fireEvent.click(await within(picker).findByRole('button', { name: `PV ${PV_HIT.node_id}` }));

    await waitFor(() => expect(screen.getByLabelText('NodeID PV')).toHaveValue(PV_HIT.node_id));
    expect(endpoints.opcuaSearch).toHaveBeenCalledWith('PV');
  });

  it('walks into a folder instead of binding it', async () => {
    mockAddressSpace();
    renderDialog(seededController());

    const picker = await openPicker('NodeID SP');
    fireEvent.click(await within(picker).findByRole('button', { name: `PID ${PID_FOLDER.node_id}` }));

    await waitFor(() => expect(endpoints.opcuaBrowse).toHaveBeenCalledWith(PID_FOLDER.node_id));
    expect(screen.getByLabelText('NodeID SP')).toHaveValue(SEEDED['NodeID SP']);
    expect(picker).toBeVisible();
  });

  it('PUTs the picked NodeID', async () => {
    mockAddressSpace();
    const { onClose } = renderDialog(seededController());

    const picker = await openPicker('NodeID CO');
    fireEvent.click(await within(picker).findByRole('button', { name: `PV ${PV_NODE.node_id}` }));
    await waitFor(() => expect(screen.getByLabelText('NodeID CO')).toHaveValue(PV_NODE.node_id));

    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string) as {
      tag_bindings: Record<string, string>;
    };
    expect(body.tag_bindings).toMatchObject({
      node_id_co: PV_NODE.node_id,
      node_id_pv: SEEDED['NodeID PV'],
      node_id_sp: SEEDED['NodeID SP'],
      node_id_kp: SEEDED['NodeID Kp'],
      node_id_ti: SEEDED['NodeID Ki/Ti'],
      node_id_td: SEEDED['NodeID Kd/Td'],
    });
  });

  it('still binds a hand-typed NodeID — E2E-009 never opens the picker', async () => {
    const { onClose } = renderDialog({ execution_mode: 'DDC' });
    await openTab('Tags');

    fireEvent.change(screen.getByLabelText('NodeID PV'), { target: { value: 'ns=2;i=5' } });
    fireEvent.change(screen.getByLabelText('NodeID Kp'), { target: { value: 'ns=2;i=10' } });
    fireEvent.change(screen.getByLabelText('NodeID Ki/Ti'), { target: { value: 'ns=2;i=11' } });
    fireEvent.change(screen.getByLabelText('NodeID Kd/Td'), { target: { value: 'ns=2;i=12' } });
    expect(screen.getByLabelText('NodeID PV')).toHaveValue('ns=2;i=5');

    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string) as {
      tag_bindings: Record<string, string>;
    };
    expect(body.tag_bindings).toMatchObject({
      node_id_pv: 'ns=2;i=5',
      node_id_kp: 'ns=2;i=10',
      node_id_ti: 'ns=2;i=11',
      node_id_td: 'ns=2;i=12',
    });
  });

  it('offers no picker to a user — tag mapping is a write', async () => {
    renderDialog(seededController(), 'user');
    await openTab('Tags');
    expect(screen.getByLabelText('NodeID PV')).toBeDisabled();
    for (const label of NODE_ID_LABELS) {
      expect(screen.queryByRole('button', { name: `Procurar ${label}` })).toBeNull();
    }
  });
});

describe('LoopConfigDialog — AI Optimization section', () => {
  it('offers the three engines and the guardrail band', async () => {
    renderDialog();
    await openTab('IA');
    const engine = screen.getByLabelText('Motor');
    expect(within(engine).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'NONE',
      'FUZZY',
      'RL',
    ]);
    expect(screen.getByLabelText('Tempo morto L')).toBeInTheDocument();
    expect(screen.getByLabelText('Ti mínimo')).toBeInTheDocument();
    expect(screen.getByLabelText('Ti máximo')).toBeInTheDocument();
    expect(screen.getByLabelText('Velocidade do processo')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'AI Optimization' })).toBeVisible();
  });

  it('has no second save button of its own', async () => {
    renderDialog();
    await openTab('IA');
    screen.getByLabelText('Motor');
    expect(screen.queryByRole('button', { name: 'Salvar IA' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Salvar' })).toHaveLength(1);
  });

  it('explains the process-speed classes in a tooltip', async () => {
    renderDialog();
    await openTab('IA');
    const trigger = screen.getByRole('button', {
      name: 'Mais informações sobre Velocidade do processo',
    });
    fireEvent.focus(trigger);
    const tip = await screen.findByRole('tooltip');
    for (const speed of ['ULTRA_FAST', 'FAST', 'MEDIUM', 'SLOW']) {
      expect(tip).toHaveTextContent(speed);
    }
  });

  it('hides the surge band knobs for the other objectives', async () => {
    renderDialog();
    await openTab('IA');
    expect(screen.queryByLabelText('Nível mín. (%)')).toBeNull();
    expect(screen.queryByLabelText('Rampa máx. do CO (%/min)')).toBeNull();
  });

  it('offers the surge band knobs once SURGE_LEVEL is selected', async () => {
    renderDialog();
    await openTab('IA');
    fireEvent.change(screen.getByLabelText('Objetivo'), {
      target: { value: 'SURGE_LEVEL' },
    });
    expect(await screen.findByLabelText('Nível mín. (%)')).toBeInTheDocument();
    expect(screen.getByLabelText('Nível máx. (%)')).toBeInTheDocument();
    expect(screen.getByLabelText('Erro pequeno (% da faixa)')).toBeInTheDocument();
    expect(screen.getByLabelText('Rampa máx. do CO (%/min)')).toBeInTheDocument();
  });

  it('refuses to save an inverted surge band', async () => {
    renderDialog();
    await openTab('IA');
    // The guardrails are inert while the engine is off, so turn it on first.
    fireEvent.change(screen.getByLabelText('Motor'), {
      target: { value: 'FUZZY' },
    });
    fireEvent.change(screen.getByLabelText('Objetivo'), {
      target: { value: 'SURGE_LEVEL' },
    });
    fireEvent.change(await screen.findByLabelText('Nível mín. (%)'), {
      target: { value: '80' },
    });
    fireEvent.change(screen.getByLabelText('Nível máx. (%)'), {
      target: { value: '20' },
    });
    expect(
      await screen.findByText('Limite inferior deve ser menor que o superior'),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled();
  });

  it('refuses to save an inverted guardrail band', async () => {
    renderDialog({
      ai_config: {
        dead_time_l: 1,
        engine: 'FUZZY',
        limit_max: 100,
        limit_min: 0.1,
        objective: 'DISTURBANCE_REJECTION',
        rl_fallback_kd: 0.2,
        rl_fallback_kp: 0.6,
        rl_learning_rate: 0.0003,
        rl_train_interval: 32,
        sl_co_ramp_max_pct_min: 10,
        sl_error_small_pct: 5,
      },
    });
    await openTab('IA');
    fireEvent.change(screen.getByLabelText('Ti mínimo'), { target: { value: '500' } });
    expect(await screen.findByText('Limite mínimo deve ser menor que o máximo')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('disables the AI fields for a read-only user', async () => {
    renderDialog({}, 'user');
    await openTab('IA');
    expect(screen.getByLabelText('Motor')).toBeDisabled();
    expect(screen.getByLabelText('Objetivo')).toBeDisabled();
    expect(screen.getByLabelText('Velocidade do processo')).toBeDisabled();
    expect(screen.getByLabelText('Tempo morto L')).toBeDisabled();
    expect(screen.getByLabelText('Ti mínimo')).toBeDisabled();
    expect(screen.getByLabelText('Ti máximo')).toBeDisabled();
  });

  // The same limit_min/limit_max pair clamps Ki for a GAIN_KI loop and Ti for
  // a TIME_TI one, so the label must follow the radio or the operator clamps
  // the wrong quantity.
  it('labels the integral limits after the loop integral type', async () => {
    renderDialog({ integral_type: 'GAIN_KI' });
    await openTab('IA');
    expect(screen.getByLabelText('Ki mínimo')).toBeInTheDocument();
    expect(screen.getByLabelText('Ki máximo')).toBeInTheDocument();
    expect(screen.queryByLabelText('Ti mínimo')).toBeNull();
  });

  it('flips the integral limit labels when the integral type radio changes', async () => {
    renderDialog({ integral_type: 'TIME_TI' });
    await openTab('IA');
    fireEvent.click(screen.getByRole('radio', { name: 'Ganho Integral (Ki)' }));
    expect(screen.getByLabelText('Ki mínimo')).toBeInTheDocument();
    expect(screen.queryByLabelText('Ti máximo')).toBeNull();
  });

  it('defaults the integral limits to 1 and 10 for a loop with no ai_config', async () => {
    renderDialog({ ai_config: undefined });
    await openTab('IA');
    expect(screen.getByLabelText('Ti mínimo')).toHaveValue(1);
    expect(screen.getByLabelText('Ti máximo')).toHaveValue(10);
  });

  it('sends ai_config and process_speed in the single PATCH', async () => {
    const { onClose } = renderDialog();
    await openTab('IA');
    fireEvent.change(screen.getByLabelText('Motor'), { target: { value: 'FUZZY' } });
    fireEvent.change(screen.getByLabelText('Objetivo'), { target: { value: 'SP_TRACKING' } });
    fireEvent.change(screen.getByLabelText('Velocidade do processo'), { target: { value: 'FAST' } });
    fireEvent.change(screen.getByLabelText('Tempo morto L'), { target: { value: '4' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(fetchMock.mock.calls).toHaveLength(1);
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string) as {
      process_speed: string;
      ai_config: Record<string, unknown>;
    };
    expect(body.process_speed).toBe('FAST');
    expect(body.ai_config).toEqual({
      engine: 'FUZZY',
      objective: 'SP_TRACKING',
      dead_time_l: 4,
      limit_min: 0.1,
      limit_max: 100,
      // Surge Level knobs ride along unchanged for every objective: the
      // dialog sends one whole ai_config, and the engine only reads them
      // when the objective is SURGE_LEVEL.
      sl_band_lo_pct: null,
      sl_band_hi_pct: null,
      sl_error_small_pct: 5,
      sl_co_ramp_max_pct_min: 10,
    });
  });
});

const ALL_MODES = ['OOS', 'IMAN', 'LO', 'MAN', 'AUTO', 'CAS', 'RCAS', 'ROUT', 'BYPASS'] as const;

describe('LoopConfigDialog — mode tag and numeric mapping (§6.10)', () => {
  it('offers read and write NodeID fields for the block mode', async () => {
    renderDialog();
    await openTab('Tags');
    expect(screen.getByLabelText('NodeID Modo (leitura)')).toBeInTheDocument();
    expect(screen.getByLabelText('NodeID Modo (escrita)')).toBeInTheDocument();
  });

  it('offers an integer mapping field for every controller mode', async () => {
    renderDialog();
    await openTab('Tags');
    for (const mode of ALL_MODES) {
      expect(screen.getByLabelText(mode)).toBeInTheDocument();
    }
  });

  it('loads existing mode bindings and mapping into their fields', async () => {
    renderDialog({
      tag_bindings: {
        ...makeController().tag_bindings,
        node_id_mode_actual: 'ns=2;i=8',
        node_id_mode_target: 'ns=2;i=9',
        mode_int_map: { MAN: 0, AUTO: 1 },
      },
    });
    await openTab('Tags');
    expect(screen.getByLabelText('NodeID Modo (leitura)')).toHaveValue('ns=2;i=8');
    expect(screen.getByLabelText('NodeID Modo (escrita)')).toHaveValue('ns=2;i=9');
    expect(screen.getByLabelText('MAN')).toHaveValue(0);
    expect(screen.getByLabelText('AUTO')).toHaveValue(1);
    expect(screen.getByLabelText('CAS')).toHaveValue(null);
  });

  it('saves typed mode bindings and mapping, omitting blank modes', async () => {
    const { onClose } = renderDialog();
    await openTab('Tags');
    fireEvent.change(screen.getByLabelText('NodeID Modo (leitura)'), {
      target: { value: 'ns=2;i=8' },
    });
    fireEvent.change(screen.getByLabelText('NodeID Modo (escrita)'), {
      target: { value: 'ns=2;i=8' },
    });
    fireEvent.change(screen.getByLabelText('MAN'), { target: { value: '0' } });
    fireEvent.change(screen.getByLabelText('AUTO'), { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string) as {
      tag_bindings: {
        node_id_mode_actual: string;
        node_id_mode_target: string;
        mode_int_map: Record<string, number>;
      };
    };
    expect(body.tag_bindings.node_id_mode_actual).toBe('ns=2;i=8');
    expect(body.tag_bindings.node_id_mode_target).toBe('ns=2;i=8');
    expect(body.tag_bindings.mode_int_map).toEqual({ MAN: 0, AUTO: 1 });
  });

  it('keeps a typed 0 in the map instead of treating it as unset', async () => {
    const { onClose } = renderDialog();
    await openTab('Tags');
    fireEvent.change(screen.getByLabelText('MAN'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string) as {
      tag_bindings: { mode_int_map: Record<string, number> };
    };
    expect(body.tag_bindings.mode_int_map).toEqual({ MAN: 0 });
  });

  it('shows a tooltip describing the field on focus of its info icon', async () => {
    renderDialog();
    await openTab('Tags');
    const trigger = screen.getByRole('button', { name: 'Mais informações sobre AUTO' });
    fireEvent.focus(trigger);
    expect(await screen.findByRole('tooltip')).toHaveTextContent('AUTO');
  });

  it('disables the mode NodeID and mapping fields for a read-only user', async () => {
    renderDialog({}, 'user');
    await openTab('Tags');
    expect(screen.getByLabelText('NodeID Modo (leitura)')).toBeDisabled();
    expect(screen.getByLabelText('MAN')).toBeDisabled();
  });
});

describe('LoopConfigDialog — Limites (EU e faixas)', () => {
  it('fills every range and coerces a legacy blank unit to %', async () => {
    renderDialog({
      execution_mode: 'SUPERVISORY',
      pv_scale: { eu_min: 0, eu_max: 100, unit: '' },
      out_scale: { eu_min: 0, eu_max: 100, unit: '' },
    });
    await openTab('Limites');
    expect(screen.getByLabelText('PV mín.')).toHaveValue(0);
    expect(screen.getByLabelText('PV máx.')).toHaveValue(100);
    expect(screen.getByLabelText('Unidade PV')).toHaveValue('%');
    expect(screen.getByLabelText('SP mín.')).toHaveValue(0);
    expect(screen.getByLabelText('SP máx.')).toHaveValue(100);
    expect(screen.getByLabelText('CO mín.')).toHaveValue(0);
    expect(screen.getByLabelText('CO máx.')).toHaveValue(100);
    expect(screen.getByLabelText('Unidade CO')).toHaveValue('%');
  });

  // SP has no unit of its own on the wire: it rides the PV scale. Showing a
  // free box here would let the operator save a unit the SP never uses.
  it('mirrors the PV unit into a permanently read-only SP unit', async () => {
    renderDialog({ execution_mode: 'SUPERVISORY' });
    await openTab('Limites');
    const spUnit = screen.getByLabelText('Unidade SP');
    expect(spUnit).toBeDisabled();

    fireEvent.change(screen.getByLabelText('Unidade PV'), { target: { value: 'bar' } });
    expect(spUnit).toHaveValue('bar');
    expect(spUnit).toBeDisabled();
  });

  it('persists the CO scale and the SP band for a SUPERVISORY loop', async () => {
    const { onClose } = renderDialog({ execution_mode: 'SUPERVISORY' });
    await openTab('Limites');
    fireEvent.change(screen.getByLabelText('CO máx.'), { target: { value: '60' } });
    fireEvent.change(screen.getByLabelText('Unidade CO'), { target: { value: 'kPa' } });
    fireEvent.change(screen.getByLabelText('SP máx.'), { target: { value: '80' } });
    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string) as Record<
      string,
      unknown
    >;
    expect(body.out_scale).toEqual({ eu_min: 0, eu_max: 60, unit: 'kPa' });
    expect(body.pv_scale).toEqual({ eu_min: 0, eu_max: 100, unit: '%' });
    expect(body.sp_hi_lim).toBe(80);
    expect(body.sp_lo_lim).toBe(0);
    // Tuning stays DCS-owned in SUPERVISORY — lifting the scales out of the
    // DDC gate must not drag the PID payload with them.
    expect(body.pid_params).toBeUndefined();
    expect(body.out_hi_lim).toBeUndefined();
  });

  it('blocks the save on an inverted PV range until it is fixed', async () => {
    renderDialog({ execution_mode: 'SUPERVISORY' });
    await openTab('Limites');
    fireEvent.change(screen.getByLabelText('PV mín.'), { target: { value: '150' } });

    expect(
      await screen.findByText('Limite inferior da PV deve ser menor que o superior'),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText('PV mín.'), { target: { value: '50' } });
    expect(screen.getByRole('button', { name: 'Salvar' })).toBeEnabled();
  });
});
