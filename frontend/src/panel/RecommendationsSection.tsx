import { useId, useState, type CSSProperties } from 'react'
import * as fmt from '../format'
import type { IrrigationEstimate, Recommendation } from '../model'

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
  // One step open at a time keeps the list short enough to compare steps at a glance.
  const [open, setOpen] = useState<string | null>(null)
  return (
    <section className="report-section" aria-labelledby="recs-heading">
      <p className="eyebrow print-only">3 · Plan działań</p>
      <h3 id="recs-heading">Co zrobić na tej działce</h3>
      <p className="section-lead">
        Najpierw zatrzymaj wodę, która spada na pole, potem popraw glebę. Nawadniaj na końcu.
      </p>
      {recommendations.length === 0 ? (
        <p>Brak danych do zaleceń.</p>
      ) : (
        <ol className="recs">
          {recommendations.map((r, i) => (
            <Step
              key={r.key}
              rec={r}
              step={i + 1}
              open={open === r.key}
              onToggle={() => setOpen(open === r.key ? null : r.key)}
              onSelectSite={onSelectSite}
            />
          ))}
        </ol>
      )}
    </section>
  )
}

interface StepProps {
  rec: Recommendation
  step: number
  open: boolean
  onToggle: () => void
  onSelectSite: (id: number) => void
}

/** Closed: number, title, effect and cost. Open: what to do, where, why and when. */
function Step({ rec: r, step, open, onToggle, onSelectSite }: StepProps) {
  const bodyId = useId()
  return (
    <li className={`rec rec-${r.category}`} style={{ '--i': step - 1 } as CSSProperties}>
      <h4 className="rec-heading">
        <button type="button" className="rec-toggle" aria-expanded={open} aria-controls={bodyId} onClick={onToggle}>
          <span className="rec-step" aria-hidden="true">
            {step}
          </span>
          <span className="rec-title">{r.title}</span>
          <span className="rec-meta">
            {r.effect_m3 && <span className="rec-effect">{fmt.m3Range(r.effect_m3)}</span>}
            <span>
              {CATEGORY[r.category]} · koszt {r.cost}
            </span>
          </span>
        </button>
      </h4>
      <div id={bodyId} className="rec-body" hidden={!open}>
        {r.effect_m3 && (
          <p className="rec-effect-note">
            {fmt.m3Range(r.effect_m3)} {r.effect_note}
          </p>
        )}
        {r.irrigation && <IrrigationNote estimate={r.irrigation} />}
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
        <dl className="rec-why">
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
      </div>
    </li>
  )
}

/** Compact water and cost estimate with the water-law limit; details stay in "Formalności". */
function IrrigationNote({ estimate }: { estimate: IrrigationEstimate }) {
  const { water_m3, cost_pln, yearly_limit_m3, over_limit } = estimate
  return (
    <p className="rec-irrigation-note">
      <span>
        Koszt pracy ok. {fmt.whole(cost_pln.low)}–{fmt.whole(cost_pln.high)} zł (szacunek, własne źródło wody,
        bez sprzętu).
      </span>{' '}
      {over_limit && (
        <span className="rec-warning">
          ⚠ {fmt.m3(water_m3)} to więcej niż {fmt.m3(yearly_limit_m3)} rocznie (średnio 5 m³ na dobę), które można
          pobrać bez pozwolenia wodnoprawnego.
        </span>
      )}
    </p>
  )
}
