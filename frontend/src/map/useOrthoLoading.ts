import type { Map as MapLibreMap, MapSourceDataEvent } from 'maplibre-gl'
import { useEffect, useState } from 'react'
import { ORTHO_SOURCE, STREET_MAP_MAX_ZOOM } from './style'

/** True while the orthophoto is still loading at zooms where it is the only base map. */
export function useOrthoLoading(map: MapLibreMap | null): boolean {
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!map) return
    const update = () =>
      setLoading(map.getZoom() >= STREET_MAP_MAX_ZOOM && !map.isSourceLoaded(ORTHO_SOURCE))
    const onSourceData = (event: MapSourceDataEvent) => {
      if (event.sourceId === ORTHO_SOURCE) update()
    }
    map.on('sourcedata', onSourceData)
    map.on('sourcedataloading', onSourceData)
    map.on('moveend', update)
    update()
    return () => {
      map.off('sourcedata', onSourceData)
      map.off('sourcedataloading', onSourceData)
      map.off('moveend', update)
    }
  }, [map])

  return loading
}
