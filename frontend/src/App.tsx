import { useEffect, useState } from 'react'
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

  const terrain = report.status === 'done' ? report.report.terrain.data : null

  return (
    <div className="app">
      <MapView
        parcel={parcel}
        terrain={terrain}
        selectedSiteId={selectedSiteId}
        onPick={(lon, lat) => {
          setSelectedSiteId(null)
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
      />
    </div>
  )
}
