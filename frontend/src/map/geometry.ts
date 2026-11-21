import type { LngLatBoundsLike, PaddingOptions } from 'maplibre-gl'
import type { Geometry } from '../model'

function points(geometry: Geometry): number[][] {
  return geometry.coordinates.flat(geometry.type === 'Polygon' ? 1 : 2) as number[][]
}

export function bounds(geometry: Geometry): LngLatBoundsLike {
  const pts = points(geometry)
  const lons = pts.map((p) => p[0])
  const lats = pts.map((p) => p[1])
  return [Math.min(...lons), Math.min(...lats), Math.max(...lons), Math.max(...lats)]
}

/** Label position: the vertex average of the outer ring (good enough for compact hollows). */
export function centre(geometry: Geometry): [number, number] {
  const ring = (geometry.type === 'Polygon'
    ? geometry.coordinates[0]
    : geometry.coordinates[0][0]) as number[][]
  const sum = ring.reduce((acc, p) => [acc[0] + p[0], acc[1] + p[1]], [0, 0])
  return [sum[0] / ring.length, sum[1] / ring.length]
}

/** The panel floats over the map; keep fitted features in the part of the map left visible. */
export function viewPadding(extra = 60): Required<PaddingOptions> {
  const panel = document.querySelector('.panel')?.getBoundingClientRect()
  const mobile = window.matchMedia('(width < 720px)').matches
  return {
    top: extra,
    left: extra,
    right: extra + (!mobile && panel ? window.innerWidth - panel.left : 0),
    bottom: extra + (mobile && panel ? window.innerHeight - panel.top : 0),
  }
}
