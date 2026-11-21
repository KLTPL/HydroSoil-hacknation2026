import type { CSSProperties } from 'react'
import * as fmt from '../format'
import type { Recommendation } from '../model'

const CATEGORY = {
  retention: 'Retencja',
  soil: 'Gleba',
  crop: 'Uprawa',
  irrigation: 'Nawadnianie, w ostateczności',
} as const

export function RecommendationsSection({
  recommendations,
  onSelectSite,
}: {
  recommendations: Recommendation[]
  onSelectSite: (id: number) => void
}) {
  return (
    <section className="report-section" aria-labelledby="recs-heading">
      <p className="eyebrow">3 · Plan działań</p>
      <h3 id="recs-heading">Co zrobić na tej działce</h3>
      <p className="section-lead">
        Najpierw zatrzymaj wodę, która spada na pole, potem popraw glebę. Nawadniaj na końcu.
      </p>
      {recommendations.length === 0 ? (
        <p>Brak danych do zaleceń.</p>
      ) : (
        <ol className="recs">
          {recommendations.map((r, i) => (
            <li key={r.key} className={`rec rec-${r.category}`} style={{ '--i': i } as CSSProperties}>
              <span className="rec-step" aria-hidden="true">
                {i + 1}
              </span>
              <div className="rec-body">
                <p className="rec-category">
                  {CATEGORY[r.category]} · koszt {r.cost}
                </p>
                <h4 className="rec-title">{r.title}</h4>
                {r.effect_m3 && (
                  <p className="rec-effect">
                    {fmt.m3Range(r.effect_m3)} <small>{r.effect_note}</small>
                  </p>
                )}
                <p className="rec-action">{r.action}</p>
                {r.site_ids.length > 0 && (
                  <p className="rec-sites">
                    <span className="muted">Na mapie:</span>
                    {r.site_ids.map((id) => (
                      <button key={id} type="button" className="chip" onClick={() => onSelectSite(id)}>
                        miejsce {id}
                      </button>
                    ))}
                  </p>
                )}
                <details className="rec-more">
                  <summary>Dlaczego i kiedy</summary>
                  <dl>
                    <dt>Dlaczego</dt>
                    <dd>{r.why}</dd>
                    <dt>Kiedy</dt>
                    <dd>{r.when}</dd>
                    {r.formalities && (
                      <>
                        <dt>Formalności</dt>
                        <dd>{r.formalities}</dd>
                      </>
                    )}
                    {r.ditch_ids.length > 0 && (
                      <>
                        <dt>Mapa</dt>
                        <dd>Rowy i proponowane zastawki zaznaczono na mapie (różowe punkty).</dd>
                      </>
                    )}
                  </dl>
                </details>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
