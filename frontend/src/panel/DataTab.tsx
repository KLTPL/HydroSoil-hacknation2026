import * as fmt from '../format'
import type { AnalysisReport, ModuleResult, RetentionAnalysis } from '../model'
import { Busy } from './Busy'
import { EvidenceList, Limitations } from './DiagnosisSection'
import { EdoSection } from './EdoSection'
import { HydroSection, LandSection, SatelliteSection, SoilSection } from './FieldSections'
import { SiteCard } from './SiteCard'
import { Sources } from './Sources'
import { WaterSection } from './WaterSection'

interface SiteProps {
  selectedSiteId: number | null
  onSelectSite: (id: number) => void
}

function TerrainSection({ terrain, ...sites }: SiteProps & { terrain: ModuleResult<RetentionAnalysis> }) {
  return (
    <section className="report-section" aria-labelledby="terrain-heading">
      <h3 id="terrain-heading">Miejsca na wodę z modelu terenu LIDAR</h3>
      {terrain.status === 'pending' && <Busy label={terrain.message ?? 'Analizuję teren…'} />}
      {terrain.status === 'unavailable' && <p className="notice">{terrain.message}</p>}
      {terrain.status === 'ok' && terrain.data && <TerrainResults analysis={terrain.data} {...sites} />}
      <Sources sources={terrain.sources} />
    </section>
  )
}

function TerrainResults({ analysis, selectedSiteId, onSelectSite }: SiteProps & { analysis: RetentionAnalysis }) {
  const { summary, sites, assumptions } = analysis
  const lidar = analysis.ditches.filter((d) => d.kind === 'lidar').length
  return (
    <>
      {sites.length === 0 ? (
        <p>
          Na tej działce nie ma zagłębień, które zatrzymają wodę: teren jest płaski albo woda
          spływa poza działkę.
        </p>
      ) : (
        <>
          <p>
            <strong>{fmt.m3Range(summary.retained_m3)}</strong> wody z jednego deszczu{' '}
            {assumptions.design_rain_mm} mm mogą zatrzymać zagłębienia terenu w{' '}
            {summary.site_count} {summary.site_count === 1 ? 'miejscu' : 'miejscach'}.
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
        </>
      )}
      <p className="muted fine">
        Rowy przy działce: {lidar} wykryte w modelu terenu LIDAR
        {analysis.ditches_checked
          ? `, ${analysis.ditches.length - lidar} z OpenStreetMap (© współtwórcy OSM, ODbL).`
          : '; mapa rowów OpenStreetMap była niedostępna.'}{' '}
        Siatka {assumptions.resolution_m} m, współczynnik spływu {assumptions.runoff_coeff.low}–
        {assumptions.runoff_coeff.high}; bez drenażu i wód gruntowych.
      </p>
    </>
  )
}

/** "Dane" tab: every data source's reading, then the report's limits. */
export function DataTab({ report, ...sites }: SiteProps & { report: AnalysisReport }) {
  const year = Number(report.analysis_date.slice(0, 4))
  const { diagnosis } = report
  return (
    <>
      <h2 className="print-only">Dane i dowody</h2>
      <EvidenceList diagnosis={diagnosis} />
      <EdoSection edo={report.edo} />
      <WaterSection water={report.water} year={year} />
      <SatelliteSection satellite={report.satellite} year={year} />
      <SoilSection soil={report.soil} />
      <TerrainSection terrain={report.terrain} {...sites} />
      <LandSection land={report.land} />
      <HydroSection hydro={report.hydro} />
      <section className="report-section" aria-labelledby="limits-heading">
        <h3 id="limits-heading">Ograniczenia raportu</h3>
        <Limitations diagnosis={diagnosis} />
      </section>
      <p className="muted fine no-print">Raport wygenerowano {fmt.dateTime(report.generated_at)}.</p>
    </>
  )
}
