import { useEffect, useId, useState } from 'react'
import * as fmt from '../format'
import { errorMessage } from '../useParcelReport'
import { fetchReports, type ReportSummary, type SavedParcel } from './accountApi'
import { LevelBadge } from './Change'
import { changeText, parcelLabel } from './labels'

interface Props {
  saved: SavedParcel[]
  cropName: (id: string) => string
  onOpenReport: (reportId: number) => void
}

export function ReportArchive({ saved, cropName, onOpenReport }: Props) {
  const selectId = useId()
  const [reports, setReports] = useState<ReportSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [parcelId, setParcelId] = useState<string>('')

  useEffect(() => {
    fetchReports().then(setReports, (err: unknown) => setError(errorMessage(err)))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!reports) return <p className="muted">Wczytuję archiwum…</p>
  if (reports.length === 0) {
    return (
      <p className="notice">
        Archiwum jest puste. Każda analiza, którą uruchomisz po zalogowaniu, zapisze się tutaj, żeby
        można było porównać, jak zmienia się sytuacja na działce.
      </p>
    )
  }

  // Parcels with reports, newest activity first (reports arrive newest first).
  const parcelIds = [...new Set(reports.map((r) => r.parcel_id))]
  const current = parcelIds.includes(parcelId) ? parcelId : parcelIds[0]
  const label = (id: string) => {
    const known = saved.find((s) => s.parcel_id === id)
    return known ? parcelLabel(known) : id
  }
  const history = reports.filter((r) => r.parcel_id === current)

  return (
    <>
      <div className="field">
        <label htmlFor={selectId}>Działka</label>
        <select id={selectId} value={current} onChange={(e) => setParcelId(e.target.value)}>
          {parcelIds.map((id) => (
            <option key={id} value={id}>
              {label(id)}
            </option>
          ))}
        </select>
      </div>
      <ol className="archive-list">
        {history.map((report, i) => (
          <li key={report.id}>
            <button type="button" className="archive-item" onClick={() => onOpenReport(report.id)}>
              <span className="archive-when">
                <strong>{fmt.dateTime(report.generated_at)}</strong>
                <span className="muted fine">
                  {cropName(report.crop)}, stan na {fmt.longDate(report.analysis_date)}
                </span>
              </span>
              <span className="archive-result">
                <LevelBadge level={report.level} />
                <span className="num">
                  {report.water_pct === null ? '' : `woda ${fmt.pct(report.water_pct)}`}
                </span>
              </span>
              <span className="muted fine archive-change">
                {changeText(report, history[i + 1] ?? null)}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </>
  )
}
