import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { OpcuaBrowseResponse, OpcuaSearchResponse, OpcuaStatus } from '@/api/types';

/**
 * OPC-UA session state and address-space reads (routers/opcua.py).
 *
 * `GET /opcua/status` is `require_user`; everything else on the router is
 * `require_admin`. Each hook therefore takes an `enabled` gate the caller wires
 * to `opcua.configure`, so a `user` session never spends a request — or a
 * retry storm — on a guaranteed 403.
 *
 * Every mutation writes `queryKeys.opcuaStatus` directly: the POST/PUT
 * responses ARE the new status, so the panel must not wait out the poll.
 */

/** The adapter reconnects in the background; 5 s keeps the readout honest. */
const STATUS_POLL_MS = 5_000;

/** OPC-UA `Objects` folder — the root of every browsable address space. */
export const ROOT_NODE_ID = 'i=85';

export function useOpcuaStatus(enabled = true): UseQueryResult<OpcuaStatus, ApiError> {
  return useQuery<OpcuaStatus, ApiError>({
    queryKey: queryKeys.opcuaStatus,
    enabled,
    queryFn: () => endpoints.opcuaStatus(),
    refetchInterval: STATUS_POLL_MS,
  });
}

function useStatusMutation<TArg>(
  mutationFn: (arg: TArg) => Promise<OpcuaStatus>,
): UseMutationResult<OpcuaStatus, ApiError, TArg> {
  const queryClient = useQueryClient();
  return useMutation<OpcuaStatus, ApiError, TArg>({
    mutationFn,
    onSuccess: (status) => {
      queryClient.setQueryData(queryKeys.opcuaStatus, status);
    },
  });
}

export function useSaveEndpoint(): UseMutationResult<OpcuaStatus, ApiError, string> {
  return useStatusMutation((endpoint: string) => endpoints.saveOpcuaEndpoint(endpoint));
}

export function useConnect(): UseMutationResult<OpcuaStatus, ApiError, string | undefined> {
  return useStatusMutation((endpoint: string | undefined) => endpoints.opcuaConnect(endpoint));
}

export function useDisconnect(): UseMutationResult<OpcuaStatus, ApiError, void> {
  return useStatusMutation(() => endpoints.opcuaDisconnect());
}

export function useBrowse(
  nodeId: string,
  enabled: boolean,
): UseQueryResult<OpcuaBrowseResponse, ApiError> {
  return useQuery<OpcuaBrowseResponse, ApiError>({
    queryKey: queryKeys.opcuaBrowse(nodeId),
    enabled,
    queryFn: () => endpoints.opcuaBrowse(nodeId),
  });
}

export function useTagSearch(
  query: string,
  enabled: boolean,
): UseQueryResult<OpcuaSearchResponse, ApiError> {
  return useQuery<OpcuaSearchResponse, ApiError>({
    // `q` is min_length=1 on the backend — an empty query is never sent.
    queryKey: queryKeys.opcuaSearch(query),
    enabled: enabled && query.length > 0,
    queryFn: () => endpoints.opcuaSearch(query),
  });
}
