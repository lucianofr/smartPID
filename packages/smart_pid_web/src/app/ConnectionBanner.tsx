import { formatTimestamp } from '@/lib/format';
import { useConnectionStatus, type ConnectionStatus } from '@/realtime/useConnectionStatus';
import { cn } from '@/lib/utils';

type Tone = 'crit' | 'warn' | 'adv';

interface BannerState {
  tone: Tone;
  /** Short state word, uppercase — the thing an operator reads at a glance. */
  title: string;
  /** One sentence saying what that means for the numbers on screen. */
  detail: string;
}

/** Advisory/warning/critical strips, from the §6.4 severity tokens. No raw colour. */
const TONE_CLASS: Record<Tone, string> = {
  crit: 'border-alarm-crit bg-alarm-crit-bg',
  warn: 'border-alarm-warn bg-alarm-warn-bg',
  adv: 'border-alarm-adv bg-alarm-adv-bg',
};
const TONE_TEXT: Record<Tone, string> = {
  crit: 'text-alarm-crit',
  warn: 'text-alarm-warn',
  adv: 'text-alarm-adv',
};

/**
 * Abnormal-link states, worst first. `null` = there is nothing an operator
 * needs to be told.
 *
 * Two rules earn their place here:
 *  - `stale` outranks `live`. A socket reporting itself open is not evidence
 *    that anything is arriving through it (E2E-047), and the operator's
 *    question is only ever "is this number current?".
 *  - Everything except a LOST link is gated on `stale`. A §8 resync fires on
 *    any seq gap and normally finishes in well under a second; a full-width
 *    strip that flashes for 300 ms is how an operator learns to tune the
 *    banner out, and a banner that gets tuned out is worse than none.
 */
export function connectionBannerState(status: ConnectionStatus): BannerState | null {
  const { phase, stale, staleSince } = status;
  if (phase === 'auth-failed') {
    return {
      tone: 'crit',
      title: 'SESSÃO EXPIRADA',
      detail: 'entre novamente — os valores exibidos não são atuais',
    };
  }
  // `idle` is excluded: no session has been established yet, so the page is
  // showing em dashes, not frozen numbers. `connecting` means the link was
  // HAD and lost — see ConnectionPhase.
  if (phase === 'connecting') {
    return {
      tone: 'crit',
      title: 'SEM CONEXÃO',
      detail: stale
        ? `tentando reconectar — última leitura às ${formatTimestamp(staleSince === null ? null : staleSince / 1000)}, os valores exibidos NÃO são atuais`
        : 'tentando reconectar — os valores exibidos NÃO são atuais',
    };
  }
  if (!stale) return null;
  const lastReading = formatTimestamp(staleSince === null ? null : staleSince / 1000);
  if (phase === 'resyncing') {
    return {
      tone: 'adv',
      title: 'RESSINCRONIZANDO',
      detail: `recuperando o estado da planta — última leitura às ${lastReading}`,
    };
  }
  return {
    tone: 'warn',
    title: 'DADOS DESATUALIZADOS',
    detail: `nenhuma leitura desde ${lastReading} — os valores exibidos NÃO são atuais`,
  };
}

/**
 * Persistent connection state for the whole shell (E2E-047).
 *
 * An industrial HMI may never let a frozen number pass for a live one. The
 * realtime provider already knew when the link was down; nothing rendered it,
 * so a killed backend left four cards showing plausible pre-outage PV with no
 * cue whatsoever. This is that cue.
 *
 * `role="status"` + `aria-live="assertive"` is the same pairing the alarm bar
 * and alarm panel use for conditions that must interrupt. The announced text is
 * stable for the whole episode — the timestamp is the last reading, not a
 * ticking age — so the region speaks once per state change instead of once a
 * second.
 */
export function ConnectionBanner() {
  const status = useConnectionStatus();
  const state = connectionBannerState(status);
  if (state === null) return null;

  return (
    <div
      role="status"
      aria-live="assertive"
      aria-label="Estado da conexão"
      data-testid="connection-banner"
      data-tone={state.tone}
      className={cn(
        'flex shrink-0 flex-wrap items-baseline justify-center gap-x-2 border-b px-3 py-2 text-center',
        TONE_CLASS[state.tone],
      )}
    >
      <span className={cn('text-xs font-semibold uppercase tracking-widest', TONE_TEXT[state.tone])}>
        {state.title}
      </span>
      <span className="text-xs text-text-soft">{state.detail}</span>
    </div>
  );
}
