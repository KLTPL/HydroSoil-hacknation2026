// Mirrors backend/src/retencja_api/models.py.

import type { EdoDrought, Scenarios } from './scenario-types'

export type { EdoDrought, Scenario, Scenarios } from './scenario-types'

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

export interface DitchWeirs {
  id: number
  kind: string
  length_m: number
  slope_pct: number
  weir_count: number
  weir_head_m: number
  channel_m3: number
  soil_m3: Range
  geometry: { type: 'LineString'; coordinates: number[][] }
  weirs: { type: 'MultiPoint'; coordinates: number[][] }
}

export interface FlowPath {
  area_m2: number
  end: 'pool' | 'exit' | 'join'
  next: number | null
  geometry: { type: 'LineString'; coordinates: number[][] }
}

export interface ReliefImage {
  /** [lon, lat]: top-left, top-right, bottom-right, bottom-left */
  corners: [number, number][]
  spread_m: number
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
  ditches: DitchWeirs[]
  ditches_checked: boolean
  flow: FlowPath[]
  relief: ReliefImage | null
}


export type ModuleName = 'water' | 'soil' | 'satellite' | 'hydro' | 'land' | 'terrain' | 'edo'

/** One data module finished during a streamed analysis. */
export interface ModuleProgress {
  module: ModuleName
  status: ModuleResult<unknown>['status']
  fact: string
  duration_ms: number
  live: boolean
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
  scenarios: Scenarios | null
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

export interface LandCover {
  year: number
  classes: { code: number; name: string; share: number }[]
  agricultural_share: number
  is_agricultural: boolean
}

export type DroughtLevel = 'none' | 'watch' | 'moderate' | 'severe'

export interface Cause {
  key: string
  title: string
  amount_mm: number | null
  detail: string
}

export interface SourceSignal {
  key: string
  source: string
  verdict: 'dry' | 'normal' | 'wet' | 'missing'
  value: string
  note: string
}

export interface Diagnosis {
  level: DroughtLevel
  headline: string
  signals: SourceSignal[]
  stress_threshold_pct: number | null
  warnings: string[]
  evidence: string[]
  causes: Cause[]
  confidence: 'high' | 'medium' | 'low'
  limitations: string[]
  missing_data: string[]
}

export interface Recommendation {
  key: string
  category: 'retention' | 'soil' | 'crop' | 'irrigation'
  title: string
  action: string
  why: string
  effect_m3: Range | null
  effect_note: string | null
  when: string
  cost: 'niski' | 'średni' | 'wysoki'
  formalities: string | null
  site_ids: number[]
  ditch_ids: number[]
}

export interface AnalysisReport {
  parcel: Parcel
  crop: Crop
  analysis_date: string
  generated_at: string
  diagnosis: Diagnosis
  recommendations: Recommendation[]
  water: ModuleResult<WaterBalance>
  soil: ModuleResult<SoilProfile>
  satellite: ModuleResult<VegetationState>
  hydro: ModuleResult<HydroStatus>
  land: ModuleResult<LandCover>
  terrain: ModuleResult<RetentionAnalysis>
  edo: ModuleResult<EdoDrought>
}
