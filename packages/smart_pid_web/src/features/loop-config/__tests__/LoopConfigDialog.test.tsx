import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { ControllerResponse, Role } from '@/api/types';
import { makeController } from '@/test/fixtures';
import { createQueryClient, TestProviders } from '@/test/providers';
import { DDC_SECTIONS, LoopConfigDialog } from '../LoopConfigDialog';

const fetchMock = vi.fn();

function renderDialog(
  overrides: Partial<ControllerResponse> = {},
  role: Role = 'admin',
  onClose = vi.fn(),
) {
  sessionStorage.setItem('smart-pid-token', 'jwt');
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

// jsdom reports every element as 0×0, so @tanstack/react-virtual windows the
// picker's tag list down to nothing. Same fix the VirtualList suite uses.
const offsetWidthDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');
const offsetHeightDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');

beforeEach(() => {
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
  it('pins the DDC-only section list', () => {
    expect(DDC_SECTIONS).toEqual([
      'PID Tuning',
      'Scaling & Limits',
      'Filters & IO',
      'Shed & Safety',
      'PID Structure',
      'Integral Type',
    ]);
  });

  it('hides every DCS-owned section while the loop is SUPERVISORY', async () => {
    renderDialog({ execution_mode: 'SUPERVISORY' });
    await screen.findByLabelText('Modo de execução');
    for (const name of DDC_SECTIONS) {
      expect(screen.queryByRole('region', { name })).not.toBeInTheDocument();
    }
  });

  it('reveals them all as soon as the loop is switched to DDC', async () => {
    renderDialog({ execution_mode: 'SUPERVISORY' });
    fireEvent.change(await screen.findByLabelText('Modo de execução'), {
      target: { value: 'DDC' },
    });
    for (const name of DDC_SECTIONS) {
      expect(screen.getByRole('region', { name })).toBeVisible();
    }
  });

  it('keeps identification, scan rate and the OPC-UA bindings in both modes', async () => {
    const view = renderDialog({ execution_mode: 'SUPERVISORY' });
    const always = ['Nome', 'Descrição', 'Taxa de varredura (s)', 'NodeID PV', 'NodeID SP', 'NodeID CO', 'NodeID Ti'];
    for (const label of always) expect(await screen.findByLabelText(label)).toBeInTheDocument();
    view.unmount();

    renderDialog({ execution_mode: 'DDC' });
    for (const label of always) expect(await screen.findByLabelText(label)).toBeInTheDocument();
  });
});

describe('LoopConfigDialog — writes', () => {
  it('PUTs the edited fields', async () => {
    const { onClose } = renderDialog({ execution_mode: 'DDC' });
    fireEvent.change(await screen.findByLabelText('Nome'), { target: { value: 'PIC-006' } });
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
    fireEvent.change(await screen.findByLabelText('Reset (Ti)'), { target: { value: '0' } });
    expect(await screen.findByText('Reset (Ti) deve ser maior que 0')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
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

const NODE_ID_LABELS = ['NodeID PV', 'NodeID SP', 'NodeID CO', 'NodeID Ti'] as const;

/** Distinct per field, so "only the target moved" is an assertion and not a coincidence. */
const SEEDED = {
  'NodeID PV': 'ns=2;i=900',
  'NodeID SP': 'ns=2;i=901',
  'NodeID CO': 'ns=2;i=902',
  'NodeID Ti': 'ns=2;i=903',
} as const;

function seededController(): Partial<ControllerResponse> {
  return {
    execution_mode: 'DDC',
    tag_bindings: {
      ...makeController().tag_bindings,
      node_id_pv: SEEDED['NodeID PV'],
      node_id_sp: SEEDED['NodeID SP'],
      node_id_co: SEEDED['NodeID CO'],
      node_id_ti: SEEDED['NodeID Ti'],
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
  fireEvent.click(await screen.findByRole('button', { name: `Procurar ${label}` }));
  return screen.findByRole('dialog', { name: `Selecionar tag para ${label}` });
}

describe('LoopConfigDialog — OPC-UA tag picker', () => {
  it('gives each NodeID field its own picker without touching the typed input', async () => {
    renderDialog(seededController());
    for (const label of NODE_ID_LABELS) {
      expect(await screen.findByRole('button', { name: `Procurar ${label}` })).toBeEnabled();
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
      node_id_ti: SEEDED['NodeID Ti'],
    });
  });

  it('still binds a hand-typed NodeID — E2E-009 never opens the picker', async () => {
    const { onClose } = renderDialog({ execution_mode: 'DDC' });

    fireEvent.change(await screen.findByLabelText('NodeID PV'), { target: { value: 'ns=2;i=5' } });
    fireEvent.change(screen.getByLabelText('NodeID Ti'), { target: { value: 'ns=2;i=11' } });
    expect(screen.getByLabelText('NodeID PV')).toHaveValue('ns=2;i=5');

    fireEvent.click(screen.getByRole('button', { name: 'Salvar' }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const body = JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string) as {
      tag_bindings: Record<string, string>;
    };
    expect(body.tag_bindings).toMatchObject({ node_id_pv: 'ns=2;i=5', node_id_ti: 'ns=2;i=11' });
  });

  it('offers no picker to a user — tag mapping is a write', async () => {
    renderDialog(seededController(), 'user');
    expect(await screen.findByLabelText('NodeID PV')).toBeDisabled();
    for (const label of NODE_ID_LABELS) {
      expect(screen.queryByRole('button', { name: `Procurar ${label}` })).toBeNull();
    }
  });
});

describe('LoopConfigDialog — AI Optimization section', () => {
  it('offers the three engines and the guardrail band', async () => {
    renderDialog();
    const engine = await screen.findByLabelText('Motor');
    expect(within(engine).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'NONE',
      'FUZZY',
      'RL',
    ]);
    expect(screen.getByLabelText('Tempo morto L')).toBeInTheDocument();
    expect(screen.getByLabelText('Limite mín.')).toBeInTheDocument();
    expect(screen.getByLabelText('Limite máx.')).toBeInTheDocument();
    expect(screen.getByLabelText('Velocidade do processo')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'AI Optimization' })).toBeVisible();
  });

  it('has no second save button of its own', async () => {
    renderDialog();
    await screen.findByLabelText('Motor');
    expect(screen.queryByRole('button', { name: 'Salvar IA' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Salvar' })).toHaveLength(1);
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
      },
    });
    fireEvent.change(await screen.findByLabelText('Limite mín.'), { target: { value: '500' } });
    expect(await screen.findByText('Limite mínimo deve ser menor que o máximo')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('disables the AI fields for a read-only user', async () => {
    renderDialog({}, 'user');
    expect(await screen.findByLabelText('Motor')).toBeDisabled();
    expect(screen.getByLabelText('Objetivo')).toBeDisabled();
    expect(screen.getByLabelText('Velocidade do processo')).toBeDisabled();
    expect(screen.getByLabelText('Tempo morto L')).toBeDisabled();
    expect(screen.getByLabelText('Limite mín.')).toBeDisabled();
    expect(screen.getByLabelText('Limite máx.')).toBeDisabled();
  });

  it('sends ai_config and process_speed in the single PATCH', async () => {
    const { onClose } = renderDialog();
    fireEvent.change(await screen.findByLabelText('Motor'), { target: { value: 'FUZZY' } });
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
    });
  });
});
