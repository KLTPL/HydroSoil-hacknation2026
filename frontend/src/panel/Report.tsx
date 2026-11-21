import { useEffect, useState, type ReactNode } from 'react'
import * as fmt from '../format'
import type { AnalysisReport, ModuleResult, RetentionAnalysis } from '../model'
import { requestPrint } from '../print'
import { Busy } from './Busy'
import { CausesSection, EvidenceList, Limitations } from './DiagnosisSection'
import { EdoSection } from './EdoSection'
import { HydroSection, LandSection, SatelliteSection, SoilSection } from './FieldSections'
import { RecommendationsSection } from './RecommendationsSection'
import { ScenariosSection } from './ScenariosSection'
import { SiteCard } from './SiteCard'
import { Sources } from './Sources'
import { Verdict } from './Verdict'
import { WaterSection } from './WaterSection'

interface Props {
  report: AnalysisReport
  selectedSiteId: number | null
  onSelectSite: (id: number) => void
}

function More({ summary, hint, children }: { summary: string; hint: string; children: ReactNode }) {
  return (
    <details className="more">
      <summary>
        <span className="more-title">{summary}</span>
        <span className="more-hint">{hint}</span>
      </summary>
      <div className="more-body">{children}</div>
    </details>
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
      <h3 id="terrain-heading">Miejsca na wodę z modelu terenu LIDAR</h3>
      {terrain.status === 'pending' && <Busy label={terrain.message ?? 'Analizuję teren…'} />}
      {terrain.status === 'unavailable' && <p className="notice">{terrain.message}</p>}
      {terrain.status === 'ok' && terrain.data && (
        <TerrainResults analysis={terrain.data} selectedSiteId={selectedSiteId} onSelectSite={onSelectSite} />
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

/** Framing the map and waiting for its tiles takes a few seconds before the print dialog. */
function PrintButton() {
  const [preparing, setPreparing] = useState(false)
  useEffect(() => {
    const done = () => setPreparing(false)
    window.addEventListener('afterprint', done)
    return () => window.removeEventListener('afterprint', done)
  }, [])
  return (
    <button
      type="button"
      className="print-button no-print"
      aria-busy={preparing}
      onClick={() => {
        if (preparing) return
        setPreparing(true)
        requestPrint()
      }}
    >
      {preparing && <progress className="loading-spinner" aria-label="Przygotowuję PDF" />}
      {preparing ? 'Przygotowuję PDF…' : 'Zapisz PDF'}
    </button>
  )
}

export function Report({ report, selectedSiteId, onSelectSite }: Props) {
  const year = Number(report.analysis_date.slice(0, 4))
  const { diagnosis, terrain } = report
  const limits = diagnosis.missing_data.length + diagnosis.limitations.length
  return (
    <article className="report" aria-label="Raport">
      <header className="report-header">
        <div>
          <p className="eyebrow">Raport</p>
          <h2>
            {report.crop.name} · {fmt.longDate(report.analysis_date)}
          </h2>
          <p className="muted fine">Wygenerowano {fmt.dateTime(report.generated_at)}</p>
        </div>
        <PrintButton />
        <p className="print-only">
          Działka {report.parcel.number}, obręb {report.parcel.region}, gm.{' '}
          {report.parcel.commune}, {report.parcel.county}, woj. {report.parcel.voivodeship},{' '}
          {fmt.ha(report.parcel.area_ha)}. Identyfikator: {report.parcel.id}.
          <br />
          Raport online: {window.location.href}
        </p>
      </header>

      <Verdict diagnosis={diagnosis} water={report.water.data} />
      <CausesSection diagnosis={diagnosis} />
      <RecommendationsSection recommendations={report.recommendations} onSelectSite={onSelectSite} />
      <ScenariosSection water={report.water} />
      {terrain.status === 'pending' && (
        <p className="notice no-print" role="status">
          Model terenu LIDAR jeszcze się pobiera. Miejsca na wodę i symulacja ulewy pojawią się
          same, a plan uzupełni się o nie.
        </p>
      )}

      <More summary="Dane i dowody" hint="pogoda, satelita, gleba, teren, IMGW, EDO">
        <EvidenceList diagnosis={diagnosis} />
        <EdoSection edo={report.edo} />
        <WaterSection water={report.water} year={year} />
        <SatelliteSection satellite={report.satellite} year={year} />
        <SoilSection soil={report.soil} />
        <TerrainSection terrain={terrain} selectedSiteId={selectedSiteId} onSelectSite={onSelectSite} />
        <LandSection land={report.land} />
        <HydroSection hydro={report.hydro} />
      </More>
      <More summary="Ograniczenia raportu" hint={`${limits} ${fmt.plural(limits, "uwaga", "uwagi", "uwag")} o dokładności i brakach danych`}>
        <Limitations diagnosis={diagnosis} />
      </More>
    </article>
  )
}
