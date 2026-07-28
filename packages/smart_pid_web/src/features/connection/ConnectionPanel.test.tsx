import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import type { Role } from '@/api/types';
import { createQueryClient, TestProviders } from '@/test/providers';
import { ConnectionPanel } from './ConnectionPanel';
import { TagBrowser } from './TagBrowser';

const FT_101 = { node_id: 'ns=2;s=FT-101', display_name: 'FT-101', node_class: 'Variable' };
const FOLDER = { node_id: 'ns=2;s=Plant', display_name: 'Plant', node_class: 'Object' };

function mockSession(role: Role) {
  sessionStorage.setItem('smart-pid-token', 'jwt');
  vi.spyOn(endpoints, 'me').mockResolvedValue({ user_id: 1, username: role, role });
}

function renderPanel(role: Role = 'admin', state: 'OFFLINE' | 'ONLINE' = 'OFFLINE') {
  mockSession(role);
  vi.spyOn(endpoints, 'opcuaStatus').mockResolvedValue({ state, endpoint: 'opc.tcp://x:4840' });
  return render(
    <TestProviders queryClient={createQueryClient()}>
      <ConnectionPanel />
    </TestProviders>,
  );
}

function renderBrowser(role: Role = 'admin') {
  mockSession(role);
  const onSelect = vi.fn();
  render(
    <TestProviders queryClient={createQueryClient()}>
      <TagBrowser onSelect={onSelect} />
    </TestProviders>,
  );
  return onSelect;
}

// jsdom reports every element as 0×0, so @tanstack/react-virtual windows the
// tag list down to nothing. Same fix the VirtualList primitive's own suite uses.
const offsetWidthDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');
const offsetHeightDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');

beforeEach(() => {
  sessionStorage.clear();
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 600 });
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 400 });
});

afterEach(() => {
  vi.restoreAllMocks();
  if (offsetWidthDesc) Object.defineProperty(HTMLElement.prototype, 'offsetWidth', offsetWidthDesc);
  if (offsetHeightDesc)
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', offsetHeightDesc);
});

describe('ConnectionPanel', () => {
  it('shows the live connection state and the stored endpoint', async () => {
    renderPanel('admin', 'ONLINE');
    expect(await screen.findByText('ONLINE')).toBeVisible();
    expect(screen.getByLabelText('Endpoint')).toHaveValue('opc.tcp://x:4840');
  });

  it('saves a changed endpoint before connecting, then reads the new state', async () => {
    renderPanel();
    expect(await screen.findByText('OFFLINE')).toBeVisible();
    const save = vi
      .spyOn(endpoints, 'saveOpcuaEndpoint')
      .mockResolvedValue({ state: 'OFFLINE', endpoint: 'opc.tcp://plc:4840' });
    const connect = vi
      .spyOn(endpoints, 'opcuaConnect')
      .mockResolvedValue({ state: 'ONLINE', endpoint: 'opc.tcp://plc:4840' });

    fireEvent.change(screen.getByLabelText('Endpoint'), {
      target: { value: 'opc.tcp://plc:4840' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Connect' }));

    await waitFor(() => expect(connect).toHaveBeenCalledWith('opc.tcp://plc:4840'));
    expect(save).toHaveBeenCalledWith('opc.tcp://plc:4840');
    expect(await screen.findByText('ONLINE')).toBeVisible();
  });

  it('does not re-save an unchanged endpoint', async () => {
    renderPanel();
    expect(await screen.findByText('OFFLINE')).toBeVisible();
    const save = vi.spyOn(endpoints, 'saveOpcuaEndpoint');
    vi.spyOn(endpoints, 'opcuaConnect').mockResolvedValue({
      state: 'ONLINE',
      endpoint: 'opc.tcp://x:4840',
    });

    fireEvent.click(screen.getByRole('button', { name: 'Connect' }));

    expect(await screen.findByText('ONLINE')).toBeVisible();
    expect(save).not.toHaveBeenCalled();
  });

  it('surfaces the 422 endpoint rule instead of a generic failure', async () => {
    renderPanel();
    expect(await screen.findByText('OFFLINE')).toBeVisible();
    vi.spyOn(endpoints, 'saveOpcuaEndpoint').mockRejectedValue(
      new ApiError(422, 'validation', 'Endpoint must start with opc.tcp://'),
    );

    fireEvent.change(screen.getByLabelText('Endpoint'), { target: { value: 'http://plc' } });
    fireEvent.click(screen.getByRole('button', { name: 'Connect' }));

    expect(await screen.findByText('O endpoint deve começar com opc.tcp://')).toBeVisible();
    // The rejected value stays in the field — the operator does not retype it.
    expect(screen.getByLabelText('Endpoint')).toHaveValue('http://plc');
  });

  it('Disconnect is unavailable while the session is not ONLINE', async () => {
    renderPanel();
    expect(await screen.findByText('OFFLINE')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Disconnect' })).toBeDisabled();
  });

  it('refuses the whole panel to a user — opcua.configure is admin-only', async () => {
    mockSession('user');
    const status = vi.spyOn(endpoints, 'opcuaStatus');
    render(
      <TestProviders queryClient={createQueryClient()}>
        <ConnectionPanel />
      </TestProviders>,
    );
    expect(
      await screen.findByText('Somente administradores podem configurar a conexão OPC-UA.'),
    ).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Connect' })).toBeNull();
    expect(status).not.toHaveBeenCalled();
  });
});

describe('TagBrowser', () => {
  it('browses the Objects folder when the search box is empty', async () => {
    const browse = vi
      .spyOn(endpoints, 'opcuaBrowse')
      .mockResolvedValue({ parent_node_id: 'i=85', children: [FOLDER, FT_101] });
    renderBrowser();

    expect(await screen.findByText('FT-101')).toBeVisible();
    expect(browse).toHaveBeenCalledWith('i=85');
    expect(screen.getByText('Plant')).toBeVisible();
  });

  it('searches the address space once the query settles', async () => {
    vi.spyOn(endpoints, 'opcuaBrowse').mockResolvedValue({
      parent_node_id: 'i=85',
      children: [FOLDER],
    });
    const search = vi
      .spyOn(endpoints, 'opcuaSearch')
      .mockResolvedValue({ query: 'MAIN.PV', results: [FT_101] });
    renderBrowser();
    await screen.findByText('Plant');

    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'MAIN.PV' } });

    expect(await screen.findByText('FT-101')).toBeVisible();
    expect(search).toHaveBeenCalledWith('MAIN.PV');
    expect(screen.queryByText('Plant')).toBeNull();
  });

  it('hands the selected node back to the caller', async () => {
    vi.spyOn(endpoints, 'opcuaBrowse').mockResolvedValue({
      parent_node_id: 'i=85',
      children: [FT_101],
    });
    const onSelect = renderBrowser();

    fireEvent.click(await screen.findByRole('button', { name: 'FT-101' }));

    expect(onSelect).toHaveBeenCalledWith(FT_101);
  });

  it('walks into a folder rather than reporting it as the selection', async () => {
    const browse = vi
      .spyOn(endpoints, 'opcuaBrowse')
      .mockImplementation((nodeId: string) =>
        Promise.resolve({
          parent_node_id: nodeId,
          children: nodeId === FOLDER.node_id ? [FT_101] : [FOLDER],
        }),
      );
    const onSelect = renderBrowser();

    fireEvent.click(await screen.findByRole('button', { name: 'Plant' }));

    expect(await screen.findByRole('button', { name: 'FT-101' })).toBeVisible();
    expect(browse).toHaveBeenCalledWith(FOLDER.node_id);
    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getByTestId('tag-browser-path')).toHaveTextContent('Objects › Plant');
  });

  it('Voltar climbs back to the parent level', async () => {
    vi.spyOn(endpoints, 'opcuaBrowse').mockImplementation((nodeId: string) =>
      Promise.resolve({
        parent_node_id: nodeId,
        children: nodeId === FOLDER.node_id ? [FT_101] : [FOLDER],
      }),
    );
    renderBrowser();

    const plant = await screen.findByRole('button', { name: 'Plant' });
    expect(screen.getByRole('button', { name: 'Voltar' })).toBeDisabled();

    fireEvent.click(plant);
    await screen.findByRole('button', { name: 'FT-101' });

    fireEvent.click(screen.getByRole('button', { name: 'Voltar' }));

    expect(await screen.findByRole('button', { name: 'Plant' })).toBeVisible();
    expect(screen.getByTestId('tag-browser-path')).toHaveTextContent('Objects');
    expect(screen.getByRole('button', { name: 'Voltar' })).toBeDisabled();
  });

  it('shows the NodeID beside the name only when the caller asks for it', async () => {
    vi.spyOn(endpoints, 'opcuaBrowse').mockResolvedValue({
      parent_node_id: 'i=85',
      children: [FT_101],
    });
    mockSession('admin');
    render(
      <TestProviders queryClient={createQueryClient()}>
        <TagBrowser showNodeId onSelect={vi.fn()} />
      </TestProviders>,
    );

    expect(
      await screen.findByRole('button', { name: `FT-101 ${FT_101.node_id}` }),
    ).toBeVisible();
  });

  it('reports a disconnected server instead of an empty tree', async () => {
    vi.spyOn(endpoints, 'opcuaBrowse').mockRejectedValue(
      new ApiError(503, 'server', 'OPC-UA client not connected'),
    );
    renderBrowser();

    expect(
      await screen.findByText('Não foi possível ler o espaço de endereços do servidor OPC-UA.'),
    ).toBeVisible();
  });

  it('never browses on behalf of a user role', async () => {
    const browse = vi.spyOn(endpoints, 'opcuaBrowse');
    renderBrowser('user');

    expect(
      await screen.findByText('Somente administradores podem navegar as tags OPC-UA.'),
    ).toBeVisible();
    expect(browse).not.toHaveBeenCalled();
  });
});
