import type { Map as MapLibreMap } from 'maplibre-gl'
import { useEffect } from 'react'
import type { RetentionAnalysis } from '../model'
import { frameClear } from './framing'
import { boxAround, points } from './geometry'
import { DITCHES_SOURCE, SITES_SOURCE } from './style'

/** The places and ditches of the open plan step. */
export interface MapFocus {
  siteIds: number[]
  ditchIds: number[]
}

/** Fades everything the open plan step does not use and frames what it does. */
export function useMapFocus(map: MapLibreMap | null, terrain: RetentionAnalysis | null, focus: MapFocus | null) {
  useEffect(() => {
    if (!map || !terrain) return
    const fadedSite = (id: number) => focus !== null && !focus.siteIds.includes(id)
    const fadedDitch = (id: number) => focus !== null && !focus.ditchIds.includes(id)
    for (const s of terrain.sites)
      map.setFeatureState({ source: SITES_SOURCE, id: s.id }, { faded: fadedSite(s.id) })
    for (const d of terrain.ditches)
      map.setFeatureState({ source: DITCHES_SOURCE, id: d.id }, { faded: fadedDitch(d.id) })
    // The numbered pins are DOM markers, outside the style.
    for (const pin of map.getContainer().querySelectorAll<HTMLElement>('.site-pin'))
      pin.classList.toggle('faded', fadedSite(Number(pin.dataset.site)))

    if (!focus) return
    const kept = [
      ...terrain.sites.filter((s) => focus.siteIds.includes(s.id)).flatMap((s) => points(s.geometry)),
      ...terrain.ditches.filter((d) => focus.ditchIds.includes(d.id)).flatMap((d) => d.geometry.coordinates),
    ]
    if (kept.length > 0) frameClear(map, boxAround(kept), 18)
  }, [map, terrain, focus])
}
