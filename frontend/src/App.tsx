import { useEffect, useMemo, useState } from 'react'
import { useAccountPanel } from './account/useAccountPanel'
import type { Place } from './geocode'
import { MapView } from './map/MapView'
import type { Recommendation } from './model'
import { Panel } from './panel/Panel'
import { ReportViewContext, useReportViewState } from './panel/reportView'
import { readHash, todayIso, useParcelReport } from './useParcelReport'

export default function App() {
  const { parcel, lookup, report, choose, pickAt, loadById, analyze } = useParcelReport()
  const [crop, setCrop] = useState(() => readHash().crop ?? '')
  const [date, setDate] = useState(() => readHash().date ?? todayIso())
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null)
  const [place, setPlace] = useState<Place | null>(null)

  // Share/demo links open the parcel and, when crop and date are given, run the analysis.
  useEffect(() => {
    const { parcelId, crop: hashCrop, date: hashDate } = readHash()
    if (!parcelId) return
    void loadById(parcelId).then((found) => {
      if (found && hashCrop) void analyze(found, hashCrop, hashDate ?? todayIso())
    })
  }, [loadById, analyze])

  const account = useAccountPanel({
    parcel,
    crop,
    date,
    selectedSiteId,
    onDateChange: setDate,
    onSelectSite: setSelectedSiteId,
    onOpenSaved: (saved) => {
      setCrop(saved.crop)
      setSelectedSiteId(null)
      void loadById(saved.parcel_id).then((found) => {
        if (found) void analyze(found, saved.crop, date)
      })
    },
  })
  // An archived report opened from the account replaces the live one on the map too.
  const shown = account.archived ?? (report.status === 'done' ? report.report : null)
  const terrain = shown ? shown.terrain.data : null

  const view = useReportViewState(shown)
  const recommendations = useMemo(() => shown?.recommendations ?? [], [shown])
  const openStep = recommendations.find((r) => r.key === view.step)
  const focus = useMemo(
    () =>
      openStep && openStep.site_ids.length + openStep.ditch_ids.length > 0
        ? { siteIds: openStep.site_ids, ditchIds: openStep.ditch_ids }
        : null,
    [openStep],
  )
  // A place or ditch clicked on the map opens the plan step that uses it; the open step wins
  // when several do.
  const showStepWith = (uses: (r: Recommendation) => boolean) => {
    const step = openStep && uses(openStep) ? openStep : recommendations.find(uses)
    if (step) view.showStep(step.key)
  }

  return (
    <ReportViewContext value={view}>
      <div className="app">
        {/* The map comes first in the DOM (print order); keyboard users jump past its controls.
            No href="#panel": the hash carries the share link. */}
        <a
          className="skip-link"
          href="#"
          onClick={(event) => {
            event.preventDefault()
            document.getElementById('panel')?.focus()
          }}
        >
          Przejdź do analizy
        </a>
        <MapView
          parcel={account.archived?.parcel ?? parcel}
          terrain={terrain}
          selectedSiteId={selectedSiteId}
          place={place}
          focus={focus}
          onPick={(lon, lat) => {
            setSelectedSiteId(null)
            account.close()
            void pickAt(lon, lat)
          }}
          onSelectSite={(id) => {
            setSelectedSiteId(id)
            showStepWith((r) => r.site_ids.includes(id))
          }}
          onSelectDitch={(id) => showStepWith((r) => r.ditch_ids.includes(id))}
        />
        <Panel
          parcel={parcel}
          lookup={lookup}
          report={report}
          crop={crop}
          date={date}
          selectedSiteId={selectedSiteId}
          onChooseParcel={(p) => {
            setSelectedSiteId(null)
            choose(p)
          }}
          onPlace={setPlace}
          onCropChange={setCrop}
          onDateChange={setDate}
          onAnalyze={() => {
            if (!parcel) return
            setSelectedSiteId(null)
            void analyze(parcel, crop, date)
          }}
          onSelectSite={setSelectedSiteId}
          {...account.slots}
        />
      </div>
    </ReportViewContext>
  )
}
