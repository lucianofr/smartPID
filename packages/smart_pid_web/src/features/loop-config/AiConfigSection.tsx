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
  type IntegralType,
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
  integral_type: IntegralType;
  dead_time_l: number;
  limit_min: number;
  limit_max: number;
  sl_band_lo_pct: number | null;
  sl_band_hi_pct: number | null;
  sl_error_small_pct: number;
  sl_co_ramp_max_pct_min: number;
}

export interface AiConfigSectionProps {
  value: AiSectionForm;
  errors: FieldErrors;
  disabled: boolean;
  /** `integral_type` is display-only here — the dialog owns that radio. */
  onChange(patch: Partial<Omit<AiSectionForm, 'integral_type'>>): void;
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
  const bandLoId = useId();
  const bandHiId = useId();
  const errorSmallId = useId();
  const coRampId = useId();

  // One pair of limits clamps whichever integral parameter the loop uses
  // (ai_worker clamps Ki for GAIN_KI, Ti for TIME_TI), so the label has to
  // follow `integral_type`: a box labelled Ti holding a Ki bound is how an
  // operator ends up clamping the wrong quantity.
  const integralParam = value.integral_type === 'GAIN_KI' ? 'Ki' : 'Ti';

  return (
    <>
      <Field
        label="Motor"
        htmlFor={engineId}
        tooltip="Motor de otimização usado para ajustar a sintonia desta malha: NONE (desativado), FUZZY (lógica fuzzy) ou RL (aprendizado por reforço)."
      >
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

      <Field
        label="Objetivo"
        htmlFor={objectiveId}
        tooltip="Objetivo de controle que a IA prioriza ao propor ajustes de sintonia."
      >
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

      <Field
        label="Velocidade do processo"
        htmlFor={speedId}
        tooltip="Classificação da dinâmica do processo, usada pela IA para calibrar a agressividade dos ajustes de sintonia."
      >
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

      <Field
        label="Tempo morto L"
        htmlFor={deadTimeId}
        error={errors.dead_time_l}
        tooltip="Tempo morto estimado do processo, em segundos — usado pela IA para calcular limites seguros de sintonia."
      >
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

      <Field
        label={`${integralParam} mínimo`}
        htmlFor={limitMinId}
        error={errors.limit_min}
        tooltip={`Menor ${integralParam} que a IA pode propor para esta malha. Toda sugestão de sintonia é limitada a esta faixa.`}
      >
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

      <Field
        label={`${integralParam} máximo`}
        htmlFor={limitMaxId}
        error={errors.limit_max}
        tooltip={`Maior ${integralParam} que a IA pode propor para esta malha. Toda sugestão de sintonia é limitada a esta faixa.`}
      >
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

      {/* Surge Level is the only objective that reasons about a PV band, so
          its knobs stay hidden for the other two rather than sitting inert. */}
      {value.objective === 'SURGE_LEVEL' && (
        <>
          <Field
            label="Nível mín. (%)"
            htmlFor={bandLoId}
            error={errors.sl_band_lo_pct}
            tooltip="Nível mínimo da faixa segura de PV, em % da faixa de medição. Em branco usa o padrão de 20 %."
          >
            <Input
              id={bandLoId}
              type="number"
              inputMode="decimal"
              className="numeric"
              placeholder="20"
              value={value.sl_band_lo_pct ?? ''}
              disabled={disabled}
              invalid={errors.sl_band_lo_pct !== undefined}
              onChange={(e) =>
                onChange({
                  sl_band_lo_pct: e.target.value === '' ? null : Number(e.target.value),
                })
              }
            />
          </Field>

          <Field
            label="Nível máx. (%)"
            htmlFor={bandHiId}
            error={errors.sl_band_hi_pct}
            tooltip="Nível máximo da faixa segura de PV, em % da faixa de medição. Em branco usa o padrão de 80 %."
          >
            <Input
              id={bandHiId}
              type="number"
              inputMode="decimal"
              className="numeric"
              placeholder="80"
              value={value.sl_band_hi_pct ?? ''}
              disabled={disabled}
              invalid={errors.sl_band_hi_pct !== undefined}
              onChange={(e) =>
                onChange({
                  sl_band_hi_pct: e.target.value === '' ? null : Number(e.target.value),
                })
              }
            />
          </Field>

          <Field
            label="Erro pequeno (% da faixa)"
            htmlFor={errorSmallId}
            error={errors.sl_error_small_pct}
            tooltip="Abaixo deste erro, com o nível dentro da faixa, a IA leva a ação integral ao mínimo para manter a válvula parada."
          >
            <Input
              id={errorSmallId}
              type="number"
              inputMode="decimal"
              className="numeric"
              value={value.sl_error_small_pct}
              disabled={disabled}
              invalid={errors.sl_error_small_pct !== undefined}
              onChange={(e) => onChange({ sl_error_small_pct: Number(e.target.value) })}
            />
          </Field>

          <Field
            label="Rampa máx. do CO (%/min)"
            htmlFor={coRampId}
            error={errors.sl_co_ramp_max_pct_min}
            tooltip="Se a válvula variar mais rápido que isto, a IA nunca reduz o tempo integral neste ciclo. 0 desativa a verificação."
          >
            <Input
              id={coRampId}
              type="number"
              inputMode="decimal"
              className="numeric"
              value={value.sl_co_ramp_max_pct_min}
              disabled={disabled}
              invalid={errors.sl_co_ramp_max_pct_min !== undefined}
              onChange={(e) => onChange({ sl_co_ramp_max_pct_min: Number(e.target.value) })}
            />
          </Field>
        </>
      )}
    </>
  );
}
