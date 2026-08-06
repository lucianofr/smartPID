import { useState } from 'react';
import { useCan } from '@/auth/useCan';
import { Button } from '@/components/Button';
import { Checkbox } from '@/components/Checkbox';
import { Field, Input } from '@/components/Field';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/Select';
import { Switch } from '@/components/Switch';
import { useTheme, type ThemeId } from '@/theme/ThemeProvider';
import type { LogLevelName } from '@/api/types';
import {
  DECIMALS_MAX,
  DECIMALS_MIN,
  DEFAULT_PREFERENCES,
  TREND_WINDOW_MAX_S,
  TREND_WINDOW_MIN_S,
  type AppPreferences,
} from './settingsTypes';
import { useLogLevels } from './useLogLevels';
import { useSettings } from './useSettings';

/** stdlib level names, severity-ordered — the skeleton rendered while the query loads. */
const ALL_LOG_LEVELS: readonly LogLevelName[] = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];

const LOG_LEVEL_HINTS: Readonly<Record<LogLevelName, string>> = {
  DEBUG: 'Detalhes internos de depuração (volume muito alto)',
  INFO: 'Eventos normais de operação (alto volume)',
  WARNING: 'Situações anômalas que não interrompem a operação',
  ERROR: 'Falhas que afetam a operação',
  CRITICAL: 'Falhas graves que exigem ação imediata',
};

/**
 * Application preferences (§9 `settings.manage`, admin-only).
 *
 * Explicit save, not save-on-keystroke: the numeric fields are validated as a
 * set and a rejected draft KEEPS what the operator typed, so a typo never
 * silently persists and never has to be retyped.
 */

interface Draft {
  trendWindowSeconds: string;
  numberDecimals: string;
  confirmDestructive: boolean;
}

export interface PreferenceIssues {
  trendWindowSeconds?: string;
  numberDecimals?: string;
}

function toDraft(preferences: AppPreferences): Draft {
  return {
    trendWindowSeconds: String(preferences.trendWindowSeconds),
    numberDecimals: String(preferences.numberDecimals),
    confirmDestructive: preferences.confirmDestructive,
  };
}

function integerIn(raw: string, min: number, max: number): number | null {
  const value = Number(raw);
  if (raw.trim() === '' || !Number.isInteger(value) || value < min || value > max) return null;
  return value;
}

export function validatePreferences(draft: Draft): PreferenceIssues {
  const issues: PreferenceIssues = {};
  if (integerIn(draft.numberDecimals, DECIMALS_MIN, DECIMALS_MAX) === null) {
    issues.numberDecimals = `Use um inteiro entre ${DECIMALS_MIN} e ${DECIMALS_MAX}.`;
  }
  if (integerIn(draft.trendWindowSeconds, TREND_WINDOW_MIN_S, TREND_WINDOW_MAX_S) === null) {
    issues.trendWindowSeconds = `Use um valor entre ${TREND_WINDOW_MIN_S} e ${TREND_WINDOW_MAX_S} segundos.`;
  }
  return issues;
}

export function SettingsForm() {
  const canManage = useCan('settings.manage');
  const { preferences, save, reset } = useSettings();
  const [draft, setDraft] = useState<Draft>(() => toDraft(preferences));
  const [issues, setIssues] = useState<PreferenceIssues>({});
  const [saved, setSaved] = useState(false);
  const { theme, setTheme, themes } = useTheme();
  const logLevels = useLogLevels();
  const [levelsDraft, setLevelsDraft] = useState<LogLevelName[] | null>(null);

  if (!canManage) {
    return (
      <p className="p-4 text-sm text-text-soft">
        Somente administradores podem alterar as configurações.
      </p>
    );
  }

  const patch = (next: Partial<Draft>): void => {
    setSaved(false);
    setDraft((current) => ({ ...current, ...next }));
  };

  return (
    <form
      aria-label="Configurações"
      className="flex max-w-xl flex-col gap-5 p-3"
      // The pt-BR field messages below are the contract; native bubbles would
      // both duplicate them and abort submit before validatePreferences runs.
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        const found = validatePreferences(draft);
        setIssues(found);
        if (found.numberDecimals !== undefined || found.trendWindowSeconds !== undefined) return;
        save({
          trendWindowSeconds: Number(draft.trendWindowSeconds),
          numberDecimals: Number(draft.numberDecimals),
          confirmDestructive: draft.confirmDestructive,
        });
        setSaved(true);
      }}
    >
      <fieldset className="flex flex-col gap-3 border border-rule p-3">
        <legend className="px-1 text-xs font-semibold uppercase tracking-wider text-text">
          Aparência
        </legend>
        <Field
          label="Tema"
          htmlFor="pref-theme"
          description="O tema é aplicado imediatamente e salvo na sua conta."
        >
          <Select value={theme} onValueChange={(next) => setTheme(next as ThemeId)}>
            <SelectTrigger id="pref-theme" aria-describedby="pref-theme-desc">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {themes.map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </fieldset>

      <fieldset className="flex flex-col gap-3 border border-rule p-3">
        <legend className="px-1 text-xs font-semibold uppercase tracking-wider text-text">
          Exibição
        </legend>
        <Field
          label="Casas decimais"
          htmlFor="pref-decimals"
          description="Casas decimais dos valores de processo."
          error={issues.numberDecimals}
        >
          <Input
            id="pref-decimals"
            type="number"
            className="numeric"
            min={DECIMALS_MIN}
            max={DECIMALS_MAX}
            invalid={issues.numberDecimals !== undefined}
            aria-describedby={
              issues.numberDecimals !== undefined ? 'pref-decimals-err' : 'pref-decimals-desc'
            }
            value={draft.numberDecimals}
            onChange={(e) => patch({ numberDecimals: e.target.value })}
          />
        </Field>
        <Field
          label="Janela de tendência (s)"
          htmlFor="pref-trend-window"
          description="Janela padrão dos gráficos de tendência."
          error={issues.trendWindowSeconds}
        >
          <Input
            id="pref-trend-window"
            type="number"
            className="numeric"
            min={TREND_WINDOW_MIN_S}
            max={TREND_WINDOW_MAX_S}
            invalid={issues.trendWindowSeconds !== undefined}
            aria-describedby={
              issues.trendWindowSeconds !== undefined
                ? 'pref-trend-window-err'
                : 'pref-trend-window-desc'
            }
            value={draft.trendWindowSeconds}
            onChange={(e) => patch({ trendWindowSeconds: e.target.value })}
          />
        </Field>
      </fieldset>

      <fieldset className="flex flex-col gap-3 border border-rule p-3">
        <legend className="px-1 text-xs font-semibold uppercase tracking-wider text-text">
          Operação
        </legend>
        {/* Radix Switch is a `role="switch"` button carrying its own accessible
            name — a wrapping <label> would name nothing. */}
        <span className="flex items-center gap-2 text-sm text-text">
          <Switch
            aria-label="Confirmar ações destrutivas"
            checked={draft.confirmDestructive}
            onCheckedChange={(confirmDestructive) => patch({ confirmDestructive })}
          />
          Confirmar ações destrutivas
        </span>
      </fieldset>

      <fieldset className="flex flex-col gap-3 border border-rule p-3">
        <legend className="px-1 text-xs font-semibold uppercase tracking-wider text-text">
          Registro de log
        </legend>
        {logLevels.isError ? (
          <p className="text-xs text-alarm-crit">
            Não foi possível carregar os níveis de log.
          </p>
        ) : (
          <>
            <div className="flex flex-col gap-2">
              {(logLevels.data?.available ?? ALL_LOG_LEVELS).map((level) => {
                const activeLevels = levelsDraft ?? logLevels.data?.levels ?? [];
                const checked = activeLevels.includes(level);
                return (
                  <span key={level} className="flex items-center gap-2 text-sm text-text">
                    <Checkbox
                      aria-label={`${level} — ${LOG_LEVEL_HINTS[level]}`}
                      disabled={logLevels.isLoading}
                      checked={checked}
                      onCheckedChange={() =>
                        setLevelsDraft(
                          checked
                            ? activeLevels.filter((l) => l !== level)
                            : [...activeLevels, level],
                        )
                      }
                    />
                    <span>
                      <span className="font-medium">{level}</span>
                      {' — '}
                      <span className="text-text-soft">{LOG_LEVEL_HINTS[level]}</span>
                    </span>
                  </span>
                );
              })}
            </div>
            <p className="text-xs text-text-soft">
              Desativar WARNING e ERROR oculta falhas reais do sistema.
            </p>
            <Button
              type="button"
              variant="primary"
              disabled={logLevels.isLoading || logLevels.isSaving}
              onClick={() => {
                const toSave = levelsDraft ?? logLevels.data?.levels ?? [];
                logLevels.save(toSave);
                setLevelsDraft(toSave);
              }}
            >
              Aplicar níveis
            </Button>
          </>
        )}
      </fieldset>

      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary">
          Salvar
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            reset();
            setDraft(toDraft(DEFAULT_PREFERENCES));
            setIssues({});
            setSaved(false);
          }}
        >
          Restaurar padrões
        </Button>
        {saved ? (
          <p role="status" className="text-xs text-text-soft">
            Configurações salvas.
          </p>
        ) : null}
      </div>
    </form>
  );
}
