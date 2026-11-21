import type { Parcel } from '../api'
import * as fmt from '../format'
import type { Lookup, ReportState } from '../useParcelReport'
import { AnalysisForm } from './AnalysisForm'
import { Busy } from './Busy'
import { ParcelSearch } from './ParcelSearch'
import { Report } from './Report'

interface Props {
  parcel: Parcel | null
  lookup: Lookup
  report: ReportState
  crop: string
  date: string
  selectedSiteId: number | null
  onChooseParcel: (parcel: Parcel) => void
  onCropChange: (crop: string) => void
  onDateChange: (date: string) => void
  onAnalyze: () => void
  onSelectSite: (id: number) => void
}

export function Panel(props: Props) {
  const { parcel, lookup, report } = props
  return (
    <aside className="panel">
      <header>
        <h1>Zatrzymaj wodę</h1>
        <p className="muted">Ocena wody na działce i co zrobić, żeby jej nie tracić</p>
      </header>

      <ParcelSearch onChoose={props.onChooseParcel} />
      <div aria-live="polite">
        {lookup.status === 'loading' && <Busy label="Szukam działki…" />}
        {lookup.status === 'error' && <p className="error">{lookup.message}</p>}
      </div>

      {parcel && (
        <section className="parcel" aria-label="Wybrana działka">
          <h2>Działka {parcel.number}</h2>
          <p className="muted">
            {parcel.region}, gm. {parcel.commune} · {fmt.ha(parcel.area_ha)}
            <br />
            <code>{parcel.id}</code>
          </p>
          <AnalysisForm
            crop={props.crop}
            date={props.date}
            busy={report.status === 'loading'}
            onCropChange={props.onCropChange}
            onDateChange={props.onDateChange}
            onSubmit={props.onAnalyze}
          />
        </section>
      )}

      <div aria-live="polite">
        {report.status === 'loading' && (
          <Busy label="Analizuję działkę…" hint="Pobieram dane i liczę wynik, zwykle do 30 s." />
        )}
        {report.status === 'error' && <p className="error">{report.message}</p>}
        {report.status === 'done' && (
          <Report
            report={report.report}
            selectedSiteId={props.selectedSiteId}
            onSelectSite={props.onSelectSite}
          />
        )}
      </div>
    </aside>
  )
}
