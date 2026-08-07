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
import type { UserCreateBody, UserRow, UserUpdateBody } from '@/api/types';

/**
 * Account management (routers/users.py — `require_admin` on every route).
 *
 * Deactivation is SOFT: `DELETE /users/{id}` flips `active` and returns the
 * updated row, so the roster keeps the account and reactivation is a plain
 * `PATCH {active: true}` rather than a re-create.
 */

export function useUsers(enabled = true): UseQueryResult<UserRow[], ApiError> {
  return useQuery<UserRow[], ApiError>({
    queryKey: queryKeys.users,
    enabled,
    queryFn: () => endpoints.users(),
  });
}

function useRosterMutation<TArg>(
  mutationFn: (arg: TArg) => Promise<UserRow>,
): UseMutationResult<UserRow, ApiError, TArg> {
  const queryClient = useQueryClient();
  return useMutation<UserRow, ApiError, TArg>({
    mutationFn,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.users });
    },
  });
}

export function useCreateUser(): UseMutationResult<UserRow, ApiError, UserCreateBody> {
  return useRosterMutation((body: UserCreateBody) => endpoints.createUser(body));
}

export interface UserPatch {
  userId: number;
  body: UserUpdateBody;
}

export function useUpdateUser(): UseMutationResult<UserRow, ApiError, UserPatch> {
  return useRosterMutation(({ userId, body }: UserPatch) => endpoints.updateUser(userId, body));
}

export function useDeactivateUser(): UseMutationResult<UserRow, ApiError, number> {
  return useRosterMutation((userId: number) => endpoints.deactivateUser(userId));
}

/**
 * The users router raises exactly two 409s (users.py
 * _reject_if_last_active_admin and create_user) and they mean very
 * different things to the administrator, so neither may collapse into "falhou".
 */
export function userErrorMessage(error: ApiError, fallback: string): string {
  if (error.kind === 'conflict') {
    if (/last active admin/i.test(error.detail)) {
      return 'Não é possível desativar o último administrador.';
    }
    if (/already exists/i.test(error.detail)) return 'Nome de usuário já existe.';
    return error.detail;
  }
  if (error.kind === 'not-found') return 'Usuário não encontrado.';
  if (error.kind === 'forbidden') return 'Sua conta não pode gerenciar usuários.';
  if (error.kind === 'validation') return error.detail;
  if (error.kind === 'network') return 'Sem resposta do servidor.';
  return fallback;
}
