import type { AnalysisReport, ModuleResult, RetentionAnalysis } from '../api'
import * as fmt from '../format'
import { Busy } from './Busy'
import { DiagnosisSection, LimitationsSection } from './DiagnosisSection'
import { HydroSection, SatelliteSection, SoilSection } from './FieldSections'
import { RecommendationsSection } from './RecommendationsSection'
import { SiteCard } from './SiteCard'
import { Sources } from './Sources'
import { WaterSection } from './WaterSection'

interface Props {
  report: AnalysisReport
  selectedSiteId: number | null
  onSelectSite: (id: number) => void
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
        <>
          <TerrainResults
            analysis={terrain.data}
            selectedSiteId={selectedSiteId}
            onSelectSite={onSelectSite}
          />
          <p className="muted">
            {!terrain.data.ditches_checked
              ? 'Mapa rowów (OpenStreetMap) była niedostępna, więc nie sprawdzono miejsc na zastawki.'
              : terrain.data.ditches.length === 0
                ? 'Na działce i przy jej granicy nie ma rowów w OpenStreetMap.'
                : `Rowy przy działce: ${terrain.data.ditches.length} (OpenStreetMap, © współtwórcy OSM, ODbL).`}
          </p>
        </>
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
  const year = Number(report.analysis_date.slice(0, 4))
  return (
    <article className="report" aria-label="Raport">
      <header className="report-header">
        <h2>
          Raport: {report.crop.name}, {fmt.longDate(report.analysis_date)}
        </h2>
        <p className="muted">Wygenerowano {fmt.dateTime(report.generated_at)}</p>
      </header>
      <DiagnosisSection diagnosis={report.diagnosis} />
      <RecommendationsSection
        recommendations={report.recommendations}
        onSelectSite={onSelectSite}
      />
      <WaterSection water={report.water} year={year} />
      <SatelliteSection satellite={report.satellite} year={year} />
      <SoilSection soil={report.soil} />
      <HydroSection hydro={report.hydro} />
      <TerrainSection
        terrain={report.terrain}
        selectedSiteId={selectedSiteId}
        onSelectSite={onSelectSite}
      />
      <LimitationsSection diagnosis={report.diagnosis} />
    </article>
  )
}
