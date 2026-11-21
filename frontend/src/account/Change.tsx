import * as fmt from '../format'
import { LEVEL } from '../panel/levels'
import type { ReportSummary } from './accountApi'
import { changeText } from './labels'

export function LevelBadge({ level }: { level: ReportSummary['level'] }) {
  const { label, tone } = LEVEL[level]
  return <span className={`batch-level tone-${tone}`}>{label}</span>
}

/** Side-by-side comparison shown above an archived report. */
export function Comparison({ now, before }: { now: ReportSummary; before: ReportSummary | null }) {
  if (!before) {
    return <p className="muted fine">To pierwsza zapisana analiza tej działki.</p>
  }
  const pct = (s: ReportSummary) => (s.water_pct === null ? '–' : fmt.pct(s.water_pct))
  return (
    <table className="compare-table">
      <caption className="muted fine">
        Zmiana od poprzedniej analizy ({fmt.dateTime(before.generated_at)}): {changeText(now, before)}
      </caption>
      <thead>
        <tr>
          <th scope="col" />
          <th scope="col">Wtedy</th>
          <th scope="col">Teraz</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th scope="row">Ocena</th>
          <td>
            <LevelBadge level={before.level} />
          </td>
          <td>
            <LevelBadge level={now.level} />
          </td>
        </tr>
        <tr>
          <th scope="row">Woda dla roślin</th>
          <td className="num">{pct(before)}</td>
          <td className="num">{pct(now)}</td>
        </tr>
        <tr>
          <th scope="row">Stan na dzień</th>
          <td>{fmt.longDate(before.analysis_date)}</td>
          <td>{fmt.longDate(now.analysis_date)}</td>
        </tr>
      </tbody>
    </table>
  )
}
