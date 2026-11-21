import { useId, useState, type CSSProperties } from 'react'
import * as fmt from '../format'
import type { Cause, Diagnosis } from '../model'

export function CausesSection({ diagnosis }: { diagnosis: Diagnosis }) {
  const [open, setOpen] = useState<string | null>(null)
  if (diagnosis.causes.length === 0) return null
  const maxMm = Math.max(1, ...diagnosis.causes.map((c) => c.amount_mm ?? 0))
  return (
    <section className="report-section" aria-labelledby="causes-heading">
      <p className="eyebrow print-only">2 · Przyczyny</p>
      <h3 id="causes-heading">Dlaczego brakuje wody</h3>
      <ol className="causes">
        {diagnosis.causes.map((cause, i) => (
          <CauseItem
            key={cause.key}
            cause={cause}
            index={i}
            share={(cause.amount_mm ?? 0) / maxMm}
            open={open === cause.key}
            onToggle={() => setOpen(open === cause.key ? null : cause.key)}
          />
        ))}
      </ol>
      <p className="muted fine">Wartości w mm wody: o ile dana przyczyna zmniejsza zapas wody dla roślin.</p>
    </section>
  )
}

interface CauseProps {
  cause: Cause
  index: number
  share: number
  open: boolean
  onToggle: () => void
}

/** Title, size and bar; the explanation opens on click (always printed). */
function CauseItem({ cause, index, share, open, onToggle }: CauseProps) {
  const detailId = useId()
  return (
    <li style={{ '--i': index } as CSSProperties}>
      <button type="button" className="cause-toggle" aria-expanded={open} aria-controls={detailId} onClick={onToggle}>
        <span className="cause-head">
          <span className="cause-title">{cause.title}</span>
          {cause.amount_mm !== null && <span className="cause-mm">{fmt.mm(cause.amount_mm)}</span>}
        </span>
        {cause.amount_mm !== null && (
          <span className="cause-bar" style={{ '--share': share } as CSSProperties} aria-hidden="true" />
        )}
      </button>
      <p id={detailId} className="cause-detail muted" hidden={!open}>
        {cause.detail}
      </p>
    </li>
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
