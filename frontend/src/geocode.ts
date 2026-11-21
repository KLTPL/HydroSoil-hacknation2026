import { ApiError } from './api'

/** A town or address found by the GUGiK address search (UUG). */
export interface Place {
  label: string
  area: string
  lon: number
  lat: number
  zoom: number
}

interface UugResult {
  city: string
  street?: string | null
  number?: string | null
  x: string
  y: string
  /** Address results: "{Polska,<voivodeship>,<county>,<commune>}" */
  jednostka?: string
  commune?: string
  voivodeship?: string
}

interface UugResponse {
  type?: 'city' | 'address' | 'street'
  results?: Record<string, UugResult> | null
  notice?: string
}

const UUG = 'https://services.gugik.gov.pl/uug/'
const RETRY_DELAY_MS = 700
const UNAVAILABLE = 'Wyszukiwarka miejscowości jest chwilowo niedostępna. Spróbuj za chwilę.'

/** UUG throttles bursts with a 200 "blocked for abuse" notice; one delayed retry gets through. */
async function queryUug(address: string, signal?: AbortSignal): Promise<UugResponse> {
  const url = `${UUG}?${new URLSearchParams({ request: 'GetAddress', address, srid: '4326' })}`
  for (let attempt = 0; attempt < 2; attempt++) {
    if (attempt > 0) await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS))
    const response = await fetch(url, { signal })
    if (!response.ok) throw new ApiError(response.status, UNAVAILABLE)
    const body = (await response.json()) as UugResponse
    if (!body.notice) return body
  }
  throw new ApiError(503, UNAVAILABLE)
}

function area(result: UugResult): string {
  if (result.commune) return `gm. ${result.commune} (${result.voivodeship})`
  const [, voivodeship, , commune] = (result.jednostka ?? '').replace(/[{}]/g, '').split(',')
  return commune ? `gm. ${commune} (${voivodeship})` : ''
}

export async function searchPlaces(q: string, signal?: AbortSignal): Promise<Place[]> {
  const body = await queryUug(q, signal)
  const isAddress = body.type === 'address'
  return Object.values(body.results ?? {}).map((r) => ({
    label: [r.city, r.street, r.number].filter(Boolean).join(' '),
    area: area(r),
    lon: Number(r.x),
    lat: Number(r.y),
    // A village fills the screen at 14; an address lands on its parcels.
    zoom: isAddress ? 17 : 14,
  }))
}
