import type { AnalysisReport, ModuleResult, RetentionAnalysis } from '../api'
import * as fmt from '../format'
import { requestPrint } from '../print'
import { Busy } from './Busy'
import { DiagnosisSection, LimitationsSection } from './DiagnosisSection'
import { EdoSection } from './EdoSection'
import { HydroSection, LandSection, SatelliteSection, SoilSection } from './FieldSections'
import { RecommendationsSection } from './RecommendationsSection'
import { ScenariosSection } from './ScenariosSection'
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
          <DitchNote analysis={terrain.data} />
        </>
      )}
      <Sources sources={terrain.sources} />
    </section>
  )
}

function DitchNote({ analysis }: { analysis: RetentionAnalysis }) {
  const lidar = analysis.ditches.filter((d) => d.kind === 'lidar').length
  const osm = analysis.ditches.length - lidar
  return (
    <p className="muted">
      Rowy przy działce: {lidar} wykryte w modelu terenu LIDAR
      {analysis.ditches_checked
        ? `, ${osm} z OpenStreetMap (© współtwórcy OSM, licencja ODbL).`
        : '; mapa rowów OpenStreetMap była niedostępna.'}
    </p>
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
        <p className="print-only">
          Działka {report.parcel.number}, obręb {report.parcel.region}, gm.{' '}
          {report.parcel.commune}, {report.parcel.county}, woj. {report.parcel.voivodeship},{' '}
          {fmt.ha(report.parcel.area_ha)}. Identyfikator: {report.parcel.id}.
          <br />
          Raport online: {window.location.href}
        </p>
        <button type="button" className="no-print" onClick={requestPrint}>
          Drukuj / zapisz jako PDF
        </button>
      </header>
      <DiagnosisSection diagnosis={report.diagnosis} />
      <EdoSection edo={report.edo} />
      <RecommendationsSection
        recommendations={report.recommendations}
        onSelectSite={onSelectSite}
      />
      <ScenariosSection water={report.water} />
      <WaterSection water={report.water} year={year} />
      <SatelliteSection satellite={report.satellite} year={year} />
      <SoilSection soil={report.soil} />
      <LandSection land={report.land} />
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
