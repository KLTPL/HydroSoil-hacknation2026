import type { Map as MapLibreMap } from 'maplibre-gl'
import { useEffect, useState } from 'react'
import { elevationTiles, fetchElevation } from '../api'

const DEM_SOURCE = 'lidar-dem'
const SHADE_SOURCE = 'lidar-dem-shade' // MapLibre advises a separate source for hillshade
const SHADE_LAYER = 'lidar-shade'
const PITCH = 62
const TURN_DEG = 25
const ZOOM_IN = 0.4 // tilting pushes the parcel away; come a little closer
const MOVE_MS = 2600
/** Exaggerate until the terrain spans about this many metres, so flat fields still show. */
const TARGET_RELIEF_M = 25
const MAX_EXAGGERATION = 12

export function exaggerationFor(reliefM: number): number {
  return Math.round(Math.min(MAX_EXAGGERATION, Math.max(1, TARGET_RELIEF_M / Math.max(reliefM, 0.1))))
}

/** 3D view of the analysed area from LIDAR: the field rises, the camera tilts and turns.
 * Returns the vertical exaggeration while on, null otherwise. */
export function useTerrain3d(map: MapLibreMap | null, parcelId: string | null, on: boolean): number | null {
  const [exaggeration, setExaggeration] = useState<number | null>(null)

  useEffect(() => {
    if (!map || !parcelId || !on) return
    const controller = new AbortController()
    let added = false
    fetchElevation(parcelId, controller.signal).then(({ bounds, relief_m }) => {
      const tiles = { type: 'raster-dem' as const, tiles: [elevationTiles(parcelId)], tileSize: 256, encoding: 'terrarium' as const, bounds, minzoom: 12, maxzoom: 16 }
      map.addSource(DEM_SOURCE, tiles)
      map.addSource(SHADE_SOURCE, tiles)
      map.addLayer(
        {
          id: SHADE_LAYER,
          type: 'hillshade',
          source: SHADE_SOURCE,
          paint: { 'hillshade-exaggeration': 0.6, 'hillshade-shadow-color': '#1a2630', 'hillshade-highlight-color': '#fff8e6' },
        },
        'kieg',
      )
      added = true
      const factor = exaggerationFor(relief_m)
      map.setTerrain({ source: DEM_SOURCE, exaggeration: factor })
      map.easeTo({
        pitch: PITCH,
        bearing: map.getBearing() - TURN_DEG,
        zoom: map.getZoom() + ZOOM_IN,
        duration: MOVE_MS,
      })
      setExaggeration(factor)
    }, (error: unknown) => {
      if (!controller.signal.aborted) throw error
    })
    return () => {
      controller.abort()
      setExaggeration(null)
      if (!added) return
      map.setTerrain(null)
      map.removeLayer(SHADE_LAYER)
      map.removeSource(DEM_SOURCE)
      map.removeSource(SHADE_SOURCE)
      map.easeTo({ pitch: 0, bearing: 0, duration: MOVE_MS / 2 })
    }
  }, [map, parcelId, on])

  return exaggeration
}
