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
import type { Place } from '../geocode'
import type { Parcel, RetentionAnalysis } from '../model'
import { PRINT_EVENT } from '../print'
import { frameClear } from './framing'
import { bounds, viewPadding } from './geometry'
import { LayerSwitch, Legend, type BaseLayer } from './MapChrome'
import { RainControl } from './RainControl'
import {
  DITCHES_LINE_LAYER,
  mapStyle,
  PARCEL_SOURCE,
  PARCELS_MIN_ZOOM,
  SITES_FILL_LAYER,
  WEIRS_LAYER,
} from './style'
import { useMapFocus, type MapFocus } from './useMapFocus'
import { useOrthoLoading } from './useOrthoLoading'
import { useParcelHover } from './useParcelHover'
import { useTerrainLayers } from './useTerrainLayers'

interface Props {
  parcel: Parcel | null
  terrain: RetentionAnalysis | null
  selectedSiteId: number | null
  /** A searched town or address; each new object flies the map there. */
  place: Place | null
  /** The open plan step's places and ditches; the rest of the terrain fades. */
  focus: MapFocus | null
  onPick: (lon: number, lat: number) => void
  onSelectSite: (id: number) => void
  onSelectDitch: (id: number) => void
}

const CLICKABLE = [SITES_FILL_LAYER, DITCHES_LINE_LAYER, WEIRS_LAYER]

type SourceData = Parameters<GeoJSONSource['setData']>[0]

setWorkerUrl(workerUrl)

// West, south, east, north; framed beside the panel so the whole country stays visible.
const POLAND_BOUNDS: [number, number, number, number] = [14.1, 49.0, 24.2, 54.9]

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

export function MapView(props: Props) {
  const { parcel, terrain, selectedSiteId, place, focus, onPick, onSelectSite, onSelectDitch } = props
  const container = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<MapLibreMap | null>(null)
  const [base, setBase] = useState<BaseLayer>('photo')
  const [raining, setRaining] = useState(false)
  // Handlers change every render; the map listeners read the latest through refs.
  const handlers = useRef({ onPick, onSelectSite, onSelectDitch })
  useLayoutEffect(() => {
    handlers.current = { onPick, onSelectSite, onSelectDitch }
  })

  useEffect(() => {
    const instance = new MapLibreMap({
      container: container.current!,
      style: mapStyle,
      bounds: POLAND_BOUNDS,
      fitBoundsOptions: { padding: viewPadding(20) },
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
      const [hit] = instance.queryRenderedFeatures(event.point, { layers: CLICKABLE })
      if (hit?.layer.id === SITES_FILL_LAYER) handlers.current.onSelectSite(Number(hit.id))
      else if (hit) handlers.current.onSelectDitch(Number(hit.properties.id))
      // Zoomed out, a click cannot aim at one parcel: zoom in until parcel borders show.
      else if (instance.getZoom() < PARCELS_MIN_ZOOM)
        instance.flyTo({ center: event.lngLat, zoom: PARCELS_MIN_ZOOM + 1 })
      else handlers.current.onPick(event.lngLat.lng, event.lngLat.lat)
    })
    instance.on('mouseenter', CLICKABLE, () => (instance.getCanvas().style.cursor = 'pointer'))
    instance.on('mouseleave', CLICKABLE, () => (instance.getCanvas().style.cursor = ''))
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

  useEffect(() => {
    if (!map || !place) return
    // An offset, not `padding`: flyTo keeps its padding, and later fitBounds calls add theirs to it.
    const pad = viewPadding()
    const offset: [number, number] = [(pad.left - pad.right) / 2, (pad.top - pad.bottom) / 2]
    map.flyTo({ center: [place.lon, place.lat], zoom: place.zoom, offset })
  }, [map, place])

  // Once terrain results arrive, reframe the parcel clear of the rain card and legend.
  const hasTerrain = terrain !== null
  useEffect(() => {
    if (!map || !hasTerrain || !printParcel.current) return
    frameClear(map, bounds(printParcel.current.geometry), 17)
  }, [map, hasTerrain])

  useTerrainLayers(map, terrain, selectedSiteId, base, raining, onSelectSite)
  // After the terrain layers: framing the step wins over framing a single selected place.
  useMapFocus(map, terrain, focus)
  useParcelHover(map, parcel?.id ?? null)
  const orthoLoading = useOrthoLoading(map)

  return (
    <div className="map-stage">
      <div ref={container} className="map" aria-label="Mapa działek" role="region" />
      {orthoLoading && (
        <p className="map-loading glass" role="status">
          Ładowanie…
        </p>
      )}
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
