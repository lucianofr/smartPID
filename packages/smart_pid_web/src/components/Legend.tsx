import { Fragment } from 'react';
import { cn } from '@/lib/utils';

/**
 * Collapsible glossary of the abbreviations a screen puts on the operator's
 * eye. Native `<details>` rather than a state-driven disclosure: it is closed
 * by default, keyboard- and screen-reader-operable for free, and a glossary
 * has no behaviour worth a hook.
 *
 * Groups own the disambiguation. The same token means different things in
 * different places — fuzzy `HIGH` is a large error under `iae` and a strong
 * oscillation under `osc` — so entries are always presented under the heading
 * that scopes them, never merged into one flat list.
 */

export interface LegendEntry {
  /** The abbreviation exactly as the screen renders it. */
  term: string;
  description: string;
}

export interface LegendGroup {
  title: string;
  entries: readonly LegendEntry[];
}

export interface LegendProps {
  groups: readonly LegendGroup[];
  /** Visible summary text, and the accessible name of the disclosure. */
  label?: string;
  className?: string;
}

export function Legend({ groups, label = 'Legenda', className }: LegendProps) {
  const populated = groups.filter((group) => group.entries.length > 0);
  if (populated.length === 0) return null;

  return (
    <details className={cn('rounded-card border border-rule bg-surface', className)}>
      <summary className="cursor-pointer px-3 py-2 text-2xs font-medium uppercase tracking-wider text-text-soft">
        {label}
      </summary>
      <div className="grid grid-cols-1 gap-x-6 gap-y-3 border-t border-rule px-3 py-3 md:grid-cols-2 xl:grid-cols-3">
        {populated.map((group) => (
          <section key={group.title} aria-label={group.title}>
            <h3 className="mb-1 text-2xs font-medium uppercase tracking-wider text-text-soft">
              {group.title}
            </h3>
            <dl className="grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 text-xs">
              {group.entries.map((entry) => (
                <Fragment key={entry.term}>
                  <dt className="font-semibold text-text">{entry.term}</dt>
                  <dd className="text-text-soft">{entry.description}</dd>
                </Fragment>
              ))}
            </dl>
          </section>
        ))}
      </div>
    </details>
  );
}
