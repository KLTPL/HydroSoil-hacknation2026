import { ApiError } from './api'

/** A town, street or address suggested by Photon (OpenStreetMap geocoder by komoot). */
export interface Place {
  id: string
  label: string
  area: string
  lon: number
  lat: number
  zoom: number
}

interface PhotonProperties {
  osm_type: string
  osm_id: number
  type: 'city' | 'locality' | 'district' | 'street' | 'house'
  countrycode?: string
  name?: string
  street?: string
  housenumber?: string
  city?: string
  county?: string
  state?: string
}

interface PhotonResponse {
  features: { geometry: { coordinates: [number, number] }; properties: PhotonProperties }[]
}

// UUG (GUGiK) has no prefix matching and often answers "blocked for abuse", so it cannot drive
// suggestions as the user types; Photon can.
const PHOTON = 'https://photon.komoot.io/api/'
const POLAND_BBOX = '14.07,49.0,24.15,54.84'
const LAYERS = ['city', 'locality', 'district', 'street', 'house']
const ZOOM: Record<PhotonProperties['type'], number> = {
  city: 14,
  locality: 15,
  district: 15,
  street: 16,
  house: 17,
}
const MAX_PLACES = 6

function toPlace(
  [lon, lat]: [number, number],
  p: PhotonProperties,
): Place | null {
  if (p.countrycode !== 'PL') return null
  // The house layer also holds named points of interest; keep only real addresses.
  if (p.type === 'house' && !p.housenumber) return null
  const street = [p.street, p.housenumber].filter(Boolean).join(' ')
  const label =
    p.type === 'house' || p.type === 'street'
      ? [p.city, street || p.name].filter(Boolean).join(', ')
      : (p.name ?? '')
  const area = [p.type !== 'house' && p.type !== 'street' ? p.city : null, p.county, p.state]
    .filter((part) => part && part !== label)
    .join(', ')
  return { id: `${p.osm_type}${p.osm_id}`, label, area, lon, lat, zoom: ZOOM[p.type] }
}

export async function searchPlaces(q: string, signal?: AbortSignal): Promise<Place[]> {
  const params = new URLSearchParams({ q, limit: String(MAX_PLACES * 2), bbox: POLAND_BBOX })
  for (const layer of LAYERS) params.append('layer', layer)
  const response = await fetch(`${PHOTON}?${params}`, { signal })
  if (!response.ok) {
    throw new ApiError(response.status, 'Wyszukiwarka miejscowości nie odpowiada. Spróbuj za chwilę.')
  }
  const body = (await response.json()) as PhotonResponse
  const seen = new Set<string>()
  const places: Place[] = []
  for (const feature of body.features) {
    const place = toPlace(feature.geometry.coordinates, feature.properties)
    // OSM often maps a town twice (place node and boundary); show it once.
    const key = place && `${place.label}|${place.area}`
    if (!place || !key || seen.has(key)) continue
    seen.add(key)
    places.push(place)
  }
  return places.slice(0, MAX_PLACES)
}
