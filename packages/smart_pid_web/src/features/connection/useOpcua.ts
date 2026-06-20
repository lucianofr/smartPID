import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { opcuaApi } from './opcuaApi';

// Canonical key shared with the page shells (see api/executive.ts useOpcuaStatus).
// Mutations write here so the shell's opcDown banner stays in sync (single source of truth).
const OPCUA_STATUS_KEY = ['opcua-status'] as const;

export function useSaveEndpoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (endpoint: string) => opcuaApi.saveEndpoint(endpoint),
    onSuccess: (data) => qc.setQueryData(OPCUA_STATUS_KEY, data),
  });
}

export function useConnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (endpoint?: string) => opcuaApi.connect(endpoint),
    onSuccess: (data) => qc.setQueryData(OPCUA_STATUS_KEY, data),
  });
}

export function useDisconnect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => opcuaApi.disconnect(),
    onSuccess: (data) => qc.setQueryData(OPCUA_STATUS_KEY, data),
  });
}

export function useBrowse(nodeId: string | null) {
  return useQuery({
    queryKey: ['opcua', 'browse', nodeId],
    queryFn: () => opcuaApi.browse(nodeId as string),
    enabled: nodeId !== null,
  });
}

export function useSearch(q: string) {
  return useQuery({
    queryKey: ['opcua', 'search', q],
    queryFn: () => opcuaApi.search(q),
    enabled: q.trim().length > 0,
  });
}
