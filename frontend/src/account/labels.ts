import type { ReportSummary } from './accountApi'

export const parcelLabel = (p: { name: string | null; number: string; region: string }) =>
  p.name ?? `Działka ${p.number}, ${p.region}`

const SEVERITY = { none: 0, watch: 1, moderate: 2, severe: 3 } as const

/** What changed since the previous analysis of the same parcel. */
export function changeText(now: ReportSummary, before: ReportSummary | null): string {
  if (!before) return 'pierwsza analiza tej działki'
  const parts: string[] = []
  const shift = SEVERITY[now.level] - SEVERITY[before.level]
  parts.push(shift > 0 ? 'gorzej' : shift < 0 ? 'lepiej' : 'ocena bez zmian')
  if (now.water_pct !== null && before.water_pct !== null) {
    const delta = Math.round(now.water_pct - before.water_pct)
    if (delta !== 0) parts.push(`woda ${delta > 0 ? '+' : '−'}${Math.abs(delta)} pkt proc.`)
  }
  return parts.join(', ')
}
