import { useEffect, useState } from 'react'
import { useAccountPanel } from './account/useAccountPanel'
import { MapView } from './map/MapView'
import { Panel } from './panel/Panel'
import { readHash, todayIso, useParcelReport } from './useParcelReport'

export default function App() {
  const { parcel, lookup, report, choose, pickAt, loadById, analyze } = useParcelReport()
  const [crop, setCrop] = useState(() => readHash().crop ?? '')
  const [date, setDate] = useState(() => readHash().date ?? todayIso())
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null)

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

  return (
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
        onPick={(lon, lat) => {
          setSelectedSiteId(null)
          account.close()
          void pickAt(lon, lat)
        }}
        onSelectSite={setSelectedSiteId}
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
  )
}
