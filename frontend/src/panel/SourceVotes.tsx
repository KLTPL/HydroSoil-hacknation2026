import type { SourceSignal } from '../model'

const VERDICT = {
  dry: 'suszej niż zwykle',
  normal: 'typowo',
  wet: 'wilgotniej niż zwykle',
  missing: 'brak danych',
} as const

// The IUNG criterion is a threshold, not a comparison with earlier years.
const CRITERION: Record<SourceSignal['verdict'], string> = {
  dry: 'susza',
  normal: 'bez suszy',
  wet: 'bez suszy',
  missing: 'brak danych',
}

const verdictText = (s: SourceSignal) => (s.key === 'smsr' ? CRITERION[s.verdict] : VERDICT[s.verdict])

/** What each data source says against 10 years, with its reading. */
export function SourceVotes({ signals }: { signals: SourceSignal[] }) {
  return (
    <ul className="votes" aria-label="Co mówią źródła danych na tle 10 lat">
      {signals.map((s) => (
        <li key={s.key} className={`vote vote-${s.verdict}`}>
          <span className="vote-dot" aria-hidden="true" />
          <span className="vote-source">{s.source}</span>
          <span className="vote-verdict">{verdictText(s)}</span>
          {s.verdict !== 'missing' && (
            <span className="vote-detail">
              {s.value}
              {s.note && ` · ${s.note}`}
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}

/** A dot per source under the verdict (its sentence already gives the count); readings in Dane. */
export function VoteSummary({ signals, onDetails }: { signals: SourceSignal[]; onDetails: () => void }) {
  return (
    <div className="vote-summary">
      <span className="vote-dots" aria-hidden="true">
        {signals.map((s) => (
          <span key={s.key} className={`vote-${s.verdict}`} title={`${s.source}: ${verdictText(s)}`}>
            <span className="vote-dot" />
          </span>
        ))}
      </span>
      <button type="button" className="link-button no-print" onClick={onDetails}>
        Co mówi każde ze źródeł
      </button>
    </div>
  )
}
