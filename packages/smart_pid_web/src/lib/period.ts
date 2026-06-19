export type PeriodKey = '15m' | '1h' | '8h' | '24h' | '7d';

export interface PeriodRange {
  startIso: string;
  endIso: string;
  key: PeriodKey;
}

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;

export const PERIOD_OPTIONS: ReadonlyArray<{ key: PeriodKey; label: string; ms: number }> = [
  { key: '15m', label: 'Last 15 min', ms: 15 * MINUTE },
  { key: '1h', label: 'Last 1 hour', ms: HOUR },
  { key: '8h', label: 'Last 8 hours', ms: 8 * HOUR },
  { key: '24h', label: 'Last 24 hours', ms: DAY },
  { key: '7d', label: 'Last 7 days', ms: 7 * DAY },
];

export function periodRange(key: PeriodKey, now: Date = new Date()): PeriodRange {
  const opt = PERIOD_OPTIONS.find((o) => o.key === key);
  if (!opt) throw new Error(`Unknown period key: ${key}`);
  const end = now.getTime();
  return {
    endIso: new Date(end).toISOString(),
    startIso: new Date(end - opt.ms).toISOString(),
    key,
  };
}
