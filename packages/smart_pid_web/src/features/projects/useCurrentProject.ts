import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import type { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { queryKeys } from '@/api/queryKeys';
import type { ProjectMeta } from '@/api/types';

/**
 * The currently-open project. `/project/current` is the one route under
 * `/project` that is NOT `require_admin` (routers/project.py), so every session
 * may name its own plant — but the caller still gates on a resolved session, or
 * the shell spends a certain 401 on every cold load of the login route.
 */
export function useCurrentProject(enabled = true): UseQueryResult<ProjectMeta, ApiError> {
  return useQuery<ProjectMeta, ApiError>({
    queryKey: queryKeys.projectCurrent,
    enabled,
    queryFn: () => endpoints.projectCurrent(),
  });
}
