import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, fetchParcelAt, fetchRetention } from './api'
import { MapView } from './map/MapView'
import { Panel, type PanelState } from './panel/Panel'

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Nie udało się połączyć z serwerem. Spróbuj ponownie.'
}

export default function App() {
  const [state, setState] = useState<PanelState>({ status: 'idle' })
  const [selectedSiteId, setSelectedSiteId] = useState<number | null>(null)
  const inFlight = useRef<AbortController | null>(null)

  const pick = useCallback(async (lon: number, lat: number) => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setSelectedSiteId(null)
    setState({ status: 'locating' })
    window.history.replaceState(null, '', `#${lat.toFixed(5)},${lon.toFixed(5)}`)

    try {
      const parcel = await fetchParcelAt(lon, lat, controller.signal)
      setState({ status: 'parcel', parcel, analysis: { status: 'loading' } })
      try {
        const analysis = await fetchRetention(parcel.id, controller.signal)
        setState({ status: 'parcel', parcel, analysis: { status: 'done', analysis } })
      } catch (error) {
        if (controller.signal.aborted) return
        setState({ status: 'parcel', parcel, analysis: { status: 'error', message: errorMessage(error) } })
      }
    } catch (error) {
      if (controller.signal.aborted) return
      setState({ status: 'error', message: errorMessage(error) })
    }
  }, [])

  // Demo/share links: #52.70,18.36 opens the parcel at that point.
  useEffect(() => {
    const match = /^#(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)$/.exec(window.location.hash)
    if (match) void pick(Number(match[2]), Number(match[1]))
  }, [pick])

  const parcel = state.status === 'parcel' ? state.parcel : null
  const sites =
    state.status === 'parcel' && state.analysis.status === 'done' ? state.analysis.analysis.sites : []

  return (
    <div className="app">
      <MapView
        parcel={parcel}
        sites={sites}
        selectedSiteId={selectedSiteId}
        onPick={(lon, lat) => void pick(lon, lat)}
        onSelectSite={setSelectedSiteId}
      />
      <Panel state={state} selectedSiteId={selectedSiteId} onSelectSite={setSelectedSiteId} />
    </div>
  )
}
