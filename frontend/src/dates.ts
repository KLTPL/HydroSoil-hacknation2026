/** Analysis dates accepted by the API: today and up to HISTORY_YEARS back. */
const HISTORY_YEARS = 10

export function earliestIso(today: string): string {
  const [y, m, d] = today.split('-').map(Number)
  const day = m === 2 && d === 29 ? 28 : d
  return `${y - HISTORY_YEARS}-${String(m).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}
