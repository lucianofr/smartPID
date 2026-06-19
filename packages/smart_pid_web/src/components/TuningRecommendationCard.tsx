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

export function TuningRecommendationCard({ loopName, rec }: TuningRecommendationCardProps) {
  return (
    <article data-testid={`tuning-${loopName}`}>
      <h4>{loopName}</h4>
      {rec == null ? (
        <p data-testid={`tuning-${loopName}-empty`}>No tuning recommendation</p>
      ) : (
        <dl data-testid={`tuning-${loopName}-body`} data-status={rec.status}>
          <div>
            <dt>Kp</dt>
            <dd>
              {rec.current_kp.toFixed(4)} &rarr; {rec.recommended_kp.toFixed(4)}
            </dd>
          </div>
          <div>
            <dt>Ti</dt>
            <dd>
              {rec.current_ti.toFixed(4)} &rarr; {rec.recommended_ti.toFixed(4)}
            </dd>
          </div>
          <div>
            <dt>Td</dt>
            <dd>
              {rec.current_td.toFixed(4)} &rarr; {rec.recommended_td.toFixed(4)}
            </dd>
          </div>
          <p>{rec.reason}</p>
        </dl>
      )}
    </article>
  );
}
