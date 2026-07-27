import { useId } from 'react';
import { Field, Input } from '@/components/Field';
import { cn } from '@/lib/utils';
import {
  AI_ENGINES,
  OBJECTIVES,
  PROCESS_SPEEDS,
  type AiEngine,
  type ControlObjective,
  type FieldErrors,
  type ProcessSpeed,
} from './types';

/**
 * The optimizer's configuration surface (§5). It lives in the loop config
 * dialog rather than the faceplate: configuration belongs where configuration
 * already is, and the 417 px it used to occupy is what made the rail scroll.
 *
 * Presentational on purpose — the dialog owns the draft, the validation and the
 * single PATCH, so there is exactly one save button for one write.
 */

export interface AiSectionForm {
  engine: AiEngine;
  objective: ControlObjective;
  speed: ProcessSpeed;
  dead_time_l: number;
  limit_min: number;
  limit_max: number;
}

export interface AiConfigSectionProps {
  value: AiSectionForm;
  errors: FieldErrors;
  disabled: boolean;
  onChange(patch: Partial<AiSectionForm>): void;
}

const SELECT_CLASS = cn(
  'numeric min-h-11 w-full rounded-control border border-rule-strong bg-surface-sunk px-3 py-2',
  'text-sm text-text outline-none focus-visible:ring-2 focus-visible:ring-focus-ring',
  'disabled:cursor-not-allowed disabled:text-text-disabled',
);

export function AiConfigSection({ value, errors, disabled, onChange }: AiConfigSectionProps) {
  const engineId = useId();
  const objectiveId = useId();
  const speedId = useId();
  const deadTimeId = useId();
  const limitMinId = useId();
  const limitMaxId = useId();

  return (
    <>
      <Field label="Motor" htmlFor={engineId}>
        <select
          id={engineId}
          className={SELECT_CLASS}
          value={value.engine}
          disabled={disabled}
          onChange={(e) => onChange({ engine: e.target.value as AiEngine })}
        >
          {AI_ENGINES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Objetivo" htmlFor={objectiveId}>
        <select
          id={objectiveId}
          className={SELECT_CLASS}
          value={value.objective}
          disabled={disabled}
          onChange={(e) => onChange({ objective: e.target.value as ControlObjective })}
        >
          {OBJECTIVES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Velocidade do processo" htmlFor={speedId}>
        <select
          id={speedId}
          className={SELECT_CLASS}
          value={value.speed}
          disabled={disabled}
          onChange={(e) => onChange({ speed: e.target.value as ProcessSpeed })}
        >
          {PROCESS_SPEEDS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Tempo morto L" htmlFor={deadTimeId} error={errors.dead_time_l}>
        <Input
          id={deadTimeId}
          type="number"
          inputMode="decimal"
          className="numeric"
          value={value.dead_time_l}
          disabled={disabled}
          invalid={errors.dead_time_l !== undefined}
          onChange={(e) => onChange({ dead_time_l: Number(e.target.value) })}
        />
      </Field>

      <Field label="Limite mín." htmlFor={limitMinId} error={errors.limit_min}>
        <Input
          id={limitMinId}
          type="number"
          inputMode="decimal"
          className="numeric"
          value={value.limit_min}
          disabled={disabled}
          invalid={errors.limit_min !== undefined}
          onChange={(e) => onChange({ limit_min: Number(e.target.value) })}
        />
      </Field>

      <Field label="Limite máx." htmlFor={limitMaxId} error={errors.limit_max}>
        <Input
          id={limitMaxId}
          type="number"
          inputMode="decimal"
          className="numeric"
          value={value.limit_max}
          disabled={disabled}
          invalid={errors.limit_max !== undefined}
          onChange={(e) => onChange({ limit_max: Number(e.target.value) })}
        />
      </Field>
    </>
  );
}
