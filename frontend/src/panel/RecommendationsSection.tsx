import type { Recommendation } from '../api'
import * as fmt from '../format'

const CATEGORY = {
  irrigation: 'Nawadnianie',
  retention: 'Retencja',
  soil: 'Gleba',
  crop: 'Uprawa',
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
      <h3 id="recs-heading">Co zrobić: zalecenia dla tej działki</h3>
      {recommendations.length === 0 ? (
        <p>Brak danych do zaleceń.</p>
      ) : (
        <ol className="recs">
          {recommendations.map((r) => (
            <li key={r.key} className={`rec rec-${r.category}`}>
              <div className="rec-head">
                <span className="rec-category">{CATEGORY[r.category]}</span>
                <span className="rec-title">{r.title}</span>
              </div>
              {r.effect_m3 && (
                <p className="rec-effect">
                  {fmt.m3Range(r.effect_m3)} <small>{r.effect_note}</small>
                </p>
              )}
              <p>{r.action}</p>
              <p className="muted">
                <strong>Dlaczego:</strong> {r.why}
              </p>
              <p className="muted">
                <strong>Kiedy:</strong> {r.when} <strong>Koszt:</strong> {r.cost}.
              </p>
              {r.formalities && (
                <p className="muted">
                  <strong>Formalności:</strong> {r.formalities}
                </p>
              )}
              {r.site_ids.length > 0 && (
                <p className="rec-sites">
                  Pokaż na mapie:{' '}
                  {r.site_ids.map((id) => (
                    <button key={id} type="button" onClick={() => onSelectSite(id)}>
                      nr {id}
                    </button>
                  ))}
                </p>
              )}
              {r.ditch_ids.length > 0 && (
                <p className="muted">Rowy i zastawki zaznaczono na mapie (czerwone punkty).</p>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
