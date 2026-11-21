import { useState } from 'react'
import { COLORS, GEOPORTAL } from '../map/style'
import type { Geometry } from '../model'

/** Rendered at 64 CSS px; the image is fetched at 2× for sharp high-density screens. */
const IMAGE_PX = 128
/** Orthophoto margin around the parcel, as a share of its larger side. */
const MARGIN = 0.15
const EARTH_RADIUS_M = 6378137

/** Web Mercator (EPSG:3857), the CRS the orthophoto is requested in, so outline and image align. */
function mercator([lon, lat]: number[]): [number, number] {
  const x = (EARTH_RADIUS_M * lon * Math.PI) / 180
  const y = EARTH_RADIUS_M * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))
  return [x, y]
}

function rings(geometry: Geometry): number[][][] {
  return (geometry.type === 'Polygon'
    ? geometry.coordinates
    : (geometry.coordinates as number[][][][]).flat()) as number[][][]
}

/** Square box around the parcel with a margin: [minX, minY, maxX, maxY] in metres. */
function squareBox(points: [number, number][]): [number, number, number, number] {
  const xs = points.map((p) => p[0])
  const ys = points.map((p) => p[1])
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2
  const cy = (Math.min(...ys) + Math.max(...ys)) / 2
  const side = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 1)
  const half = (side * (1 + 2 * MARGIN)) / 2
  return [cx - half, cy - half, cx + half, cy + half]
}

function orthophotoUrl(box: [number, number, number, number]): string {
  const params = new URLSearchParams({
    SERVICE: 'WMS',
    REQUEST: 'GetMap',
    VERSION: '1.3.0',
    LAYERS: 'Raster',
    STYLES: '',
    FORMAT: 'image/jpeg',
    CRS: 'EPSG:3857',
    WIDTH: String(IMAGE_PX),
    HEIGHT: String(IMAGE_PX),
    BBOX: box.join(','),
  })
  return `${GEOPORTAL}?${params}`
}

/** Small orthophoto of a saved parcel with its outline, so the list is easy to recognise. */
export function ParcelThumb({ geometry }: { geometry: Geometry | null }) {
  const [failed, setFailed] = useState(false)
  const projected = geometry ? rings(geometry).map((ring) => ring.map(mercator)) : []
  const points = projected.flat()
  if (points.length === 0) return <div className="parcel-thumb" aria-hidden="true" />

  const box = squareBox(points)
  const [minX, minY, maxX, maxY] = box
  // SVG y grows downwards, northing upwards: draw with -y.
  const path = projected
    .map((ring) => `M${ring.map(([x, y]) => `${x},${-y}`).join('L')}Z`)
    .join('')

  return (
    <div className="parcel-thumb" aria-hidden="true">
      {!failed && (
        <img src={orthophotoUrl(box)} alt="" loading="lazy" onError={() => setFailed(true)} />
      )}
      <svg viewBox={`${minX} ${-maxY} ${maxX - minX} ${maxY - minY}`}>
        <path
          d={path}
          fill={COLORS.parcel}
          fillOpacity={0.15}
          fillRule="evenodd"
          stroke={COLORS.parcel}
          strokeWidth={2}
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  )
}
