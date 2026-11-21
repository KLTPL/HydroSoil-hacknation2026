import {
  GeolocateControl,
  Map as MapLibreMap,
  NavigationControl,
  setWorkerUrl,
  type GeoJSONSource,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
// The production bundle does not emit MapLibre's worker by itself; ship it as an asset.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { Parcel, RetentionAnalysis } from '../model'
import { PRINT_EVENT } from '../print'
import { bounds, viewPadding } from './geometry'
import { LayerSwitch, Legend, type BaseLayer } from './MapChrome'
import { RainControl } from './RainControl'
import { mapStyle, PARCEL_SOURCE, SITES_FILL_LAYER } from './style'
import { useTerrainLayers } from './useTerrainLayers'

interface Props {
  parcel: Parcel | null
  terrain: RetentionAnalysis | null
  selectedSiteId: number | null
  onPick: (lon: number, lat: number) => void
  onSelectSite: (id: number) => void
}

type SourceData = Parameters<GeoJSONSource['setData']>[0]

setWorkerUrl(workerUrl)

const POLAND_CENTER: [number, number] = [19.3, 52.1]

// MapLibre labels its controls in English by default.
const LOCALE = {
  'Map.Title': 'Mapa',
  'NavigationControl.ZoomIn': 'Przybliż',
  'NavigationControl.ZoomOut': 'Oddal',
  'NavigationControl.ResetBearing': 'Obróć mapę na północ',
  'GeolocateControl.FindMyLocation': 'Pokaż moją lokalizację i wybierz działkę',
  'GeolocateControl.LocationNotAvailable': 'Lokalizacja niedostępna',
  'AttributionControl.ToggleAttribution': 'Pokaż lub ukryj źródła mapy',
  'AttributionControl.MapFeedback': 'Zgłoś błąd mapy',
  'LogoControl.Title': 'Logo MapLibre',
}

export function MapView({ parcel, terrain, selectedSiteId, onPick, onSelectSite }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<MapLibreMap | null>(null)
  const [base, setBase] = useState<BaseLayer>('photo')
  const [raining, setRaining] = useState(false)
  // Handlers change every render; the map listeners read the latest through refs.
  const handlers = useRef({ onPick, onSelectSite })
  useLayoutEffect(() => {
    handlers.current = { onPick, onSelectSite }
  })

  useEffect(() => {
    const instance = new MapLibreMap({
      container: container.current!,
      style: mapStyle,
      center: POLAND_CENTER,
      zoom: 6,
      maxZoom: 19,
      locale: LOCALE,
      // Keeps the last frame readable, so the map can be copied into the printed report.
      canvasContextAttributes: { preserveDrawingBuffer: true },
    })
    instance.addControl(new NavigationControl(), 'top-left')
    const geolocate = new GeolocateControl({
      positionOptions: { enableHighAccuracy: true },
      fitBoundsOptions: { maxZoom: 16 },
    })
    instance.addControl(geolocate, 'top-left')
    geolocate.on('geolocate', (position) =>
      handlers.current.onPick(position.coords.longitude, position.coords.latitude),
    )
    instance.on('click', (event) => {
      const hit = instance.queryRenderedFeatures(event.point, { layers: [SITES_FILL_LAYER] })[0]
      if (hit?.id != null) handlers.current.onSelectSite(Number(hit.id))
      else handlers.current.onPick(event.lngLat.lng, event.lngLat.lat)
    })
    instance.on('mouseenter', SITES_FILL_LAYER, () => (instance.getCanvas().style.cursor = 'pointer'))
    instance.on('mouseleave', SITES_FILL_LAYER, () => (instance.getCanvas().style.cursor = ''))
    instance.once('load', () => setMap(instance))
    return () => instance.remove()
  }, [])

  // Printing: frame the parcel, wait for tiles, snapshot the canvas, then print.
  const [snapshot, setSnapshot] = useState<string | null>(null)
  const printParcel = useRef(parcel)
  useLayoutEffect(() => {
    printParcel.current = parcel
  })
  useEffect(() => {
    if (!map) return
    const capture = () => setSnapshot(map.getCanvas().toDataURL('image/png'))
    const onPrint = () => {
      const target = printParcel.current
      if (target) map.fitBounds(bounds(target.geometry), { padding: 40, maxZoom: 18, duration: 0 })
      map.once('idle', () => {
        capture()
        // Let React swap in the snapshot before the print dialog freezes the page.
        window.setTimeout(() => window.print(), 100)
      })
      map.triggerRepaint()
    }
    window.addEventListener(PRINT_EVENT, onPrint)
    window.addEventListener('beforeprint', capture) // Ctrl+P: current view
    return () => {
      window.removeEventListener(PRINT_EVENT, onPrint)
      window.removeEventListener('beforeprint', capture)
    }
  }, [map])

  useEffect(() => {
    if (!map) return
    const data = parcel
      ? { type: 'Feature' as const, geometry: parcel.geometry, properties: {} }
      : { type: 'FeatureCollection' as const, features: [] }
    map.getSource<GeoJSONSource>(PARCEL_SOURCE)!.setData(data as unknown as SourceData)
    if (parcel) map.fitBounds(bounds(parcel.geometry), { padding: viewPadding(), maxZoom: 17 })
  }, [map, parcel])

  // Once terrain results arrive, reframe the parcel clear of the rain card.
  const hasTerrain = terrain !== null
  useEffect(() => {
    if (!map || !hasTerrain || !printParcel.current) return
    const card = document.querySelector('.rain-control')?.getBoundingClientRect()
    const padding = viewPadding()
    if (card && !window.matchMedia('(width < 720px)').matches) padding.bottom += card.height * 0.6
    map.fitBounds(bounds(printParcel.current.geometry), { padding, maxZoom: 17 })
  }, [map, hasTerrain])

  useTerrainLayers(map, terrain, selectedSiteId, base, raining, onSelectSite)

  return (
    <div className="map-stage">
      <div ref={container} className="map" aria-label="Mapa działek" role="region" />
      {terrain && parcel && (
        <div className="map-overlay">
          <LayerSwitch value={base} onChange={setBase} hasRelief={terrain.relief !== null} />
          <Legend terrain={terrain} base={base} />
          {map && terrain.flow.length > 0 && (
            <RainControl
              map={map}
              terrain={terrain}
              areaHa={parcel.area_ha}
              onRainingChange={setRaining}
            />
          )}
        </div>
      )}
      {snapshot && (
        <figure className="print-map">
          <img src={snapshot} alt="Mapa działki z miejscami retencji, rowami i zastawkami" />
          <figcaption>
            Granica działki (żółta), miejsca zatrzymania wody (niebieskie), rowy (turkusowe
            przerywane), proponowane zastawki (różowe punkty). Podkład: ortofotomapa GUGiK.
          </figcaption>
        </figure>
      )}
    </div>
  )
}
