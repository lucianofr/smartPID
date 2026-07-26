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
import type { ProjectListResponse, ProjectMeta } from '@/api/types';

/**
 * Portable `.spid` project management (routers/project.py).
 *
 * Every route below `/project` except `/current` is `require_admin`, so each
 * hook takes the caller's `projects.manage` verdict as its `enabled` gate — a
 * `user` session must never spend a request, or a retry storm, on a certain 403.
 *
 * All four mutations invalidate the same roster key: the backend list is the
 * single source of truth for size and loop count, and both change on import.
 */

export function useProjectList(enabled = true): UseQueryResult<ProjectListResponse, ApiError> {
  return useQuery<ProjectListResponse, ApiError>({
    queryKey: queryKeys.projects,
    enabled,
    queryFn: () => endpoints.projectList(),
  });
}

function useRosterMutation<TArg>(
  mutationFn: (arg: TArg) => Promise<ProjectMeta | void>,
): UseMutationResult<ProjectMeta | void, ApiError, TArg> {
  const queryClient = useQueryClient();
  return useMutation<ProjectMeta | void, ApiError, TArg>({
    mutationFn,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.projects });
    },
  });
}

export function useCreateProject(): UseMutationResult<ProjectMeta | void, ApiError, string> {
  return useRosterMutation((name: string) => endpoints.createProject(name));
}

export function useOpenProject(): UseMutationResult<ProjectMeta | void, ApiError, string> {
  return useRosterMutation((name: string) => endpoints.openProject(name));
}

export interface ImportArgs {
  file: File;
  name?: string;
}

export function useImportProject(): UseMutationResult<ProjectMeta | void, ApiError, ImportArgs> {
  return useRosterMutation(({ file, name }: ImportArgs) => endpoints.importProject(file, name));
}

export function useDeleteProject(): UseMutationResult<ProjectMeta | void, ApiError, string> {
  return useRosterMutation((name: string) => endpoints.deleteProject(name));
}

/**
 * §11 taxonomy → operator language. The backend raises exactly two 409s here
 * (`Project 'x' already exists` from new/import, `Cannot delete the active
 * project 'x'` from delete — project_service.py:106,141,169), so both get a
 * real pt-BR reason; an unforeseen conflict still echoes the server detail
 * rather than collapsing into "falhou".
 */
export function projectErrorMessage(error: ApiError, fallback: string): string {
  if (error.status === 413) return 'O arquivo excede o tamanho máximo aceito pelo servidor.';
  if (error.status === 400) return 'Arquivo .spid inválido.';
  if (error.kind === 'conflict') {
    if (/already exists/i.test(error.detail)) return 'Já existe um projeto com esse nome.';
    if (/active project/i.test(error.detail)) return 'Não é possível excluir o projeto ativo.';
    return error.detail;
  }
  if (error.kind === 'not-found') return 'Projeto não encontrado.';
  if (error.kind === 'forbidden') return 'Sua conta não pode gerenciar projetos.';
  if (error.kind === 'network') return 'Sem resposta do servidor.';
  return fallback;
}
