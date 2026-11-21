import type { CSSProperties } from 'react'
import type { ModuleResult, RiskMonth, WaterBalance } from '../api'
import * as fmt from '../format'
import { ModuleSection } from './ModuleSection'
import { YearBars } from './YearBars'

function Row({ label, value, normal }: { label: string; value: string; normal: string }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{value}</td>
      <td className="muted">{normal}</td>
    </tr>
  )
}

function RiskCalendar({ months, stage }: { months: RiskMonth[]; stage: string }) {
  return (
    <figure className="risk-calendar">
      <figcaption>
        <strong>Kalendarz ryzyka suszy (10 lat)</strong>
        <span className="muted">
          {' '}
          w ilu latach uprawa miała co najmniej 15 dni silnego stresu wodnego w danym miesiącu.
          Okres krytyczny: {stage}.
        </span>
      </figcaption>
      <ol>
        {months.map((m) => {
          const share = m.years ? m.years_with_stress / m.years : 0
          return (
            <li key={m.month} style={{ '--risk': share } as CSSProperties}>
              <span className="risk-month">{fmt.month(m.month)}</span>
              <span className="risk-cell" />
              <span className="risk-value">
                {m.years_with_stress}/{m.years}
              </span>
            </li>
          )
        })}
      </ol>
    </figure>
  )
}

export function WaterSection({ water, year }: { water: ModuleResult<WaterBalance>; year: number }) {
  return (
    <ModuleSection id="water" title="Bilans wodny: pogoda i woda w glebie" module={water}>
      {(w) => (
        <>
          <p className="muted">
            Ostatnie 60 dni ({fmt.dayMonth(w.window.start)}–{fmt.dayMonth(w.window.end)}), metoda
            klimatycznego bilansu wodnego jak w monitoringu suszy IUNG.
          </p>
          <table className="facts">
            <thead>
              <tr>
                <th scope="col" />
                <th scope="col">teraz</th>
                <th scope="col">średnio</th>
              </tr>
            </thead>
            <tbody>
              <Row
                label="Opady"
                value={fmt.mm(w.window.precipitation_mm.value)}
                normal={fmt.mm(w.window.precipitation_mm.normal)}
              />
              <Row
                label="Parowanie ET0"
                value={fmt.mm(w.window.et0_mm.value)}
                normal={fmt.mm(w.window.et0_mm.normal)}
              />
              <Row
                label="Bilans (KBW)"
                value={fmt.mmSigned(w.window.kbw_mm.value)}
                normal={fmt.mmSigned(w.window.kbw_mm.normal)}
              />
              <Row
                label="Dni ≥30 °C"
                value={fmt.num(w.window.hot_days.value)}
                normal={fmt.num(w.window.hot_days.normal)}
              />
              <Row
                label="Woda dostępna w glebie"
                value={fmt.pct(w.available_pct.value)}
                normal={fmt.pct(w.available_pct.normal)}
              />
            </tbody>
          </table>
          <YearBars
            comparison={w.window.kbw_mm}
            year={year}
            format={fmt.mmSigned}
            label="Klimatyczny bilans wodny 60 dni do tej samej daty w kolejnych latach"
          />
          <p className="muted">
            Strefa korzeni mieści {fmt.mm(w.taw_mm)} wody dostępnej, z czego{' '}
            {fmt.mm(w.raw_mm)} roślina pobiera bez stresu.
            {w.in_season
              ? ` Współczynnik uprawowy Kc dziś: ${fmt.num(w.kc)}.`
              : ' Uprawa jest poza sezonem wegetacji.'}{' '}
            Komórka siatki pogodowej: {fmt.coord(w.grid_lat)}° N, {fmt.coord(w.grid_lon)}° E.
          </p>
          <RiskCalendar months={w.risk_calendar} stage={w.critical_stage} />
        </>
      )}
    </ModuleSection>
  )
}
