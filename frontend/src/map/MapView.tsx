import {
  GeolocateControl,
  Map as MapLibreMap,
  NavigationControl,
  setWorkerUrl,
  type GeoJSONSource,
  type LngLatBoundsLike,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
// The production bundle does not emit MapLibre's worker by itself; ship it as an asset.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { DitchWeirs, Geometry, Parcel, RetentionSite } from '../api'
import { PRINT_EVENT } from '../print'
import { DITCHES_SOURCE, mapStyle, PARCEL_SOURCE, SITES_FILL_LAYER, SITES_SOURCE } from './style'

interface Props {
  parcel: Parcel | null
  sites: RetentionSite[]
  ditches: DitchWeirs[]
  selectedSiteId: number | null
  onPick: (lon: number, lat: number) => void
  onSelectSite: (id: number) => void
}

type SourceData = Parameters<GeoJSONSource['setData']>[0]

setWorkerUrl(workerUrl)

const POLAND_CENTER: [number, number] = [19.3, 52.1]

function bounds(geometry: Geometry): LngLatBoundsLike {
  const points = geometry.coordinates.flat(geometry.type === 'Polygon' ? 1 : 2) as number[][]
  const lons = points.map((p) => p[0])
  const lats = points.map((p) => p[1])
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)]
}

export function MapView({ parcel, sites, ditches, selectedSiteId, onPick, onSelectSite }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const loaded = useRef<Promise<void> | null>(null)
  // Handlers change every render; the map listeners read the latest through refs.
  const handlers = useRef({ onPick, onSelectSite })
  useLayoutEffect(() => {
    handlers.current = { onPick, onSelectSite }
  })

  useEffect(() => {
    const map = new MapLibreMap({
      container: container.current!,
      style: mapStyle,
      center: POLAND_CENTER,
      zoom: 6,
      maxZoom: 19,
      // Keeps the last frame readable, so the map can be copied into the printed report.
      canvasContextAttributes: { preserveDrawingBuffer: true },
    })
    mapRef.current = map
    loaded.current = new Promise((resolve) => map.once('load', () => resolve()))

    map.addControl(new NavigationControl(), 'top-left')
    const geolocate = new GeolocateControl({
      positionOptions: { enableHighAccuracy: true },
      fitBoundsOptions: { maxZoom: 16 },
    })
    map.addControl(geolocate, 'top-left')
    geolocate.on('geolocate', (position) =>
      handlers.current.onPick(position.coords.longitude, position.coords.latitude),
    )

    map.on('click', (event) => {
      const hit = map.queryRenderedFeatures(event.point, { layers: [SITES_FILL_LAYER] })[0]
      if (hit?.id != null) handlers.current.onSelectSite(Number(hit.id))
      else handlers.current.onPick(event.lngLat.lng, event.lngLat.lat)
    })
    map.on('mouseenter', SITES_FILL_LAYER, () => (map.getCanvas().style.cursor = 'pointer'))
    map.on('mouseleave', SITES_FILL_LAYER, () => (map.getCanvas().style.cursor = ''))

    return () => map.remove()
  }, [])

  // Printing: frame the parcel, wait for tiles, snapshot the canvas, then print.
  const [snapshot, setSnapshot] = useState<string | null>(null)
  const printParcel = useRef(parcel)
  useLayoutEffect(() => {
    printParcel.current = parcel
  })
  useEffect(() => {
    const map = mapRef.current!
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
  }, [])

  useEffect(() => {
    const map = mapRef.current!
    void loaded.current!.then(() => {
      const data = parcel
        ? { type: 'Feature' as const, geometry: parcel.geometry, properties: {} }
        : { type: 'FeatureCollection' as const, features: [] }
      map.getSource<GeoJSONSource>(PARCEL_SOURCE)!.setData(data as unknown as SourceData)
      if (parcel) map.fitBounds(bounds(parcel.geometry), { padding: 60, maxZoom: 17 })
    })
  }, [parcel])

  useEffect(() => {
    const map = mapRef.current!
    void loaded.current!.then(() => {
      const features = sites.map((s) => ({
        type: 'Feature' as const,
        id: s.id,
        geometry: s.geometry,
        properties: { id: s.id, kind: s.kind },
      }))
      const data = { type: 'FeatureCollection' as const, features }
      map.getSource<GeoJSONSource>(SITES_SOURCE)!.setData(data as unknown as SourceData)
    })
  }, [sites])

  useEffect(() => {
    const map = mapRef.current!
    void loaded.current!.then(() => {
      const features = ditches.flatMap((d) => [
        { type: 'Feature' as const, geometry: d.geometry, properties: { id: d.id } },
        ...d.weirs.coordinates.map((point) => ({
          type: 'Feature' as const,
          geometry: { type: 'Point' as const, coordinates: point },
          properties: { id: d.id },
        })),
      ])
      const data = { type: 'FeatureCollection' as const, features }
      map.getSource<GeoJSONSource>(DITCHES_SOURCE)!.setData(data as unknown as SourceData)
    })
  }, [ditches])

  useEffect(() => {
    const map = mapRef.current!
    void loaded.current!.then(() => {
      map.removeFeatureState({ source: SITES_SOURCE })
      if (selectedSiteId == null) return
      map.setFeatureState({ source: SITES_SOURCE, id: selectedSiteId }, { selected: true })
      const site = sites.find((s) => s.id === selectedSiteId)
      if (site) map.fitBounds(bounds(site.geometry), { padding: 120, maxZoom: 18 })
    })
  }, [selectedSiteId, sites])

  return (
    <>
      <div ref={container} className="map" aria-label="Mapa działek" role="region" />
      {snapshot && (
        <figure className="print-map">
          <img src={snapshot} alt="Mapa działki z miejscami retencji, rowami i zastawkami" />
          <figcaption>
            Granica działki (żółta), miejsca zatrzymania wody (niebieskie), rowy (turkusowe
            przerywane), proponowane zastawki (czerwone punkty). Podkład: ortofotomapa GUGiK.
          </figcaption>
        </figure>
      )}
    </>
  )
}
