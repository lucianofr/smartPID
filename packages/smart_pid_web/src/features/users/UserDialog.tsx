import { useState } from 'react';
import type { Role, UserRow, UserUpdateBody } from '@/api/types';
import { Button } from '@/components/Button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/Dialog';
import { Field, Input } from '@/components/Field';
import { cn } from '@/lib/utils';

/**
 * Create / edit one account.
 *
 * The username is immutable after creation — `UserUpdate` carries no username
 * field — and an empty password on edit means "keep the current one", so the
 * PATCH body only ever contains what the administrator actually changed.
 */

const SELECT_CLASS = cn(
  'min-h-11 w-full rounded-control border border-rule-strong bg-surface-sunk px-3 text-sm text-text',
  'outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
);

const ROLES: readonly Role[] = ['admin', 'user'];

export interface UserDraft {
  username: string;
  password: string;
  role: Role;
}

export interface UserDialogProps {
  open: boolean;
  /** `null` = create a new account; a row = edit that account. */
  editing: UserRow | null;
  pending: boolean;
  /** Rejection from the last submit, already translated. */
  failure: string | null;
  onSubmitCreate: (draft: UserDraft) => void;
  onSubmitUpdate: (userId: number, body: UserUpdateBody) => void;
  onClose: () => void;
}

export interface UserDraftIssues {
  username?: string;
  password?: string;
}

export function validateNewUser(draft: UserDraft): UserDraftIssues {
  const issues: UserDraftIssues = {};
  if (draft.username.trim() === '') issues.username = 'Informe um nome de usuário.';
  if (draft.password === '') issues.password = 'Informe uma senha.';
  return issues;
}

/** Only the fields that actually changed — an empty PATCH body is never sent. */
export function toUpdateBody(editing: UserRow, draft: UserDraft): UserUpdateBody {
  const body: UserUpdateBody = {};
  if (draft.role !== editing.role) body.role = draft.role;
  if (draft.password !== '') body.password = draft.password;
  return body;
}

export function UserDialog({
  open,
  editing,
  pending,
  failure,
  onSubmitCreate,
  onSubmitUpdate,
  onClose,
}: UserDialogProps) {
  const creating = editing === null;
  const [draft, setDraft] = useState<UserDraft>(() => ({
    username: editing?.username ?? '',
    password: '',
    role: editing?.role ?? 'user',
  }));
  const [issues, setIssues] = useState<UserDraftIssues>({});

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent aria-label={creating ? 'Novo usuário' : `Editar ${editing.username}`}>
        <DialogHeader>
          <DialogTitle>{creating ? 'Novo usuário' : `Editar ${editing.username}`}</DialogTitle>
          <DialogDescription>
            {creating
              ? 'Contas novas começam ativas e podem ser desativadas depois.'
              : 'Deixe a senha em branco para mantê-la.'}
          </DialogDescription>
        </DialogHeader>

        <form
          className="flex flex-col gap-3"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            if (creating) {
              const found = validateNewUser(draft);
              setIssues(found);
              if (found.username !== undefined || found.password !== undefined) return;
              onSubmitCreate({ ...draft, username: draft.username.trim() });
              return;
            }
            const body = toUpdateBody(editing, draft);
            if (Object.keys(body).length === 0) {
              onClose();
              return;
            }
            onSubmitUpdate(editing.id, body);
          }}
        >
          {/* `required` rides the control, not Field's `*`: the visual marker is
              part of the label's text content, and these labels are the names
              the account tests and the operator both bind to. */}
          <Field label="Usuário" htmlFor="user-username" error={issues.username}>
            <Input
              id="user-username"
              type="text"
              required={creating}
              autoComplete="off"
              // UserUpdate has no username field; renaming is not a backend operation.
              disabled={!creating}
              invalid={issues.username !== undefined}
              aria-describedby={issues.username !== undefined ? 'user-username-err' : undefined}
              value={draft.username}
              onChange={(e) => setDraft((d) => ({ ...d, username: e.target.value }))}
            />
          </Field>

          <Field
            label={creating ? 'Senha' : 'Nova senha'}
            htmlFor="user-password"
            error={issues.password}
          >
            <Input
              id="user-password"
              type="password"
              required={creating}
              autoComplete="new-password"
              invalid={issues.password !== undefined}
              aria-describedby={issues.password !== undefined ? 'user-password-err' : undefined}
              value={draft.password}
              onChange={(e) => setDraft((d) => ({ ...d, password: e.target.value }))}
            />
          </Field>

          <Field label="Perfil" htmlFor="user-role">
            <select
              id="user-role"
              className={SELECT_CLASS}
              value={draft.role}
              onChange={(e) => setDraft((d) => ({ ...d, role: e.target.value as Role }))}
            >
              {ROLES.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
          </Field>

          {failure !== null ? (
            <p role="alert" className="text-xs font-medium text-alarm-crit">
              {failure}
            </p>
          ) : null}

          <DialogFooter>
            <Button variant="ghost" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" variant="primary" disabled={pending}>
              Salvar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
