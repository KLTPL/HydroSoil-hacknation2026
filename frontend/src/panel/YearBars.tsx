import type { CSSProperties } from 'react'
import type { Comparison } from '../api'

/** Value on the analysis date next to the same date in earlier years (current year highlighted). */
export function YearBars({
  comparison,
  year,
  format,
  label,
}: {
  comparison: Comparison
  year: number
  format: (value: number) => string
  label: string
}) {
  const rows = [...comparison.history, { year, value: comparison.value }]
  const values = rows.map((r) => r.value)
  const min = Math.min(0, ...values)
  const max = Math.max(0, ...values)
  const span = max - min || 1
  const zero = ((0 - min) / span) * 100
  return (
    <figure className="year-bars">
      <figcaption className="muted">{label}</figcaption>
      <ul>
        {rows.map((row) => {
          const start = ((Math.min(row.value, 0) - min) / span) * 100
          const width = (Math.abs(row.value) / span) * 100
          return (
            <li key={row.year} className={row.year === year ? 'current' : undefined}>
              <span className="year">{row.year}</span>
              <span className="track" style={{ '--zero': `${zero}%` } as CSSProperties}>
                <span
                  className={row.value < 0 ? 'bar negative' : 'bar'}
                  style={{ insetInlineStart: `${start}%`, width: `${Math.max(width, 0.5)}%` }}
                />
              </span>
              <span className="value">{format(row.value)}</span>
            </li>
          )
        })}
      </ul>
    </figure>
  )
}
