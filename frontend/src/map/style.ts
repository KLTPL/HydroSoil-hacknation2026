import type { StyleSpecification } from 'maplibre-gl'

const GEOPORTAL = 'https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution'
const KIEG = 'https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow'

function wmsTiles(base: string, layers: string, format: string, transparent: boolean): string[] {
  const params = new URLSearchParams({
    SERVICE: 'WMS',
    REQUEST: 'GetMap',
    VERSION: '1.3.0',
    LAYERS: layers,
    STYLES: '',
    FORMAT: format,
    TRANSPARENT: String(transparent).toUpperCase(),
    CRS: 'EPSG:3857',
    WIDTH: '512',
    HEIGHT: '512',
  })
  // MapLibre substitutes {bbox-epsg-3857}; it must not be URL-encoded.
  return [`${base}?${params}&BBOX={bbox-epsg-3857}`]
}

export const ORTHO_SOURCE = 'orto'
/** From this zoom on, only the orthophoto is shown as the base map. */
export const STREET_MAP_MAX_ZOOM = 13
export const PARCEL_SOURCE = 'parcel'
export const SITES_SOURCE = 'sites'
export const SITES_FILL_LAYER = 'sites-fill'
export const DITCHES_SOURCE = 'ditches'
export const FLOW_SOURCE = 'flow'
export const FLOW_LAYER = 'flow-line'
export const RELIEF_SOURCE = 'relief'
/** The relief image is inserted below this layer (above the orthophoto). */
export const RELIEF_BEFORE = 'kieg'

export const COLORS = {
  pond: '#1f7cf0',
  wetDepression: '#4cc3e6',
  parcel: '#ffd23f',
  selected: '#ffffff',
  ditch: '#5ee6ff',
  weir: '#ff4f7b',
  flow: '#e6f6ff',
}

const EMPTY = { type: 'FeatureCollection' as const, features: [] }

export const mapStyle: StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      maxzoom: 19,
      attribution: '© OpenStreetMap',
    },
    [ORTHO_SOURCE]: {
      type: 'raster',
      tiles: wmsTiles(GEOPORTAL, 'Raster', 'image/jpeg', false),
      tileSize: 512,
      attribution: 'Ortofotomapa © GUGiK',
    },
    kieg: {
      type: 'raster',
      tiles: wmsTiles(KIEG, 'dzialki,numery_dzialek', 'image/png', true),
      tileSize: 512,
      attribution: 'Działki © GUGiK (KIEG)',
    },
    [PARCEL_SOURCE]: { type: 'geojson', data: EMPTY },
    [SITES_SOURCE]: { type: 'geojson', data: EMPTY, promoteId: 'id' },
    [DITCHES_SOURCE]: { type: 'geojson', data: EMPTY },
    [FLOW_SOURCE]: { type: 'geojson', data: EMPTY },
  },
  layers: [
    // Neutral ground under the orthophoto while it loads: the street map hides at field zooms
    // so a slow orthophoto never leaves a cartoon map standing in for the real terrain.
    { id: 'ground', type: 'background', paint: { 'background-color': '#c9cfc6' } },
    { id: 'osm', type: 'raster', source: 'osm', maxzoom: STREET_MAP_MAX_ZOOM },
    { id: 'orto', type: 'raster', source: ORTHO_SOURCE, minzoom: 12 },
    { id: 'kieg', type: 'raster', source: 'kieg', minzoom: 15, paint: { 'raster-opacity': 0.85 } },
    {
      id: 'parcel-fill',
      type: 'fill',
      source: PARCEL_SOURCE,
      paint: { 'fill-color': COLORS.parcel, 'fill-opacity': 0.12 },
    },
    {
      id: FLOW_LAYER,
      type: 'line',
      source: FLOW_SOURCE,
      layout: { 'line-cap': 'round', 'line-join': 'round', visibility: 'none' },
      paint: {
        'line-color': COLORS.flow,
        'line-opacity': 0.7,
        // Width grows with the area draining through the line (log scale).
        'line-width': [
          'interpolate',
          ['linear'],
          ['ln', ['get', 'area']],
          6.7, 0.6,
          9, 1.6,
          11.5, 3.5,
        ],
      },
    },
    {
      id: SITES_FILL_LAYER,
      type: 'fill',
      source: SITES_SOURCE,
      paint: {
        'fill-color': [
          'match',
          ['get', 'kind'],
          'pond',
          COLORS.pond,
          COLORS.wetDepression,
        ],
        'fill-opacity': ['case', ['boolean', ['feature-state', 'selected'], false], 0.85, 0.55],
        'fill-opacity-transition': { duration: 600 },
      },
    },
    {
      id: 'sites-line',
      type: 'line',
      source: SITES_SOURCE,
      paint: {
        'line-color': [
          'case',
          ['boolean', ['feature-state', 'selected'], false],
          COLORS.selected,
          COLORS.pond,
        ],
        'line-width': ['case', ['boolean', ['feature-state', 'selected'], false], 3, 1],
      },
    },
    {
      id: 'ditches-line',
      type: 'line',
      source: DITCHES_SOURCE,
      filter: ['==', ['geometry-type'], 'LineString'],
      paint: { 'line-color': COLORS.ditch, 'line-width': 3, 'line-dasharray': [2, 1] },
    },
    {
      id: 'parcel-line',
      type: 'line',
      source: PARCEL_SOURCE,
      paint: { 'line-color': COLORS.parcel, 'line-width': 3 },
    },
    {
      id: 'weirs',
      type: 'circle',
      source: DITCHES_SOURCE,
      filter: ['==', ['geometry-type'], 'Point'],
      paint: {
        'circle-radius': 6,
        'circle-color': COLORS.weir,
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': 2,
      },
    },
  ],
}
