export interface Scenario {
  key: 'no_rain' | 'dry' | 'typical' | 'wet' | 'irrigated' | 'more_humus'
  label: string
  analog_year: number | null
  rain_mm: number
  et0_mm: number
  first_stress_day: string | null
  stress_days: number
  available_pct_end: number
  refill_mm: number
}

export interface Scenarios {
  start: string
  end: string
  humus_gain_mm: number
  items: Scenario[]
}

export interface EdoDrought {
  dekad: string
  cdi_class: number
  label: string
  drought: boolean
  agrees: boolean | null
}
