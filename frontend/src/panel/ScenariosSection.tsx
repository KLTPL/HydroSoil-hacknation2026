import type { CSSProperties } from 'react'
import type { ModuleResult, Scenario, WaterBalance } from '../model'
import * as fmt from '../format'

function stressStart(s: Scenario, start: string): string {
  if (s.first_stress_day === null) return 'bez silnego stresu'
  const days = s.stress_days > 0 ? ` (${s.stress_days} dni)` : ''
  if (s.first_stress_day === start) return `silny stres od razu${days}`
  return `silny stres od ${fmt.dayMonth(s.first_stress_day)}${days}`
}

/**
 * What-if runs of the root-zone model over the next 30 days: one bar per weather variant,
 * showing the plant-available water left at the end against the crop's stress line.
 */
export function ScenariosSection({
  water,
  threshold,
}: {
  water: ModuleResult<WaterBalance>
  threshold: number | null
}) {
  const scenarios = water.data?.scenarios
  if (water.status !== 'ok' || !scenarios) return null
  return (
    <section className="report-section" aria-labelledby="scenarios-heading">
      <h3 id="scenarios-heading">Najbliższe 30 dni</h3>
      <p className="muted fine">
        Woda dostępna dla roślin {fmt.dayMonth(scenarios.end)}, gdy pogoda będzie jak w tych
        samych dniach wcześniejszych lat
        {threshold !== null && `; kreska to próg stresu uprawy (${fmt.pct(threshold)})`}.
      </p>
      <ul className="scenario-bars" style={{ '--stress': (threshold ?? 0) / 100 } as CSSProperties}>
        {scenarios.items.map((s) => (
          <li
            key={s.key}
            className={`scenario-${s.key}${threshold !== null && s.available_pct_end < threshold ? ' below' : ''}`}
          >
            <span className="scenario-label">{s.label}</span>
            <span className="scenario-track" aria-hidden="true">
              <span className="scenario-fill" style={{ '--end': s.available_pct_end / 100 } as CSSProperties} />
              {threshold !== null && <span className="scenario-stress" />}
            </span>
            <span className="scenario-value">{fmt.pct(s.available_pct_end)}</span>
            <span className="scenario-note">
              {fmt.mm(s.rain_mm)} deszczu · {stressStart(s, scenarios.start)} · do pełna{' '}
              {fmt.mm(s.refill_mm)}
            </span>
          </li>
        ))}
      </ul>
      <p className="muted fine">
        „Sucho” to drugi najsuchszy z 10 lat (taka susza zdarza się mniej więcej co 5 lat). Silny
        stres: roślina pobiera mniej niż połowę potrzebnej wody.
        {scenarios.items.some((s) => s.key === 'more_humus') &&
          ` +1 % próchnicy to ok. ${fmt.mm(scenarios.humus_gain_mm)} więcej wody w glebie (efekt po kilku latach).`}
      </p>
    </section>
  )
}
