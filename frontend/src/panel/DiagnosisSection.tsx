import type { CSSProperties } from 'react'
import * as fmt from '../format'
import type { Diagnosis } from '../model'

export function CausesSection({ diagnosis }: { diagnosis: Diagnosis }) {
  if (diagnosis.causes.length === 0) return null
  const maxMm = Math.max(1, ...diagnosis.causes.map((c) => c.amount_mm ?? 0))
  return (
    <section className="report-section" aria-labelledby="causes-heading">
      <p className="eyebrow print-only">2 · Przyczyny</p>
      <h3 id="causes-heading">Dlaczego brakuje wody</h3>
      <ol className="causes">
        {diagnosis.causes.map((cause, i) => (
          <li key={cause.key} style={{ '--i': i } as CSSProperties}>
            <div className="cause-head">
              <span className="cause-title">{cause.title}</span>
              {cause.amount_mm !== null && (
                <span className="cause-mm">{fmt.mm(cause.amount_mm)}</span>
              )}
            </div>
            {cause.amount_mm !== null && (
              <span
                className="cause-bar"
                style={{ '--share': cause.amount_mm / maxMm } as CSSProperties}
                aria-hidden="true"
              />
            )}
            <p className="muted">{cause.detail}</p>
          </li>
        ))}
      </ol>
      <p className="muted fine">Wartości w mm wody: o ile dana przyczyna zmniejsza zapas wody dla roślin.</p>
    </section>
  )
}

export function EvidenceList({ diagnosis }: { diagnosis: Diagnosis }) {
  if (diagnosis.evidence.length === 0) return null
  return (
    <ul className="evidence">
      {diagnosis.evidence.map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ul>
  )
}

export function Limitations({ diagnosis }: { diagnosis: Diagnosis }) {
  return (
    <>
      {diagnosis.missing_data.length > 0 && (
        <ul className="missing">
          {diagnosis.missing_data.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      <ul className="limitations">
        {diagnosis.limitations.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </>
  )
}
