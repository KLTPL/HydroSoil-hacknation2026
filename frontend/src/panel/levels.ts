/** Drought verdict labels and colour tones (CSS `tone-*` classes). */
export const LEVEL = {
  none: { label: 'Wody wystarcza', tone: 'ok' },
  watch: { label: 'Uwaga na wodę', tone: 'watch' },
  moderate: { label: 'Niedobór wody', tone: 'moderate' },
  severe: { label: 'Silny niedobór wody', tone: 'severe' },
} as const
