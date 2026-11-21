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
  computed_at: string
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

export interface Crop {
  id: string
  name: string
}

export interface DataSource {
  name: string
  url: string
  license: string
  retrieved: 'live' | 'cached'
  retrieved_at: string
}

export interface ModuleResult<T> {
  status: 'ok' | 'pending' | 'unavailable'
  message: string | null
  data: T | null
  sources: DataSource[]
  duration_ms: number
}

export interface AnalysisReport {
  parcel: Parcel
  crop: Crop
  analysis_date: string
  generated_at: string
  terrain: ModuleResult<RetentionAnalysis>
}

const query = (params: Record<string, string>) => new URLSearchParams(params).toString()

export const fetchCrops = () => getJson<Crop[]>('/api/crops')

export const searchParcels = (q: string, signal?: AbortSignal) =>
  getJson<Parcel[]>(`/api/parcels/search?${query({ q })}`, signal)

export const fetchParcelAt = (lon: number, lat: number, signal?: AbortSignal) =>
  getJson<Parcel>(`/api/parcels/at?${query({ lon: String(lon), lat: String(lat) })}`, signal)

export const fetchAnalysis = (parcelId: string, crop: string, date: string, signal?: AbortSignal) =>
  getJson<AnalysisReport>(`/api/analysis?${query({ parcel_id: parcelId, crop, date })}`, signal)

export const fetchTerrain = (parcelId: string, signal?: AbortSignal) =>
  getJson<ModuleResult<RetentionAnalysis>>(`/api/terrain?${query({ parcel_id: parcelId })}`, signal)
