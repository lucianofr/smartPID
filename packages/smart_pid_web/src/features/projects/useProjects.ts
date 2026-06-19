import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { projectApi } from './projectApi';

const LIST_KEY = ['projects', 'list'] as const;
const CURRENT_KEY = ['projects', 'current'] as const;

export function useProjectList() {
  return useQuery({ queryKey: LIST_KEY, queryFn: projectApi.list });
}

export function useCurrentProject() {
  return useQuery({ queryKey: CURRENT_KEY, queryFn: projectApi.current });
}

function invalidating(qc: ReturnType<typeof useQueryClient>) {
  return () => {
    void qc.invalidateQueries({ queryKey: LIST_KEY });
    void qc.invalidateQueries({ queryKey: CURRENT_KEY });
  };
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => projectApi.create(name),
    onSuccess: invalidating(qc),
  });
}

export function useOpenProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => projectApi.open(name),
    onSuccess: invalidating(qc),
  });
}

export function useImportProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, name }: { file: File; name?: string }) => projectApi.import(file, name),
    onSuccess: invalidating(qc),
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => projectApi.remove(name),
    onSuccess: invalidating(qc),
  });
}
