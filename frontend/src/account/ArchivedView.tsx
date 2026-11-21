import * as fmt from '../format'
import { Report } from '../panel/Report'
import type { ArchivedReport } from './accountApi'
import { BackButton } from './AccountView'
import { Comparison } from './Change'

interface Props {
  archived: ArchivedReport
  selectedSiteId: number | null
  onSelectSite: (id: number) => void
  onBack: () => void
}

/** An archived report, read-only: the stored snapshot is shown as it was, never re-run. */
export function ArchivedView({ archived, selectedSiteId, onSelectSite, onBack }: Props) {
  const { report, summary, previous } = archived
  return (
    <>
      <BackButton onClick={onBack} label="Wróć do konta" />
      <section className="card archived-banner" aria-label="Raport archiwalny">
        <p className="eyebrow">Raport archiwalny · tylko do odczytu</p>
        <h2>
          Działka {report.parcel.number} <span className="muted">· {report.parcel.region}</span>
        </h2>
        <p className="muted fine">
          Zapisany {fmt.dateTime(summary.generated_at)}. Dane pokazują stan z tamtej chwili; żeby
          sprawdzić, jak jest teraz, uruchom nową analizę.
        </p>
        <Comparison now={summary} before={previous} />
      </section>
      <Report report={report} selectedSiteId={selectedSiteId} onSelectSite={onSelectSite} />
    </>
  )
}
