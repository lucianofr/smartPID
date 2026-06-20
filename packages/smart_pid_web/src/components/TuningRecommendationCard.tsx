export interface TuningRec {
  current_kp: number;
  current_ti: number;
  current_td: number;
  recommended_kp: number;
  recommended_ti: number;
  recommended_td: number;
  reason: string;
  status: string;
}
export interface TuningRecommendationCardProps {
  loopName: string;
  rec: TuningRec | null;
}

/**
 * Flat ISA-101 tuning recommendation. Token utilities only (no shadow/gradient).
 * The before→after gain values use the `numeric` tabular-nums class so the fixed
 * 4-decimal columns align vertically across Kp/Ti/Td.
 */
export function TuningRecommendationCard({ loopName, rec }: TuningRecommendationCardProps) {
  return (
    <article data-testid={`tuning-${loopName}`}>
      <h4 className="text-text" style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--fw-semibold)' }}>
        {loopName}
      </h4>
      {rec == null ? (
        <p
          data-testid={`tuning-${loopName}-empty`}
          className="text-text-secondary"
          style={{ fontSize: 'var(--text-sm)' }}
        >
          No tuning recommendation
        </p>
      ) : (
        <dl
          data-testid={`tuning-${loopName}-body`}
          data-status={rec.status}
          className="flex flex-col gap-1"
          style={{ fontSize: 'var(--text-sm)' }}
        >
          <div className="flex items-baseline gap-3">
            <dt className="text-text-secondary">Kp</dt>
            <dd className="numeric text-text">
              {rec.current_kp.toFixed(4)} &rarr; {rec.recommended_kp.toFixed(4)}
            </dd>
          </div>
          <div className="flex items-baseline gap-3">
            <dt className="text-text-secondary">Ti</dt>
            <dd className="numeric text-text">
              {rec.current_ti.toFixed(4)} &rarr; {rec.recommended_ti.toFixed(4)}
            </dd>
          </div>
          <div className="flex items-baseline gap-3">
            <dt className="text-text-secondary">Td</dt>
            <dd className="numeric text-text">
              {rec.current_td.toFixed(4)} &rarr; {rec.recommended_td.toFixed(4)}
            </dd>
          </div>
          <p className="text-text-secondary">{rec.reason}</p>
        </dl>
      )}
    </article>
  );
}
