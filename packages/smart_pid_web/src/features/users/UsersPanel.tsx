import { useState } from 'react';
import type { UserRow, UserUpdateBody } from '@/api/types';
import { useCan } from '@/auth/useCan';
import { Badge } from '@/components/Badge';
import { Button } from '@/components/Button';
import { EmptyState, ErrorState, LoadingState } from '@/components/MissingState';
import { cn } from '@/lib/utils';
import { UserDialog, type UserDraft } from './UserDialog';
import {
  useCreateUser,
  useDeactivateUser,
  useUpdateUser,
  userErrorMessage,
  useUsers,
} from './useUsers';

/**
 * Account roster (§9 `users.manage`, admin-only).
 *
 * The backend refuses to leave the deployment without an active administrator,
 * and that refusal is a 409 with a real reason — it is surfaced verbatim in the
 * operator's language instead of being flattened into a failed write, because
 * "you are the last admin" is actionable and "falhou" is not.
 */

const TH = 'border-b border-rule px-3 py-2 text-left text-2xs uppercase tracking-wider text-text-soft';
const TD = 'border-b border-rule px-3 py-2 align-middle';

/** `null` = closed, `'new'` = create, a row = edit that account. */
type DialogState = null | 'new' | UserRow;

export function UsersPanel() {
  const canManage = useCan('users.manage');
  const list = useUsers(canManage);
  const create = useCreateUser();
  const update = useUpdateUser();
  const deactivate = useDeactivateUser();
  const [dialog, setDialog] = useState<DialogState>(null);
  const [dialogFailure, setDialogFailure] = useState<string | null>(null);
  const [rosterFailure, setRosterFailure] = useState<string | null>(null);

  if (!canManage) {
    return (
      <p className="p-4 text-sm text-text-soft">
        Somente administradores podem gerenciar usuários.
      </p>
    );
  }
  if (list.isPending) return <LoadingState label="Carregando usuários…" />;
  if (list.isError) {
    return (
      <ErrorState
        message="Não foi possível carregar a lista de usuários."
        onRetry={() => void list.refetch()}
      />
    );
  }

  const users = list.data;
  const closeDialog = (): void => {
    setDialog(null);
    setDialogFailure(null);
  };

  const handleCreate = (draft: UserDraft): void => {
    setDialogFailure(null);
    create.mutate(
      { username: draft.username, password: draft.password, role: draft.role },
      {
        onSuccess: closeDialog,
        onError: (error) =>
          setDialogFailure(userErrorMessage(error, 'Não foi possível criar o usuário.')),
      },
    );
  };

  const handleUpdate = (userId: number, body: UserUpdateBody): void => {
    setDialogFailure(null);
    update.mutate(
      { userId, body },
      {
        onSuccess: closeDialog,
        onError: (error) =>
          setDialogFailure(userErrorMessage(error, 'Não foi possível salvar o usuário.')),
      },
    );
  };

  const toggleActive = (user: UserRow): void => {
    setRosterFailure(null);
    const onError = (error: Parameters<typeof userErrorMessage>[0]): void =>
      setRosterFailure(userErrorMessage(error, 'Não foi possível alterar a conta.'));
    if (user.active) {
      deactivate.mutate(user.id, { onError });
      return;
    }
    update.mutate({ userId: user.id, body: { active: true } }, { onError });
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button
          variant="primary"
          onClick={() => {
            setDialogFailure(null);
            setDialog('new');
          }}
        >
          Novo usuário
        </Button>
      </div>

      {users.length === 0 ? (
        <EmptyState message="Nenhum usuário cadastrado." hint="Crie a primeira conta." />
      ) : (
        <table className="w-full border-collapse border border-rule bg-surface text-sm text-text">
          <caption className="sr-only">Contas de acesso</caption>
          <thead>
            <tr>
              <th className={TH}>Usuário</th>
              <th className={TH}>Perfil</th>
              <th className={TH}>Situação</th>
              <th className={cn(TH, 'text-right')}>Ações</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td className={cn(TD, 'font-medium')}>{user.username}</td>
                <td className={TD}>{user.role}</td>
                <td className={TD}>
                  <Badge tone={user.active ? 'neutral' : 'warn'}>
                    {user.active ? 'Ativo' : 'Inativo'}
                  </Badge>
                </td>
                <td className={cn(TD, 'text-right')}>
                  <span className="flex justify-end gap-2">
                    <Button
                      size="sm"
                      onClick={() => {
                        setDialogFailure(null);
                        setDialog(user);
                      }}
                    >
                      Editar
                    </Button>
                    <Button
                      size="sm"
                      variant={user.active ? 'destructive' : 'secondary'}
                      onClick={() => toggleActive(user)}
                    >
                      {user.active ? 'Desativar' : 'Reativar'}
                    </Button>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {rosterFailure !== null ? (
        <p role="alert" className="text-xs font-medium text-alarm-crit">
          {rosterFailure}
        </p>
      ) : null}

      {dialog !== null ? (
        <UserDialog
          // Remount per target so the draft never leaks between accounts.
          key={dialog === 'new' ? 'new' : dialog.id}
          open
          editing={dialog === 'new' ? null : dialog}
          pending={create.isPending || update.isPending}
          failure={dialogFailure}
          onSubmitCreate={handleCreate}
          onSubmitUpdate={handleUpdate}
          onClose={closeDialog}
        />
      ) : null}
    </div>
  );
}
