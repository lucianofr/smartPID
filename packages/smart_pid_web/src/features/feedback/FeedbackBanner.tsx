import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ApiError } from '@/api/client';
import { endpoints } from '@/api/endpoints';
import { useAuth } from '@/auth/AuthContext';
import { Button } from '@/components/Button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/Dialog';
import { toast } from '@/components/Toast';

/** Frozen copy — the banner's only text, asserted by both test suites. */
export const FEEDBACK_PROMPT = 'Envie uma mensagem ao desenvolvedor com ideias e sugestões.';

/**
 * The demo account is the one that gets asked for feedback, so the gate is the
 * username itself: there is no demo ROLE in the system (roles are admin/user),
 * and inventing one would put a permission concept in the schema to control a
 * banner. Exact, case-sensitive match against the account an admin creates.
 */
const DEMO_USERNAME = 'demo';

function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 429) return 'Aguarde um minuto antes de enviar outra mensagem.';
    if (err.status === 503) return 'O envio de email não está configurado no servidor.';
  }
  return 'Não foi possível enviar a mensagem. Tente novamente.';
}

/**
 * Page-level invitation for the demo operator to mail the developer.
 *
 * Renders nothing for every other account, so the Loops page is unchanged for
 * real operators. Not a `role="status"` live region: it is standing page
 * furniture, not an event, and announcing it on every mount would talk over
 * the alarm annunciations that DO need the screen reader.
 *
 * The typed message survives closing the dialog — only a successful send
 * clears it, so a 503 or a mis-click never costs the operator their text.
 */
export function FeedbackBanner() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const send = useMutation({ mutationFn: (m: string) => endpoints.sendFeedback(m) });

  if (user?.username !== DEMO_USERNAME) return null;

  const trimmed = message.trim();

  return (
    <>
      <div className="flex shrink-0 flex-wrap items-center justify-center gap-x-3 gap-y-1 border-b border-rule bg-surface px-3 py-2">
        <span className="text-sm text-text-soft">{FEEDBACK_PROMPT}</span>
        <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
          Enviar mensagem
        </Button>
      </div>
      <Dialog
        open={open}
        onOpenChange={(o) => {
          setOpen(o);
          if (!o) send.reset();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mensagem ao desenvolvedor</DialogTitle>
            <DialogDescription>
              Sua mensagem será enviada por email ao desenvolvedor do Smart PID.
            </DialogDescription>
          </DialogHeader>
          {/* No autoFocus prop: it is the first tabbable node in the content,
              so Radix's FocusScope lands on it when the dialog mounts. */}
          <textarea
            aria-label="Mensagem"
            rows={6}
            maxLength={2000}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            className="w-full rounded-control border border-rule-strong bg-surface-sunk px-2.5 py-2 text-base text-text placeholder:text-text-disabled outline-none transition-colors duration-fast focus-visible:ring-2 focus-visible:ring-focus-ring"
          />
          {send.isError ? (
            <p role="alert" className="text-sm font-medium text-alarm-crit">
              {errorMessage(send.error)}
            </p>
          ) : null}
          <DialogFooter>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button
              variant="primary"
              disabled={trimmed === '' || send.isPending}
              onClick={() =>
                send.mutate(trimmed, {
                  onSuccess: () => {
                    toast({ title: 'Mensagem enviada', description: 'Obrigado pelas sugestões!' });
                    setOpen(false);
                    setMessage('');
                  },
                })
              }
            >
              Enviar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
