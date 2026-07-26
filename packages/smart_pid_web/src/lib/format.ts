/**
 * Fixed-decimal tabular formatting for process values (§6.2). The SINGLE
 * format module — phase 3 extends it (units, timestamps) without changing
 * this signature. Alignment comes from .numeric (tabular-nums, Geist Mono).
 */
export function formatNumber(value: number | null | undefined, decimals: number): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  return value.toFixed(decimals);
}

/**
 * Phase-3 consolidation: this file is the SINGLE numeric formatting module
 * (spec §7 kills the old lib/ vs multitrend/ duplication). Policy: every
 * absent OR non-finite value renders as '—' (em dash), matching formatNumber.
 */

/** "150.3 °C" — formatNumber plus a unit suffix; absent values stay bare '—'. */
export function formatWithUnit(
  value: number | null | undefined,
  unit: string,
  decimals: number,
): string {
  if (value !== null && value !== undefined && !Number.isFinite(value)) return '—';
  const num = formatNumber(value, decimals);
  if (num === '—' || unit === '') return num;
  return `${num} ${unit}`;
}

/** Ratio → percent string: 0.1234 → "12.3%" (absorbs multitrend formatVariabilityPct). */
export function formatPercent(ratio: number | null | undefined, decimals = 1): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return '—';
  return `${(ratio * 100).toFixed(decimals)}%`;
}

/**
 * Local wall-clock HH:MM:SS for wire timestamps: accepts epoch SECONDS
 * (envelope.ts, monitor-mode status) or ISO-8601 strings (worker payloads).
 */
export function formatTimestamp(ts: string | number | null | undefined): string {
  if (ts === null || ts === undefined) return '—';
  const ms =
    typeof ts === 'number' ? (Number.isFinite(ts) ? ts * 1000 : Number.NaN) : Date.parse(ts);
  if (Number.isNaN(ms)) return '—';
  const d = new Date(ms);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}