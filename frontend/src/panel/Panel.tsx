import type { ReactNode } from 'react'
import * as fmt from '../format'
import type { Parcel } from '../model'
import type { Lookup, ReportState } from '../useParcelReport'
import { AnalysisForm } from './AnalysisForm'
import { Busy } from './Busy'
import { ParcelSearch } from './ParcelSearch'
import { Progress } from './Progress'
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
  /** Optional account slots: header control, parcel card action, and a view that
   * temporarily replaces the analysis (account pages, archived report). */
  headerAction?: ReactNode
  parcelAction?: ReactNode
  replacement?: ReactNode
}

function Brand({ action }: { action?: ReactNode }) {
  return (
    <header className="brand">
      <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
        <path d="M16 3c5 6.5 9 11.3 9 16a9 9 0 0 1-18 0c0-4.7 4-9.5 9-16Z" />
        <path className="brand-field" d="M7.6 21.5c3-1.6 5.8-1.6 8.4 0s5.4 1.6 8.4 0" />
      </svg>
      <div>
        <h1>Spływ</h1>
        <p>Zobacz, dokąd ucieka woda z Twojej działki, i zatrzymaj ją</p>
      </div>
      {action}
    </header>
  )
}

export function Panel(props: Props) {
  return (
    <aside className="panel" aria-label="Analiza działki">
      <div className="sheet-grabber" aria-hidden="true" />
      <Brand action={props.headerAction} />
      {props.replacement ?? <Analysis {...props} />}
    </aside>
  )
}

function Analysis(props: Props) {
  const { parcel, lookup, report } = props
  return (
    <>
      <ParcelSearch onChoose={props.onChooseParcel} />
      <div aria-live="polite">
        {lookup.status === 'loading' && <Busy label="Szukam działki…" />}
        {lookup.status === 'error' && <p className="error">{lookup.message}</p>}
      </div>

      {parcel && (
        <section className="parcel card" aria-label="Wybrana działka">
          <div className="parcel-head">
            <div>
              <p className="eyebrow">Działka ewidencyjna</p>
              <h2>
                {parcel.number} <span className="muted">· {parcel.region}</span>
              </h2>
            </div>
            <p className="parcel-area">{fmt.ha(parcel.area_ha)}</p>
          </div>
          <p className="muted fine">
            gm. {parcel.commune}, woj. {parcel.voivodeship} · <code>{parcel.id}</code>
          </p>
          <AnalysisForm
            crop={props.crop}
            date={props.date}
            busy={report.status === 'loading'}
            onCropChange={props.onCropChange}
            onDateChange={props.onDateChange}
            onSubmit={props.onAnalyze}
          />
          {props.parcelAction}
        </section>
      )}

      {report.status === 'loading' && parcel && (
        <Progress parcel={parcel} started={report.started} progress={report.progress} />
      )}
      <div aria-live="polite">
        {report.status === 'error' && <p className="error">{report.message}</p>}
      </div>
      {report.status === 'done' && (
        <Report
          report={report.report}
          selectedSiteId={props.selectedSiteId}
          onSelectSite={props.onSelectSite}
        />
      )}
      {!parcel && lookup.status === 'idle' && (
        <section className="intro" aria-label="Jak to działa">
          <ol>
            <li>
              <span><strong>Wskaż działkę</strong> numerem albo kliknij ją na mapie.</span>
            </li>
            <li>
              <span><strong>Wybierz uprawę i datę</strong>, dziś albo do 10 lat wstecz.</span>
            </li>
            <li>
              <span><strong>Dostaniesz ocenę</strong> z 7 źródeł danych i plan, jak zatrzymać wodę.</span>
            </li>
          </ol>
        </section>
      )}
    </>
  )
}
