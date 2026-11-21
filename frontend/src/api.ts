// Mirrors backend/src/retencja_api/models.py.

/** GeoJSON geometry in WGS84 (Polygon or MultiPolygon from the backend). */
export interface Geometry {
  type: 'Polygon' | 'MultiPolygon'
  coordinates: number[][][] | number[][][][]
}

export interface Parcel {
  id: string
  voivodeship: string
  county: string
  commune: string
  region: string
  number: string
  area_ha: number
  geometry: Geometry
}

export interface Range {
  low: number
  high: number
}

export type SiteKind = 'pond' | 'wet_depression'

export interface RetentionSite {
  id: number
  kind: SiteKind
  area_m2: number
  max_depth_m: number
  storage_m3: number
  catchment_ha: number
  runoff_m3: Range
  retained_m3: Range
  parcel_share: number
  geometry: Geometry
}

export interface RetentionAnalysis {
  parcel_id: string
  summary: { site_count: number; storage_m3: number; retained_m3: Range }
  sites: RetentionSite[]
  assumptions: {
    dem_source: string
    resolution_m: number
    design_rain_mm: number
    runoff_coeff: Range
    min_depth_m: number
    min_area_m2: number
  }
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, body?.detail ?? `Błąd serwera (${response.status})`)
  }
  return response.json() as Promise<T>
}

export function fetchParcelAt(lon: number, lat: number, signal?: AbortSignal) {
  const params = new URLSearchParams({ lon: String(lon), lat: String(lat) })
  return getJson<Parcel>(`/api/parcels/at?${params}`, signal)
}

export function fetchRetention(parcelId: string, signal?: AbortSignal) {
  const params = new URLSearchParams({ parcel_id: parcelId })
  return getJson<RetentionAnalysis>(`/api/retention?${params}`, signal)
}
