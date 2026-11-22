import type { LngLatBoundsLike, Map as MapLibreMap, PaddingOptions } from 'maplibre-gl'
import { viewPadding } from './geometry'

/** Cards anchored to the bottom of the map that the parcel should not sit under. */
const BOTTOM_CARDS = ['.rain-control', '.legend']

/**
 * Each bottom card can be cleared by framing above it or beside it. Padding the whole bottom
 * edge wastes the width a short card leaves free, so try every way and keep the closest view.
 */
function candidates(map: MapLibreMap, base: Required<PaddingOptions>, extra: number) {
  const box = map.getContainer().getBoundingClientRect()
  const freeMid = box.left + (base.left + box.width - base.right) / 2
  const cards = BOTTOM_CARDS.flatMap((selector) => {
    const rect = map.getContainer().parentElement?.querySelector(selector)?.getBoundingClientRect()
    return rect && rect.width > 0 ? [rect] : []
  })
  let options = [base]
  for (const card of cards) {
    options = options.flatMap((padding) => {
      const above = { ...padding, bottom: Math.max(padding.bottom, box.bottom - card.top + extra) }
      const beside = { ...padding }
      if (card.left + card.width / 2 > freeMid)
        beside.right = Math.max(padding.right, box.right - card.left + extra)
      else beside.left = Math.max(padding.left, card.right - box.left + extra)
      return [above, beside]
    })
  }
  return options
}

/** Fits the box into the free part of the map that shows it largest. */
export function frameClear(map: MapLibreMap, box: LngLatBoundsLike, maxZoom: number, extra = 60) {
  const base = viewPadding(extra)
  // On phones the cards stack inside the bottom sheet, which the base padding already clears.
  const options = window.matchMedia('(width < 720px)').matches
    ? [base]
    : candidates(map, base, extra)
  const zoomFor = (padding: PaddingOptions) =>
    map.cameraForBounds(box, { padding, maxZoom })?.zoom ?? -Infinity
  const best = options.reduce((a, b) => (zoomFor(b) > zoomFor(a) ? b : a))
  map.fitBounds(box, { padding: best, maxZoom })
}
