import type { Parcel, RetentionAnalysis } from '../api'
import * as fmt from '../format'
import { SiteCard } from './SiteCard'

export type AnalysisState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'done'; analysis: RetentionAnalysis }

export type PanelState =
  | { status: 'idle' }
  | { status: 'locating' }
  | { status: 'error'; message: string }
  | { status: 'parcel'; parcel: Parcel; analysis: AnalysisState }

interface Props {
  state: PanelState
  selectedSiteId: number | null
  onSelectSite: (id: number) => void
}

function Busy({ label, hint }: { label: string; hint?: string }) {
  return (
    <div className="busy" role="status">
      <progress className="loading-spinner" aria-label={label} />
      <div>
        <p>{label}</p>
        {hint && <p className="muted">{hint}</p>}
      </div>
    </div>
  )
}

function Results({ analysis, selectedSiteId, onSelectSite }: {
  analysis: RetentionAnalysis
  selectedSiteId: number | null
  onSelectSite: (id: number) => void
}) {
  const { summary, sites, assumptions } = analysis
  if (sites.length === 0) {
    return (
      <p>
        Nie znaleziono na tej działce zagłębień, które zatrzymają wodę. Teren jest płaski lub
        woda spływa poza działkę. Wkrótce pokażemy tu inne działania, np. zastawki na rowach.
      </p>
    )
  }
  return (
    <>
      <section className="summary" aria-label="Podsumowanie">
        <p className="summary-value">{fmt.m3Range(summary.retained_m3)}</p>
        <p className="muted">
          wody można zatrzymać z jednego deszczu {assumptions.design_rain_mm} mm w{' '}
          {summary.site_count} {summary.site_count === 1 ? 'miejscu' : 'miejscach'}
        </p>
      </section>
      <ol className="sites">
        {sites.map((site) => (
          <SiteCard
            key={site.id}
            site={site}
            rainMm={assumptions.design_rain_mm}
            selected={site.id === selectedSiteId}
            onSelect={onSelectSite}
          />
        ))}
      </ol>
      <p className="assumptions muted">
        To szacunek na podstawie {assumptions.dem_source} w siatce {assumptions.resolution_m} m.
        Przyjęty współczynnik spływu to {assumptions.runoff_coeff.low}–
        {assumptions.runoff_coeff.high}. Obliczenia nie uwzględniają drenażu ani wód
        gruntowych.
      </p>
    </>
  )
}

export function Panel({ state, selectedSiteId, onSelectSite }: Props) {
  return (
    <aside className="panel" aria-live="polite">
      <header>
        <h1>Zatrzymaj wodę</h1>
        <p className="muted">Gdzie na Twojej działce można zatrzymać wodę</p>
      </header>

      {state.status === 'idle' && (
        <p>
          Kliknij działkę na mapie albo użyj przycisku lokalizacji (◎), jeśli jesteś na polu.
        </p>
      )}
      {state.status === 'locating' && <Busy label="Szukam działki…" />}
      {state.status === 'error' && <p className="error">{state.message}</p>}

      {state.status === 'parcel' && (
        <>
          <section className="parcel" aria-label="Działka">
            <h2>Działka {state.parcel.number}</h2>
            <p className="muted">
              {state.parcel.region}, gm. {state.parcel.commune} · {fmt.ha(state.parcel.area_ha)}
            </p>
          </section>
          {state.analysis.status === 'loading' && (
            <Busy
              label="Analizuję ukształtowanie terenu…"
              hint="Przy pierwszej analizie w nowej okolicy pobieram model terenu, co trwa do ok. 2 minut."
            />
          )}
          {state.analysis.status === 'error' && (
            <p className="error">{state.analysis.message}</p>
          )}
          {state.analysis.status === 'done' && (
            <Results
              analysis={state.analysis.analysis}
              selectedSiteId={selectedSiteId}
              onSelectSite={onSelectSite}
            />
          )}
        </>
      )}
    </aside>
  )
}
