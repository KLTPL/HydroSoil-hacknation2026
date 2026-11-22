import { Marker, type GeoJSONSource, type Map as MapLibreMap } from 'maplibre-gl'
import { useEffect, useLayoutEffect, useRef } from 'react'
import { reliefUrl } from '../api'
import type { RetentionAnalysis } from '../model'
import { bounds, centre, viewPadding } from './geometry'
import type { BaseLayer } from './MapChrome'
import {
  DITCHES_SOURCE,
  FLOW_LAYER,
  FLOW_SOURCE,
  PHOTO_LAYERS,
  RELIEF_BEFORE,
  RELIEF_SOURCE,
  SHADED_LAYER,
  SITES_SOURCE,
} from './style'

type SourceData = Parameters<GeoJSONSource['setData']>[0]
const RELIEF_LAYER = 'relief'

function setData(map: MapLibreMap, source: string, features: unknown[]) {
  const data = { type: 'FeatureCollection', features } as unknown as SourceData
  map.getSource<GeoJSONSource>(source)!.setData(data)
}

/** Terrain results on the map: hollows, ditches and weirs, runoff lines, LIDAR relief. */
export function useTerrainLayers(
  map: MapLibreMap | null,
  terrain: RetentionAnalysis | null,
  selectedSiteId: number | null,
  base: BaseLayer,
  raining: boolean,
  onSelectSite: (id: number) => void,
) {
  const select = useRef(onSelectSite)
  useLayoutEffect(() => {
    select.current = onSelectSite
  })

  useEffect(() => {
    if (!map) return
    const sites = terrain?.sites ?? []
    setData(
      map,
      SITES_SOURCE,
      sites.map((s) => ({ type: 'Feature', id: s.id, geometry: s.geometry, properties: { kind: s.kind } })),
    )
    setData(
      map,
      DITCHES_SOURCE,
      (terrain?.ditches ?? []).flatMap((d) => [
        { type: 'Feature', geometry: d.geometry, properties: { id: d.id } },
        ...d.weirs.coordinates.map((point) => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: point },
          properties: { id: d.id },
        })),
      ]),
    )
    setData(
      map,
      FLOW_SOURCE,
      (terrain?.flow ?? []).map((f) => ({
        type: 'Feature',
        geometry: f.geometry,
        properties: { area: f.area_m2 },
      })),
    )
    // Numbered pins, so "miejsce nr 2" in the advice can be found on the map.
    const markers = sites.map((site) => {
      const pin = document.createElement('button')
      pin.type = 'button'
      pin.className = `site-pin kind-${site.kind}`
      pin.textContent = String(site.id)
      pin.dataset.site = String(site.id)
      pin.setAttribute('aria-label', `Miejsce na wodę nr ${site.id}`)
      pin.addEventListener('click', (event) => {
        event.stopPropagation()
        select.current(site.id)
      })
      return new Marker({ element: pin }).setLngLat(centre(site.geometry)).addTo(map)
    })
    return () => markers.forEach((m) => m.remove())
  }, [map, terrain])

  // LIDAR hollows tint (transparent elsewhere, feathered edges) under the parcel outline.
  useEffect(() => {
    if (!map || !terrain?.relief) return
    map.addSource(RELIEF_SOURCE, {
      type: 'image',
      url: reliefUrl(terrain.parcel_id, terrain.computed_at),
      coordinates: terrain.relief.corners as [
        [number, number],
        [number, number],
        [number, number],
        [number, number],
      ],
    })
    map.addLayer(
      {
        id: RELIEF_LAYER,
        type: 'raster',
        source: RELIEF_SOURCE,
        layout: { visibility: 'none' },
        paint: { 'raster-fade-duration': 0, 'raster-resampling': 'linear' },
      },
      RELIEF_BEFORE,
    )
    return () => {
      map.removeLayer(RELIEF_LAYER)
      map.removeSource(RELIEF_SOURCE)
    }
  }, [map, terrain])

  useEffect(() => {
    if (!map) return
    const relief = base === 'relief' && map.getLayer(RELIEF_LAYER) !== undefined
    const show = (on: boolean) => (on ? 'visible' : 'none')
    if (map.getLayer(RELIEF_LAYER)) map.setLayoutProperty(RELIEF_LAYER, 'visibility', show(relief))
    // The whole map switches: hillshade in place of the photo, hollows tinted on top.
    map.setLayoutProperty(SHADED_LAYER, 'visibility', show(relief))
    for (const id of PHOTO_LAYERS) map.setLayoutProperty(id, 'visibility', show(!relief))
    // Cadastral lines are blue too; keep them faint so they don't read as water.
    map.setPaintProperty(RELIEF_BEFORE, 'raster-opacity', relief ? 0.3 : 0.85)
    map.setLayoutProperty(FLOW_LAYER, 'visibility', relief || raining ? 'visible' : 'none')
    map.setPaintProperty(FLOW_LAYER, 'line-opacity', raining ? 0.5 : 0.8)
    // White reads on the photo, deep blue on the pale relief.
    map.setPaintProperty(FLOW_LAYER, 'line-color', relief ? '#0a3a8c' : '#e6f6ff')
  }, [map, terrain, base, raining])

  useEffect(() => {
    if (!map) return
    // Per key, so the plan step's fading (another key) stays.
    for (const s of terrain?.sites ?? [])
      map.setFeatureState({ source: SITES_SOURCE, id: s.id }, { selected: s.id === selectedSiteId })
    if (selectedSiteId == null) return
    const site = terrain?.sites.find((s) => s.id === selectedSiteId)
    if (site) map.fitBounds(bounds(site.geometry), { padding: viewPadding(120), maxZoom: 18 })
  }, [map, selectedSiteId, terrain])
}
