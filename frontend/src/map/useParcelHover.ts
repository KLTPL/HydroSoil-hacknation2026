import type {
  FilterSpecification,
  GeoJSONSource,
  Map as MapLibreMap,
  MapMouseEvent,
} from 'maplibre-gl'
import { useEffect } from 'react'
import { ApiError, fetchParcelAt } from '../api'
import type { Parcel } from '../model'
import { contains } from './geometry'
import { HOVER_LAYERS, HOVER_SOURCE, PARCELS_MIN_ZOOM } from './style'

/** The cursor must rest this long before ULDK is asked; sweeping across the map asks nothing. */
const REST_MS = 250
/** Parcels already fetched; moving back over one outlines it with no request. */
const CACHE_SIZE = 40

type SourceData = Parameters<GeoJSONSource['setData']>[0]

const isExpected = (error: unknown) =>
  (error instanceof DOMException && error.name === 'AbortError') ||
  (error instanceof ApiError && error.status === 404)

/** Outlines the parcel under a resting cursor, once parcel borders are drawn on the map. */
export function useParcelHover(map: MapLibreMap | null, selectedId: string | null) {
  useEffect(() => {
    if (!map) return
    const source = map.getSource<GeoJSONSource>(HOVER_SOURCE)!
    const cache: Parcel[] = []
    let shown: string | null = null
    let timer: number | undefined
    // Requests are never cancelled when the cursor moves: an answer still fills the cache,
    // and cancelling made a parcel next to a known one never load. One request at a time;
    // the latest resting point waits for it.
    const unmount = new AbortController()
    let pending = false
    let queued: [number, number] | null = null
    let cursor: [number, number] | null = null

    const show = (parcel: Parcel | null) => {
      const id = parcel?.id ?? null
      if (id === shown) return
      shown = id
      const data = parcel
        ? { type: 'Feature' as const, geometry: parcel.geometry, properties: { id: parcel.id } }
        : { type: 'FeatureCollection' as const, features: [] }
      source.setData(data as unknown as SourceData)
    }
    const cached = (lon: number, lat: number) =>
      cache.find((parcel) => contains(parcel.geometry, lon, lat)) ?? null

    const lookup = async (lon: number, lat: number) => {
      if (pending) {
        queued = [lon, lat]
        return
      }
      pending = true
      try {
        const parcel = await fetchParcelAt(lon, lat, unmount.signal)
        cache.unshift(parcel)
        cache.length = Math.min(cache.length, CACHE_SIZE)
        // The cursor may have moved on while ULDK answered.
        if (cursor && contains(parcel.geometry, ...cursor)) show(parcel)
      } catch (error) {
        if (!isExpected(error)) throw error
      } finally {
        pending = false
      }
      const next = queued
      queued = null
      if (next && !cached(...next)) void lookup(...next)
    }

    const stop = () => {
      window.clearTimeout(timer)
      queued = null
      cursor = null
      show(null)
    }
    const onMove = (event: MapMouseEvent) => {
      window.clearTimeout(timer)
      if (map.getZoom() < PARCELS_MIN_ZOOM) return stop()
      const { lng, lat } = event.lngLat
      cursor = [lng, lat]
      const hit = cached(lng, lat)
      if (hit) {
        queued = null
        return show(hit)
      }
      show(null)
      timer = window.setTimeout(() => void lookup(lng, lat), REST_MS)
    }
    const onZoom = () => {
      if (map.getZoom() < PARCELS_MIN_ZOOM) stop()
    }

    map.on('mousemove', onMove)
    map.on('mouseout', stop)
    map.on('zoomend', onZoom)
    return () => {
      map.off('mousemove', onMove)
      map.off('mouseout', stop)
      map.off('zoomend', onZoom)
      stop()
      unmount.abort()
    }
  }, [map])

  // The picked parcel has its own yellow outline; never draw the hover one over it.
  useEffect(() => {
    if (!map) return
    const filter = ['!=', ['get', 'id'], selectedId ?? ''] as FilterSpecification
    for (const layer of HOVER_LAYERS) map.setFilter(layer, filter)
  }, [map, selectedId])
}
