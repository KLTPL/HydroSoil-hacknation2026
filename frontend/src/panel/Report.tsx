import { useEffect, useState } from 'react'
import * as fmt from '../format'
import type { AnalysisReport } from '../model'
import { requestPrint } from '../print'
import { DataTab } from './DataTab'
import { CausesSection } from './DiagnosisSection'
import { RecommendationsSection } from './RecommendationsSection'
import { ReportTabs } from './ReportTabs'
import { ScenariosSection } from './ScenariosSection'
import { Verdict } from './Verdict'

interface Props {
  report: AnalysisReport
  selectedSiteId: number | null
  onSelectSite: (id: number) => void
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
      className="print-button quiet no-print"
      aria-busy={preparing}
      onClick={() => {
        if (preparing) return
        setPreparing(true)
        requestPrint()
      }}
    >
      {preparing && <progress className="loading-spinner" aria-hidden="true" />}
      {preparing ? 'Przygotowuję PDF…' : 'Zapisz PDF'}
    </button>
  )
}

type TabId = 'assessment' | 'plan' | 'data'

export function Report({ report, selectedSiteId, onSelectSite }: Props) {
  const { diagnosis, recommendations } = report
  const [tab, setTab] = useState<TabId>('assessment')
  const [dataRow, setDataRow] = useState<string | null>(null)
  const steps = recommendations.length
  return (
    <article className="report" aria-label="Raport">
      <header className="report-header print-only">
        <p className="eyebrow">Raport</p>
        <h2>
          {report.crop.name} · {fmt.longDate(report.analysis_date)}
        </h2>
        <p>
          Wygenerowano {fmt.dateTime(report.generated_at)}. Działka {report.parcel.number}, obręb{' '}
          {report.parcel.region}, gm. {report.parcel.commune}, {report.parcel.county}, woj.{' '}
          {report.parcel.voivodeship}, {fmt.ha(report.parcel.area_ha)}. Identyfikator:{' '}
          {report.parcel.id}.
          <br />
          Raport online: {window.location.href}
        </p>
      </header>
      <ReportTabs
        active={tab}
        onSelect={setTab}
        actions={<PrintButton />}
        tabs={[
          {
            id: 'assessment',
            label: 'Ocena',
            content: (
              <>
                <Verdict diagnosis={diagnosis} water={report.water.data} onShowData={() => {
                    setDataRow('basis')
                    setTab('data')
                  }}
                />
                <CausesSection diagnosis={diagnosis} />
                <ScenariosSection water={report.water} threshold={diagnosis.stress_threshold_pct} />
                {steps > 0 && (
                  <button type="button" className="next-tab no-print" onClick={() => setTab('plan')}>
                    Co z tym zrobić: plan działań, {steps} {fmt.plural(steps, 'krok', 'kroki', 'kroków')}
                  </button>
                )}
              </>
            ),
          },
          {
            id: 'plan',
            label: (
              <>
                Plan <span className="tab-count">{steps}</span>
              </>
            ),
            content: (
              <>
                {report.terrain.status === 'pending' && (
                  <p className="notice no-print" role="status">
                    Model terenu LIDAR jeszcze się pobiera. Miejsca na wodę i symulacja ulewy
                    pojawią się same, a plan uzupełni się o nie.
                  </p>
                )}
                <RecommendationsSection recommendations={recommendations} onSelectSite={onSelectSite} />
              </>
            ),
          },
          {
            id: 'data',
            label: 'Dane',
            content: (
              <DataTab
                report={report}
                openRow={dataRow}
                onOpenRow={setDataRow}
                selectedSiteId={selectedSiteId}
                onSelectSite={onSelectSite}
              />
            ),
          },
        ]}
      />
    </article>
  )
}
