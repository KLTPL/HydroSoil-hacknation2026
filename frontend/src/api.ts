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

export interface YearValue {
  year: number
  value: number
}

/** A value on the analysis date against the same date in earlier years. */
export interface Comparison {
  value: number
  normal: number
  rank: number // 1 = lowest
  years: number
  history: YearValue[]
}

export interface SoilLayer {
  depth: string
  clay_pct: number
  sand_pct: number
  silt_pct: number
  organic_carbon_pct: number
}

export interface SoilProfile {
  texture: string
  category: 'I' | 'II' | 'III' | 'IV'
  category_label: string
  awc_mm_per_m: number
  organic_carbon_pct: number
  layers: SoilLayer[]
  resolution_m: number
  assumed: boolean
}

export interface RiskMonth {
  month: number
  years_with_stress: number
  years: number
  mean_stress_days: number
}

export interface WaterBalance {
  window: {
    start: string
    end: string
    precipitation_mm: Comparison
    et0_mm: Comparison
    kbw_mm: Comparison
    hot_days: Comparison
  }
  in_season: boolean
  kc: number
  taw_mm: number
  raw_mm: number
  available_pct: Comparison
  stress_days_30: number
  reanalysis_soil_moisture: Comparison | null
  soil_moisture_source: string
  risk_calendar: RiskMonth[]
  critical_stage: string
  grid_lat: number
  grid_lon: number
}

export interface VegetationObservation {
  year: number
  date: string
  ndvi: number
  ndmi: number
  clear_pct: number
}

export interface VegetationState {
  current: VegetationObservation | null
  history: VegetationObservation[]
  ndvi: Comparison | null
  ndmi: Comparison | null
  window_days: number
  missing_years: number[]
}

export interface HydroWarning {
  number: string
  event: string
  probability_pct: number
  valid_from: string
  valid_to: string | null
  office: string
  area: string
  description: string
}

export interface HydroStatus {
  voivodeship: string
  drought_warnings: HydroWarning[]
  other_warnings: number
}

export type DroughtLevel = 'none' | 'watch' | 'moderate' | 'severe'

export interface Cause {
  key: string
  title: string
  amount_mm: number | null
  detail: string
}

export interface Diagnosis {
  level: DroughtLevel
  headline: string
  evidence: string[]
  causes: Cause[]
  confidence: 'high' | 'medium' | 'low'
  limitations: string[]
  missing_data: string[]
}

export interface AnalysisReport {
  parcel: Parcel
  crop: Crop
  analysis_date: string
  generated_at: string
  diagnosis: Diagnosis
  water: ModuleResult<WaterBalance>
  soil: ModuleResult<SoilProfile>
  satellite: ModuleResult<VegetationState>
  hydro: ModuleResult<HydroStatus>
  terrain: ModuleResult<RetentionAnalysis>
}

const query = (params: Record<string, string>) => new URLSearchParams(params).toString()

export const fetchCrops = () => getJson<Crop[]>('/api/crops')

export const searchParcels = (q: string, signal?: AbortSignal) =>
  getJson<Parcel[]>(`/api/parcels/search?${query({ q })}`, signal)

export const fetchParcelAt = (lon: number, lat: number, signal?: AbortSignal) =>
  getJson<Parcel>(`/api/parcels/at?${query({ lon: String(lon), lat: String(lat) })}`, signal)

/** `poll` only collects results of slow modules that finished in the background. */
export const fetchAnalysis = (
  parcelId: string,
  crop: string,
  date: string,
  signal?: AbortSignal,
  poll = false,
) =>
  getJson<AnalysisReport>(
    `/api/analysis?${query({ parcel_id: parcelId, crop, date, poll: String(poll) })}`,
    signal,
  )
