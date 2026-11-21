import type { AnalysisReport, DataSource, ModuleResult, RetentionAnalysis } from '../api'
import * as fmt from '../format'
import { Busy } from './Busy'
import { SiteCard } from './SiteCard'

const dateTime = new Intl.DateTimeFormat('pl-PL', { dateStyle: 'medium', timeStyle: 'short' })
const dateOnly = new Intl.DateTimeFormat('pl-PL', { dateStyle: 'long' })

interface Props {
  report: AnalysisReport
  selectedSiteId: number | null
  onSelectSite: (id: number) => void
}

function Sources({ sources }: { sources: DataSource[] }) {
  if (sources.length === 0) return null
  return (
    <ul className="sources muted">
      {sources.map((s) => (
        <li key={s.name}>
          <a href={s.url} target="_blank" rel="noreferrer">
            {s.name}
          </a>{' '}
          · {s.retrieved === 'live' ? 'pobrane teraz' : 'z pamięci podręcznej'},{' '}
          {dateTime.format(new Date(s.retrieved_at))} · {s.license}
        </li>
      ))}
    </ul>
  )
}

function TerrainSection({
  terrain,
  selectedSiteId,
  onSelectSite,
}: {
  terrain: ModuleResult<RetentionAnalysis>
  selectedSiteId: number | null
  onSelectSite: (id: number) => void
}) {
  return (
    <section className="report-section" aria-labelledby="terrain-heading">
      <h3 id="terrain-heading">Gdzie zatrzymać wodę na działce</h3>
      {terrain.status === 'pending' && <Busy label={terrain.message ?? 'Analizuję teren…'} />}
      {terrain.status === 'unavailable' && <p className="error">{terrain.message}</p>}
      {terrain.status === 'ok' && terrain.data && (
        <TerrainResults
          analysis={terrain.data}
          selectedSiteId={selectedSiteId}
          onSelectSite={onSelectSite}
        />
      )}
      <Sources sources={terrain.sources} />
    </section>
  )
}

function TerrainResults({
  analysis,
  selectedSiteId,
  onSelectSite,
}: {
  analysis: RetentionAnalysis
  selectedSiteId: number | null
  onSelectSite: (id: number) => void
}) {
  const { summary, sites, assumptions } = analysis
  if (sites.length === 0) {
    return (
      <p>
        Na tej działce nie ma zagłębień, które zatrzymają wodę: teren jest płaski albo woda
        spływa poza działkę.
      </p>
    )
  }
  return (
    <>
      <p className="summary-value">{fmt.m3Range(summary.retained_m3)}</p>
      <p className="muted">
        wody można zatrzymać z jednego deszczu {assumptions.design_rain_mm} mm w{' '}
        {summary.site_count} {summary.site_count === 1 ? 'miejscu' : 'miejscach'}
      </p>
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
        Szacunek z modelu terenu w siatce {assumptions.resolution_m} m. Przyjęty współczynnik
        spływu {assumptions.runoff_coeff.low}–{assumptions.runoff_coeff.high}. Obliczenia nie
        uwzględniają drenażu ani wód gruntowych.
      </p>
    </>
  )
}

export function Report({ report, selectedSiteId, onSelectSite }: Props) {
  return (
    <article className="report" aria-label="Raport">
      <header className="report-header">
        <h2>
          Raport: {report.crop.name}, {dateOnly.format(new Date(report.analysis_date))}
        </h2>
        <p className="muted">Wygenerowano {dateTime.format(new Date(report.generated_at))}</p>
      </header>
      <TerrainSection
        terrain={report.terrain}
        selectedSiteId={selectedSiteId}
        onSelectSite={onSelectSite}
      />
    </article>
  )
}
