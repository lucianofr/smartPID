import { useEffect, useMemo, useState } from 'react';
import { useCan } from '@/auth/useCan';
import { Button } from '@/components/Button';
import { Field, Input } from '@/components/Field';
import { ErrorState, LoadingState } from '@/components/MissingState';
import { Switch } from '@/components/Switch';
import { cn } from '@/lib/utils';
import { ALARM_SEVERITIES } from './severity';
import { useAlarmConfig, useUpdateAlarmConfig } from './useAlarmConfig';
import {
  ALARM_TYPES,
  ORDERED_LIMIT_TYPES,
  type AlarmSeverity,
  type AlarmThreshold,
  type AlarmType,
} from './types';

/**
 * Per-loop alarm limits (§9: `alarms.configure` is admin-only).
 *
 * Two invariants this form exists to hold:
 *  1. The PUT REPLACES the whole threshold array, so every one of the six
 *     types round-trips even when the operator only touched HIHI.
 *  2. Enabled analog limits must stay ordered LOLO < LO < HI < HIHI. A
 *     disabled limit leaves the chain instead of blocking its neighbours.
 */

export interface ThresholdIssues {
  limit?: string;
  deadband?: string;
}

export type ConfigErrors = Partial<Record<AlarmType, ThresholdIssues>>;

interface ThresholdDraft {
  alarm_type: AlarmType;
  priority: AlarmSeverity;
  /** Kept as typed text: parsing on every keystroke would fight the operator. */
  limit: string;
  deadband: string;
  enabled: boolean;
  delay_on_s: number;
  delay_off_s: number;
}

const SELECT_CLASS = cn(
  'min-h-11 w-full rounded-control border border-rule-strong bg-surface-sunk px-2 text-sm text-text',
  'outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
);

function blank(alarmType: AlarmType): ThresholdDraft {
  return {
    alarm_type: alarmType,
    priority: 'WARNING',
    limit: '0',
    deadband: '0',
    enabled: false,
    delay_on_s: 0,
    delay_off_s: 0,
  };
}

function toDraft(thresholds: readonly AlarmThreshold[]): ThresholdDraft[] {
  const byType = new Map(thresholds.map((t) => [t.alarm_type, t]));
  return ALARM_TYPES.map((alarmType) => {
    const found = byType.get(alarmType);
    if (!found) return blank(alarmType);
    return {
      alarm_type: alarmType,
      priority: found.priority,
      limit: String(found.limit),
      deadband: String(found.deadband),
      enabled: found.enabled,
      delay_on_s: found.delay_on_s,
      delay_off_s: found.delay_off_s,
    };
  });
}

function toThresholds(draft: readonly ThresholdDraft[]): AlarmThreshold[] {
  return draft.map((row) => ({
    alarm_type: row.alarm_type,
    priority: row.priority,
    limit: Number(row.limit),
    deadband: Number(row.deadband),
    enabled: row.enabled,
    delay_on_s: row.delay_on_s,
    delay_off_s: row.delay_off_s,
  }));
}

export function validateThresholds(draft: readonly ThresholdDraft[]): ConfigErrors {
  const errors: ConfigErrors = {};
  const issue = (type: AlarmType, patch: ThresholdIssues): void => {
    errors[type] = { ...errors[type], ...patch };
  };

  for (const row of draft) {
    if (!Number.isFinite(Number(row.limit)) || row.limit.trim() === '') {
      issue(row.alarm_type, { limit: 'Informe um número' });
    }
    const deadband = Number(row.deadband);
    if (!Number.isFinite(deadband) || row.deadband.trim() === '') {
      issue(row.alarm_type, { deadband: 'Informe um número' });
    } else if (deadband < 0) {
      issue(row.alarm_type, { deadband: 'A banda morta não pode ser negativa' });
    }
  }

  // Deviation limits are relative to setpoint and carry no ordering rule.
  const chain = ORDERED_LIMIT_TYPES.map((type) =>
    draft.find((row) => row.alarm_type === type),
  ).filter((row): row is ThresholdDraft => row !== undefined && row.enabled);

  for (let i = 0; i < chain.length - 1; i += 1) {
    const higher = chain[i];
    const lower = chain[i + 1];
    if (Number(higher.limit) <= Number(lower.limit)) {
      issue(higher.alarm_type, {
        limit: `${higher.alarm_type} deve ser maior que ${lower.alarm_type}`,
      });
    }
  }
  return errors;
}

/** FastAPI 422 `loc` is `['body','thresholds',<index>,'<field>']` — index into the sent array. */
export function mapServerErrors(
  fields: readonly { loc: (string | number)[]; msg: string }[],
): ConfigErrors {
  const errors: ConfigErrors = {};
  for (const field of fields) {
    const index = field.loc.find((part): part is number => typeof part === 'number');
    const key = field.loc[field.loc.length - 1];
    const alarmType = index === undefined ? undefined : ALARM_TYPES[index];
    if (alarmType === undefined) continue;
    if (key === 'deadband') errors[alarmType] = { ...errors[alarmType], deadband: field.msg };
    else errors[alarmType] = { ...errors[alarmType], limit: field.msg };
  }
  return errors;
}

export interface AlarmConfigFormProps {
  controllerId: number;
}

export function AlarmConfigForm({ controllerId }: AlarmConfigFormProps) {
  const canConfigure = useCan('alarms.configure');
  const config = useAlarmConfig(controllerId, canConfigure);
  const update = useUpdateAlarmConfig(controllerId);
  const [draft, setDraft] = useState<ThresholdDraft[]>([]);
  const [serverErrors, setServerErrors] = useState<ConfigErrors>({});

  const loaded = config.data;
  useEffect(() => {
    if (loaded) setDraft(toDraft(loaded.thresholds));
  }, [loaded]);

  const errors = useMemo(() => validateThresholds(draft), [draft]);
  const invalid = Object.values(errors).some(
    (issues) => issues.limit !== undefined || issues.deadband !== undefined,
  );

  if (!canConfigure) {
    return (
      <p className="p-4 text-sm text-text-soft">
        Somente administradores podem configurar alarmes.
      </p>
    );
  }
  if (config.isPending) return <LoadingState label="Carregando configuração de alarmes…" />;
  if (config.isError) {
    return (
      <ErrorState
        message="Não foi possível carregar a configuração de alarmes."
        onRetry={() => void config.refetch()}
      />
    );
  }

  const patch = (alarmType: AlarmType, next: Partial<ThresholdDraft>): void => {
    setServerErrors({});
    setDraft((current) =>
      current.map((row) => (row.alarm_type === alarmType ? { ...row, ...next } : row)),
    );
  };

  const issuesFor = (alarmType: AlarmType): ThresholdIssues => ({
    ...serverErrors[alarmType],
    ...errors[alarmType],
  });

  return (
    <form
      aria-label="Configuração de alarmes"
      className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (invalid) return;
        setServerErrors({});
        update.mutate(toThresholds(draft), {
          onError: (error) => setServerErrors(mapServerErrors(error.fields)),
        });
      }}
    >
      {draft.map((row) => {
        const issues = issuesFor(row.alarm_type);
        return (
          <fieldset
            key={row.alarm_type}
            data-testid={`threshold-${row.alarm_type}`}
            className="grid grid-cols-[8rem_1fr_1fr_1fr] items-start gap-3 border border-rule p-3"
          >
            <legend className="px-1 text-xs font-semibold uppercase tracking-wider text-text">
              {row.alarm_type}
            </legend>
            {/* Radix Switch is a `role="switch"` button: it carries its own
                accessible name, so a wrapping <label> would name nothing. */}
            <span className="flex items-center gap-2 self-center text-xs text-text-soft">
              <Switch
                aria-label={`${row.alarm_type} ativo`}
                checked={row.enabled}
                onCheckedChange={(enabled) => patch(row.alarm_type, { enabled })}
              />
              Ativo
            </span>
            <Field label={row.alarm_type} htmlFor={`alarm-${row.alarm_type}-limit`} error={issues.limit}>
              <Input
                id={`alarm-${row.alarm_type}-limit`}
                type="number"
                step="any"
                className="numeric"
                invalid={issues.limit !== undefined}
                aria-describedby={issues.limit ? `alarm-${row.alarm_type}-limit-err` : undefined}
                value={row.limit}
                onChange={(e) => patch(row.alarm_type, { limit: e.target.value })}
              />
            </Field>
            <Field
              label={`Banda morta ${row.alarm_type}`}
              htmlFor={`alarm-${row.alarm_type}-deadband`}
              error={issues.deadband}
            >
              <Input
                id={`alarm-${row.alarm_type}-deadband`}
                type="number"
                step="any"
                className="numeric"
                invalid={issues.deadband !== undefined}
                aria-describedby={
                  issues.deadband ? `alarm-${row.alarm_type}-deadband-err` : undefined
                }
                value={row.deadband}
                onChange={(e) => patch(row.alarm_type, { deadband: e.target.value })}
              />
            </Field>
            <Field
              label={`Prioridade ${row.alarm_type}`}
              htmlFor={`alarm-${row.alarm_type}-priority`}
            >
              <select
                id={`alarm-${row.alarm_type}-priority`}
                className={SELECT_CLASS}
                value={row.priority}
                onChange={(e) =>
                  patch(row.alarm_type, { priority: e.target.value as AlarmSeverity })
                }
              >
                {ALARM_SEVERITIES.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </Field>
          </fieldset>
        );
      })}

      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary" disabled={invalid || update.isPending}>
          Salvar
        </Button>
        {update.isSuccess ? (
          <p role="status" className="text-xs text-text-soft">
            Configuração salva.
          </p>
        ) : null}
        {update.isError && update.error.kind !== 'validation' ? (
          <p role="alert" className="text-xs font-medium text-alarm-crit">
            Não foi possível salvar a configuração.
          </p>
        ) : null}
      </div>
    </form>
  );
}
