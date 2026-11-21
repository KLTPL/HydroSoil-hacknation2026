import type { DataSource } from '../api'
import * as fmt from '../format'

export function Sources({ sources }: { sources: DataSource[] }) {
  if (sources.length === 0) return null
  return (
    <ul className="sources muted">
      {sources.map((s) => (
        <li key={s.name}>
          Źródło:{' '}
          <a href={s.url} target="_blank" rel="noreferrer">
            {s.name}
          </a>{' '}
          · {s.retrieved === 'live' ? 'pobrane teraz' : 'z pamięci podręcznej'},{' '}
          {fmt.dateTime(s.retrieved_at)} · {s.license}
        </li>
      ))}
    </ul>
  )
}
