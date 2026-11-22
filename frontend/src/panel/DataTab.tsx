import * as fmt from '../format'
import type { AnalysisReport, Diagnosis, ModuleResult, RetentionAnalysis } from '../model'
import { DataRow, RowGroup } from './DataRow'
import { EvidenceList, Limitations } from './DiagnosisSection'
import { EdoSection } from './EdoSection'
import { HydroSection, LandSection, SatelliteSection, SoilSection } from './FieldSections'
import { ModuleSection } from './ModuleSection'
import { SiteCard } from './SiteCard'
import { SourceVotes } from './SourceVotes'
import { WaterSection } from './WaterSection'

const CONFIDENCE = { high: 'wysoka', medium: 'średnia', low: 'niska' } as const

interface SiteProps {
  selectedSiteId: number | null
  onSelectSite: (id: number) => void
}

function TerrainSection({ terrain, ...sites }: SiteProps & { terrain: ModuleResult<RetentionAnalysis> }) {
  return (
    <ModuleSection
      id="terrain"
      title="Teren LIDAR: miejsca na wodę"
      module={terrain}
      summary={({ summary }) =>
        summary.site_count === 0
          ? 'brak zagłębień'
          : `${summary.site_count} ${fmt.plural(summary.site_count, 'miejsce', 'miejsca', 'miejsc')}, ${fmt.m3Range(summary.retained_m3)}`
      }
    >
      {(analysis) => <TerrainResults analysis={analysis} {...sites} />}
    </ModuleSection>
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

/** How the verdict was reached: each source's reading, then the evidence lines. */
function BasisRow({ diagnosis }: { diagnosis: Diagnosis }) {
  return (
    <DataRow id="basis" title="Na czym opiera się ocena" summary={`pewność ${CONFIDENCE[diagnosis.confidence]}`}>
      {diagnosis.signals.length > 0 && <SourceVotes signals={diagnosis.signals} />}
      <EvidenceList diagnosis={diagnosis} />
    </DataRow>
  )
}

interface Props extends SiteProps {
  report: AnalysisReport
  openRow: string | null
  onOpenRow: (id: string | null) => void
}

/** "Dane" tab: one row per data source with its key reading, then the report's limits. */
export function DataTab({ report, openRow, onOpenRow, ...sites }: Props) {
  const year = Number(report.analysis_date.slice(0, 4))
  const { diagnosis } = report
  const limits = diagnosis.missing_data.length + diagnosis.limitations.length
  return (
    <RowGroup open={openRow} onOpenChange={onOpenRow}>
      <div className="data-rows">
        <h2 className="print-only">Dane i dowody</h2>
        <BasisRow diagnosis={diagnosis} />
        <WaterSection water={report.water} year={year} />
        <SatelliteSection satellite={report.satellite} year={year} />
        <SoilSection soil={report.soil} />
        <TerrainSection terrain={report.terrain} {...sites} />
        <EdoSection edo={report.edo} />
        <HydroSection hydro={report.hydro} />
        <LandSection land={report.land} />
        <DataRow
          id="limits"
          title="Ograniczenia raportu"
          summary={`${limits} ${fmt.plural(limits, 'uwaga', 'uwagi', 'uwag')}`}
        >
          <Limitations diagnosis={diagnosis} />
        </DataRow>
      </div>
      <p className="muted fine no-print">Raport wygenerowano {fmt.dateTime(report.generated_at)}.</p>
    </RowGroup>
  )
}
