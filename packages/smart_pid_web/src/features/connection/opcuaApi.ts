import { apiGet, apiPost, apiPut } from '../../api/client';
import type { OpcuaStatus } from '../../api/executive';

export interface OpcuaNode {
  node_id: string;
  display_name: string;
  node_class: string;
}

export const opcuaApi = {
  getStatus: (): Promise<OpcuaStatus> => apiGet('/opcua/status'),
  saveEndpoint: (endpoint: string): Promise<OpcuaStatus> => apiPut('/opcua/endpoint', { endpoint }),
  connect: (endpoint?: string): Promise<OpcuaStatus> =>
    apiPost('/opcua/connect', endpoint ? { endpoint } : undefined),
  disconnect: (): Promise<OpcuaStatus> => apiPost('/opcua/disconnect'),
  browse: (nodeId: string): Promise<{ parent_node_id: string; children: OpcuaNode[] }> =>
    apiGet(`/opcua/browse/${encodeURIComponent(nodeId)}`),
  search: (q: string): Promise<{ query: string; results: OpcuaNode[] }> =>
    apiGet(`/opcua/search?q=${encodeURIComponent(q)}`),
};
