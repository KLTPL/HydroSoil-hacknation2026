import type { ModuleResult, Scenario, WaterBalance } from '../api'
import * as fmt from '../format'

function stressStart(s: Scenario, start: string): string {
  if (s.first_stress_day === null) return 'nie wystąpi'
  if (s.first_stress_day === start) return 'już teraz'
  return `od ${fmt.dayMonth(s.first_stress_day)}`
}

/** What-if runs of the root-zone model over the next 30 days. */
export function ScenariosSection({ water }: { water: ModuleResult<WaterBalance> }) {
  const scenarios = water.data?.scenarios
  if (water.status !== 'ok' || !scenarios) return null
  return (
    <section className="report-section" aria-labelledby="scenarios-heading">
      <h3 id="scenarios-heading">Co jeśli: najbliższe 30 dni</h3>
      <p className="muted">
        {fmt.dayMonth(scenarios.start)}–{fmt.dayMonth(scenarios.end)}. Model wody w glebie liczony
        dalej od dzisiejszego stanu z pogodą tych samych dni z poprzednich lat.
      </p>
      <ul className="scenarios">
        {scenarios.items.map((s) => (
          <li key={s.key} className={`scenario-${s.key}`}>
            <strong>{s.label}</strong>
            <span>
              opady {fmt.mm(s.rain_mm)} · silny stres: {stressStart(s, scenarios.start)}
              {s.stress_days > 0 && ` (${s.stress_days} dni)`}
            </span>
            <span>
              na koniec w glebie {fmt.pct(s.available_pct_end)} wody, do uzupełnienia{' '}
              {fmt.mm(s.refill_mm)}
            </span>
          </li>
        ))}
      </ul>
      <p className="muted">
        „Sucho” to drugi najsuchszy z 10 lat (susza zdarzająca się mniej więcej co 5 lat). Silny
        stres: roślina pobiera mniej niż połowę potrzebnej wody.
        {scenarios.items.some((s) => s.key === 'more_humus') &&
          ` +1 % próchnicy to ok. ${fmt.mm(scenarios.humus_gain_mm)} więcej wody w glebie (efekt po kilku latach).`}
      </p>
    </section>
  )
}
